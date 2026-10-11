from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.canary_learning_v23 import CanaryLearning


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.db'
        auth = LearningAuthority()
        self.actors = {r: auth.issue('tenant', 'agent', r)
                       for r in ('trainer', 'runtime', 'evaluator', 'operator', 'auditor')}
        self.engine = GovernedLearning(self.path, authority=auth, strategies=REPOSITORY_STRATEGIES,
            judge=repository_judge, baseline_routes={CONTEXT: 'regex-inventory'}, contract_revision='test')
        self.baseline = self.engine.bootstrap(self.actors['operator'])
        for n in range(3):
            self.engine.learn_from_task(self.actors['trainer'], self.task(n))
        self.candidate = self.engine.freeze_candidate(self.actors['trainer'])
        self.engine.evaluate_candidate(self.actors['evaluator'], self.candidate,
                                        [self.task(n) for n in range(3, 8)])
        self.canary = CanaryLearning(self.engine)
        self.id = self.start()

    @staticmethod
    def task(n):
        return AgentTask(f'task-{n}', CONTEXT, f'# private source {n}\ndef top_{n}():\n    def nested(): pass\n')

    def start(self, **kwargs):
        return self.canary.start(self.actors['operator'], self.candidate,
            expected_generation=0, reason='test-review', percent=25, required_successes=5, **kwargs)

    def selected(self, start=100, yes=True):
        for n in range(start, start + 10000):
            task = self.task(n)
            _, digest = self.engine._task(task)
            if (int(sha256((self.id + ':' + digest).encode()).hexdigest(), 16) % 100 < 25) == yes:
                return task
        self.fail('no sample task found')

    def execute(self, task=None):
        return self.canary.execute(self.actors['runtime'], self.id, task or self.selected())

    def report(self):
        return self.canary.report(self.actors['auditor'], self.id)

    def test_sampling_returns_baseline_or_approved_candidate_without_activation(self):
        self.assertEqual(self.execute(self.selected(yes=False))['strategy'], 'regex-inventory')
        result = self.execute()
        self.assertEqual(result['strategy'], 'ast-inventory')
        self.assertTrue(result['canary']['used'])
        self.assertEqual(self.report()['active_release'], self.baseline['active_release'])
        self.assertNotIn(b'private source', self.path.read_bytes())

    def test_success_waits_for_operator_then_can_promote_and_rollback(self):
        for n in range(5):
            self.execute(self.selected(100 + n * 10000))
        self.assertEqual(self.report()['phase'], 'ready')
        self.assertEqual(self.report()['active_generation'], 0)
        self.assertEqual(self.execute(self.selected(60000))['strategy'], 'regex-inventory')
        active = self.canary.promote(self.actors['operator'], self.id,
                                     expected_generation=0, reason='promote-review')
        self.assertEqual(active['generation'], 1)
        self.assertEqual(self.engine.execute(self.actors['runtime'], self.task(99999))['strategy'], 'ast-inventory')
        rolled = self.engine.rollback(self.actors['operator'], self.baseline['active_release'],
                                      expected_generation=1, reason='rollback-drill')
        self.assertEqual(rolled['routes'][CONTEXT], 'regex-inventory')

    def test_quality_failure_stops_and_falls_back(self):
        self.engine._registry[(CONTEXT, 'ast-inventory')] = lambda _: []
        result = self.execute()
        self.assertEqual(result['strategy'], 'regex-inventory')
        self.assertEqual(result['canary']['reason'], 'quality_failure')
        self.assertEqual(self.report()['phase'], 'stopped')
        self.assertEqual(self.execute(self.selected(10000))['strategy'], 'regex-inventory')
        with self.assertRaises(ValueError):
            self.start()

    def test_handler_exception_is_sanitised_and_baseline_served(self):
        def broken(_):
            raise RuntimeError('private error text')
        self.engine._registry[(CONTEXT, 'ast-inventory')] = broken
        self.assertEqual(self.execute()['canary']['reason'], 'handler_error')
        self.assertNotIn(b'private error text', self.path.read_bytes())

    def test_bad_judge_stops_not_passing_reward(self):
        self.engine.judge = lambda *_: 'true'
        self.assertEqual(self.execute()['canary']['reason'], 'judge_error')
        self.assertEqual(self.report()['outcomes'], {'judge_error': 1})

    def test_latency_failure_uses_measured_duration(self):
        with patch('nerve_awim.canary_learning_v23.perf_counter', side_effect=(0, 2)):
            self.assertEqual(self.execute()['canary']['reason'], 'latency_failure')
        self.assertEqual(self.report()['latency']['max_ms'], 2000)

    def test_pending_attempt_after_restart_blocks_new_exposure(self):
        with self.engine._db() as con:
            con.execute('INSERT INTO gl_canary_outcomes VALUES(?,?,?,NULL)', (self.id, 'interrupted', 'pending'))
        self.canary = CanaryLearning(self.engine)
        self.assertEqual(self.execute()['canary']['reason'], 'pending_attempt')
        with self.assertRaises(ValueError):
            self.canary.promote(self.actors['operator'], self.id, expected_generation=0, reason='premature')

    def test_repeat_task_cannot_inflate_success_count_or_train(self):
        task = self.selected()
        self.execute(task)
        self.assertEqual(self.execute(task)['canary']['reason'], 'not_fresh_or_reserved')
        self.assertEqual(self.report()['outcomes'], {'passed': 1})
        with self.assertRaises(ValueError):
            self.engine.learn_from_task(self.actors['trainer'], task)

    def test_reserved_holdout_is_excluded(self):
        task = self.selected()
        _, digest = self.engine._task(task)
        with self.engine._db() as con:
            con.execute('INSERT INTO gl_holdout_reservations VALUES(?,?,?,?)', ('tenant', 'agent', task.task_id, digest))
        self.assertEqual(self.execute(task)['canary']['reason'], 'not_fresh_or_reserved')
        self.assertEqual(self.report()['outcomes'], {})

    def test_operator_stop_during_handler_prevents_candidate_response(self):
        original = self.engine._registry[(CONTEXT, 'ast-inventory')]
        def handler(payload):
            self.canary.stop(self.actors['operator'], self.id, reason='stop-now')
            return original(payload)
        self.engine._registry[(CONTEXT, 'ast-inventory')] = handler
        self.assertEqual(self.execute()['canary']['reason'], 'operator_stopped')

    def test_generation_change_stops_stale_canary(self):
        self.engine.activate(self.actors['operator'], self.candidate, expected_generation=0, reason='other-release')
        self.assertEqual(self.execute()['canary']['reason'], 'active_release_changed')
        self.assertEqual(self.report()['phase'], 'stopped')

    def test_role_scope_and_stale_approval(self):
        with self.assertRaises(PermissionError):
            self.canary.stop(self.actors['runtime'], self.id, reason='bad-role')
        other = self.engine.authority.issue('other', 'agent', 'runtime')
        with self.assertRaises(LookupError):
            self.canary.execute(other, self.id, self.selected())
        with self.assertRaises(ValueError):
            self.canary.start(self.actors['operator'], self.candidate,
                              expected_generation=1, reason='stale')

    def test_rejected_candidate_cannot_start(self):
        candidate = self.engine.freeze_candidate(self.actors['trainer'])
        with self.assertRaises(ValueError):
            self.canary.start(self.actors['operator'], candidate, expected_generation=0, reason='not-evaluated')

    def test_another_inflight_request_uses_baseline(self):
        observed = []
        original = self.engine._registry[(CONTEXT, 'ast-inventory')]
        def handler(payload):
            observed.append(self.execute(self.selected(10000)))
            return original(payload)
        self.engine._registry[(CONTEXT, 'ast-inventory')] = handler
        self.assertTrue(self.execute()['canary']['used'])
        self.assertEqual(observed[0]['canary']['reason'], 'pending_attempt')


if __name__ == '__main__':
    unittest.main()
