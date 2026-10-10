"""Real registered executions, held-out boundaries and reversible route releases."""
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nerve_awim.agent_learning_v12 import AgentTask, RegisteredStrategy
from nerve_awim.agent_bridge_v13 import STRATEGIES
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority


def tasks(prefix, n=5):
    cases, answers = [], {}
    for context in ('extract', 'normalise'):
        for i in range(n):
            raw = f'  {prefix.upper()}.{i}@EXAMPLE.ORG  '
            task = AgentTask(f'{prefix}.{context}.{i}', context,
                             json.dumps({'email': raw}) if context == 'extract' else raw)
            cases.append(task)
            answers[task.task_id] = raw if context == 'extract' else raw.strip().lower()
    return cases, answers


class GovernedLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'learning.sqlite'
        self.authority = LearningAuthority()
        self.actors = {role: self.authority.issue('tenant-a', 'agent', role)
                       for role in ('trainer', 'evaluator', 'operator', 'runtime', 'auditor')}
        self.training, self.answers = tasks('train', 3)
        self.holdout, answers = tasks('heldout')
        self.answers.update(answers)
        self.judge = lambda task, output: output == self.answers[task.task_id]
        self.engine = self.make_engine()
        self.initial = self.engine.bootstrap(self.actors['operator'])

    def make_engine(self, **kwargs):
        options = dict(authority=self.authority, strategies=STRATEGIES,
                       judge=self.judge, contract_revision='tools-v13-judge-v1',
                       baseline_routes={'extract': 'raw', 'normalise': 'lower-only'})
        options.update(kwargs)
        return GovernedLearning(self.path, **options)

    def train(self):
        for task in self.training:
            self.engine.learn_from_task(self.actors['trainer'], task)
        return self.engine.freeze_candidate(self.actors['trainer'])

    def evaluate(self, candidate):
        return self.engine.evaluate_candidate(self.actors['evaluator'], candidate, self.holdout)

    def activate(self, candidate):
        return self.engine.activate(self.actors['operator'], candidate,
                                    expected_generation=0, reason='review-1')

    def test_end_to_end_real_handlers_change_only_after_approval_then_rollback(self):
        task = AgentTask('live.1', 'normalise', '  LIVE@EXAMPLE.ORG  ')
        runtime = self.actors['runtime']
        self.assertEqual(self.engine.execute(runtime, task)['value'], '  live@example.org  ')
        candidate = self.train()
        evidence = self.evaluate(candidate)
        self.assertEqual(evidence['status'], 'passed')
        self.assertEqual(self.engine.status(runtime)['generation'], 0)
        before = self.engine.status(runtime)['task_counts']
        approved = self.activate(candidate)
        executed = self.engine.execute(runtime, task)
        self.assertEqual(executed['value'], 'live@example.org')
        self.assertEqual(executed['release'], approved['active_release'])
        self.assertFalse(executed['feedback_written'])
        self.assertEqual(self.engine.status(runtime)['task_counts'], before)
        rolled = self.engine.rollback(self.actors['operator'], self.initial['active_release'],
                                      expected_generation=1, reason='rollback-review')
        self.assertEqual(rolled['generation'], 2)
        self.assertEqual(self.engine.execute(runtime, task)['value'], '  live@example.org  ')
        self.assertEqual([e['event'] for e in self.engine.audit(self.actors['operator'])][-2:],
                         ['activated', 'rolled_back'])

    def test_training_scores_come_from_actual_handlers_not_user_rewards(self):
        candidate = self.train()
        report = self.engine.candidate_report(self.actors['auditor'], candidate)
        self.assertEqual(report['training']['normalise']['trim-lower'], {'hits': 3, 'tasks': 3})
        self.assertEqual(report['training']['normalise']['lower-only']['hits'], 0)
        with self.assertRaises(TypeError):
            self.engine.learn_from_task(self.actors['trainer'], self.training[0], reward=1)

    def test_frozen_snapshot_unchanged_by_later_training(self):
        candidate = self.train()
        before = self.engine.candidate_report(self.actors['auditor'], candidate)
        more, answers = tasks('later', 3)
        self.answers.update(answers)
        for task in more:
            self.engine.learn_from_task(self.actors['trainer'], task)
        self.assertEqual(before, self.engine.candidate_report(self.actors['auditor'], candidate))

    def test_persistence_survives_new_engine_and_new_host_capabilities(self):
        candidate = self.train()
        self.evaluate(candidate)
        active = self.activate(candidate)
        self.authority = LearningAuthority()
        operator = self.authority.issue('tenant-a', 'agent', 'operator')
        runtime = self.authority.issue('tenant-a', 'agent', 'runtime')
        reopened = self.make_engine()
        self.assertEqual(reopened.status(operator)['active_release'], active['active_release'])
        self.assertEqual(reopened.execute(runtime, AgentTask('live', 'normalise', ' X '))['value'], 'x')
        self.assertEqual(reopened.rollback(operator, self.initial['active_release'],
                         expected_generation=1, reason='restart-rollback')['generation'], 2)

    def test_trainer_and_evaluator_cannot_activate_or_rollback(self):
        candidate = self.train()
        self.evaluate(candidate)
        for role in ('trainer', 'evaluator', 'runtime', 'auditor'):
            with self.subTest(role=role), self.assertRaises(PermissionError):
                self.engine.activate(self.actors[role], candidate, expected_generation=0, reason='fake')
            with self.assertRaises(PermissionError):
                self.engine.rollback(self.actors[role], self.initial['active_release'],
                                     expected_generation=0, reason='fake')

    def test_forged_and_revoked_capabilities_rejected(self):
        for actor in (replace(self.actors['trainer'], role='operator'),
                      replace(self.actors['operator'], tenant='tenant-b')):
            with self.assertRaises(PermissionError):
                self.engine.status(actor)
        self.authority.revoke(self.actors['operator'])
        with self.assertRaises(PermissionError):
            self.engine.status(self.actors['operator'])

    def test_tenant_and_agent_isolation_for_candidates_releases_and_training(self):
        candidate = self.train()
        for tenant, agent in (('tenant-b', 'agent'), ('tenant-a', 'other-agent')):
            operator = self.authority.issue(tenant, agent, 'operator')
            trainer = self.authority.issue(tenant, agent, 'trainer')
            self.engine.bootstrap(operator)
            with self.assertRaises(LookupError):
                self.engine.candidate_report(operator, candidate)
            with self.assertRaises(LookupError):
                self.engine.rollback(operator, self.initial['active_release'],
                                     expected_generation=0, reason='other')
            with self.assertRaises(ValueError):
                self.engine.freeze_candidate(trainer)

    def test_underpowered_training_and_holdout_fail_before_evaluation(self):
        with self.assertRaises(ValueError):
            self.engine.freeze_candidate(self.actors['trainer'])
        candidate = self.train()
        with self.assertRaisesRegex(ValueError, 'five held-out'):
            self.engine.evaluate_candidate(self.actors['evaluator'], candidate, self.holdout[:3])
        self.assertEqual(self.engine.candidate_report(self.actors['auditor'], candidate)['status'], 'frozen')

    def test_overlap_detected_by_payload_even_with_renamed_task_ids(self):
        candidate = self.train()
        overlap = [replace(t, task_id='alias.' + t.task_id) for t in self.training]
        with self.assertRaisesRegex(ValueError, 'already reserved'):
            self.engine.evaluate_candidate(self.actors['evaluator'], candidate, overlap + self.holdout)
        self.assertNotIn('holdout', self.engine.status(self.actors['operator'])['task_counts'])
        self.assertEqual(self.evaluate(candidate)['status'], 'passed')

    def test_heldout_tasks_cannot_train_or_evaluate_another_candidate(self):
        candidate = self.train()
        self.evaluate(candidate)
        renamed = replace(self.holdout[0], task_id='renamed')
        with self.assertRaises(ValueError):
            self.engine.learn_from_task(self.actors['trainer'], renamed)
        second = self.engine.freeze_candidate(self.actors['trainer'])
        with self.assertRaises(ValueError):
            self.evaluate(second)

    def test_same_candidate_cannot_retry_holdout(self):
        candidate = self.train()
        self.evaluate(candidate)
        with self.assertRaisesRegex(ValueError, 'fresh frozen'):
            self.evaluate(candidate)

    def test_pending_candidate_never_deploys(self):
        with self.assertRaisesRegex(ValueError, 'holdout gate'):
            self.activate(self.train())

    def test_no_improvement_against_capable_baseline_is_rejected(self):
        path = Path(self.temp.name) / 'capable.sqlite'
        capable = GovernedLearning(path, authority=self.authority, strategies=STRATEGIES,
            judge=self.judge, contract_revision='capable-v1',
            baseline_routes={'extract': 'json-field', 'normalise': 'trim-lower'})
        capable.bootstrap(self.actors['operator'])
        for task in self.training:
            capable.learn_from_task(self.actors['trainer'], task)
        candidate = capable.freeze_candidate(self.actors['trainer'])
        result = capable.evaluate_candidate(self.actors['evaluator'], candidate, self.holdout)
        self.assertEqual(result['status'], 'rejected')
        with self.assertRaises(ValueError):
            capable.activate(self.actors['operator'], candidate, expected_generation=0, reason='no-gain')

    def test_holdout_regression_blocks_activation(self):
        candidate = self.train()
        # New evaluation cases have a different desired contract, showing drift.
        for task in self.holdout:
            self.answers[task.task_id] = task.payload.lower() if task.context == 'normalise' else task.payload
        self.assertEqual(self.evaluate(candidate)['status'], 'rejected')
        with self.assertRaises(ValueError):
            self.activate(candidate)

    def test_judge_failure_stores_no_partial_training_rewards(self):
        self.answers.clear()
        with self.assertRaises(RuntimeError):
            self.engine.learn_from_task(self.actors['trainer'], self.training[0])
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM gl_outcomes').fetchone()[0], 0)
        with self.assertRaises(ValueError):
            self.engine.learn_from_task(self.actors['trainer'], self.training[0])

    def test_holdout_judge_failure_is_terminal_and_unpromotable(self):
        candidate = self.train()
        self.answers.clear()
        with self.assertRaises(RuntimeError):
            self.evaluate(candidate)
        self.assertEqual(self.engine.candidate_report(self.actors['operator'], candidate)['status'], 'failed')
        with self.assertRaises(ValueError):
            self.activate(candidate)

    def test_invalid_judge_boolean_is_not_a_reward(self):
        self.engine.judge = lambda task, value: 'yes'
        with self.assertRaises(RuntimeError):
            self.engine.learn_from_task(self.actors['trainer'], self.training[0])

    def test_stale_activation_after_another_release_or_rollback_rejected(self):
        candidate = self.train()
        second = self.engine.freeze_candidate(self.actors['trainer'])
        self.evaluate(candidate)
        alternate, answers = tasks('alternate')
        self.answers.update(answers)
        self.engine.evaluate_candidate(self.actors['evaluator'], second, alternate)
        self.activate(candidate)
        with self.assertRaisesRegex(ValueError, 'stale approval'):
            self.activate(second)
        self.engine.rollback(self.actors['operator'], self.initial['active_release'],
                             expected_generation=1, reason='rollback')
        with self.assertRaises(ValueError):
            self.engine.activate(self.actors['operator'], second, expected_generation=2, reason='stale')

    def test_revision_change_fails_closed(self):
        self.train()
        changed = self.make_engine(contract_revision='new-judge-v2')
        with self.assertRaisesRegex(ValueError, 'contract revision changed'):
            changed.status(self.actors['operator'])
        with self.assertRaises(ValueError):
            changed.execute(self.actors['runtime'], AgentTask('live', 'normalise', 'hi'))

    def test_context_regression_is_rejected_even_with_overall_gain(self):
        candidate = self.train()
        extra, answers = tasks('extra')
        self.answers.update(answers)
        # Ten improving extraction tasks cannot hide five regressing normalisation tasks.
        holdout = self.holdout + [t for t in extra if t.context == 'extract']
        for task in holdout:
            if task.context == 'normalise':
                self.answers[task.task_id] = task.payload.lower()
        result = self.engine.evaluate_candidate(self.actors['evaluator'], candidate, holdout)
        contexts = result['contexts'].values()
        self.assertGreater(sum(r['candidate_hits'] for r in contexts),
                           sum(r['baseline_hits'] for r in contexts))
        self.assertEqual(result['status'], 'rejected')

    def test_handler_errors_remain_in_holdout_denominators(self):
        candidate = self.train()
        # A failing registered handler cannot silently shrink the test sample.
        def broken(value):
            raise RuntimeError('handler failed')
        self.engine._registry[('normalise', 'trim-lower')] = broken
        result = self.evaluate(candidate)
        self.assertEqual(result['contexts']['normalise']['tasks'], 5)
        self.assertEqual(result['contexts']['normalise']['candidate_errors'], 5)
        self.assertEqual(result['status'], 'rejected')

    def test_concurrent_approval_only_one_release_wins(self):
        from concurrent.futures import ThreadPoolExecutor
        candidate = self.train()
        self.evaluate(candidate)
        def approve():
            try:
                self.activate(candidate)
                return 'activated'
            except ValueError:
                return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: approve(), range(2)))
        self.assertCountEqual(results, ['activated', 'stale'])
        self.assertEqual(self.engine.status(self.actors['operator'])['generation'], 1)

    def test_runtime_does_not_accept_unregistered_context(self):
        with self.assertRaises(ValueError):
            self.engine.execute(self.actors['runtime'], AgentTask('bad', 'shell', 'touch anything'))

    def test_database_contains_no_raw_payload_or_expected_answer(self):
        self.train()
        raw = self.path.read_bytes()
        self.assertNotIn(b'TRAIN.0@EXAMPLE.ORG', raw)
        self.assertNotIn(b'train.0@example.org', raw)


if __name__ == '__main__':
    unittest.main()
