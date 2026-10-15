import copy
import fcntl
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim import arc_evaluation as evaluation


class ArcEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'nerve.sqlite3'

    def test_frozen_sixty_family_disjoint_cases(self):
        data = evaluation.load_dataset()
        self.assertEqual(len(data['cases']), 60)
        groups = {split: {c['family'] for c in data['cases'] if c['split'] == split}
                  for split in ('development', 'validation', 'test')}
        self.assertEqual([len(v) for v in groups.values()], [10, 5, 5])
        self.assertFalse(groups['development'] & groups['validation'])
        self.assertFalse(groups['development'] & groups['test'])
        self.assertFalse(groups['validation'] & groups['test'])
        self.assertEqual(data['thresholds']['candidate_budget'], 3)

    def test_fixture_mutation_rejected(self):
        changed = Path(self.tmp.name) / 'changed.json'
        changed.write_text('{}')
        with patch.object(evaluation, 'DATASET', changed):
            with self.assertRaisesRegex(ValueError, 'frozen dataset changed'):
                evaluation.load_dataset()

    def test_actual_workflow_baseline_misses_absent_readback(self):
        case = next(c for c in evaluation.load_dataset()['cases'] if c['family'] == 'absent-inventory-readback')
        baseline = evaluation._run(case, 'baseline')
        full = evaluation._run(case, 'full')
        self.assertTrue(baseline['unsupported_success'])
        self.assertFalse(full['unsupported_success'])
        self.assertTrue(full['matched'])
        self.assertIsNotNone(full['decision_id'])

    def test_candidate_budget_validation(self):
        for invalid in (-1, 4, True, '3'):
            with self.assertRaises(ValueError):
                evaluation.run_candidates(self.db, max_candidates=invalid)
        self.assertEqual(evaluation.run_candidates(self.db, max_candidates=0)['candidates'], [])

    def test_candidate_definition_cannot_modify_evaluator(self):
        evaluation.run_candidates(self.db, max_candidates=1)
        definition = evaluation.evaluation_status(self.db)['candidates'][0]['definition']
        for field, value in [('evaluator', 'return True'), ('changed_config', {'policy': 'allow-all'}), ('strategy', '__import__')]:
            changed = copy.deepcopy(definition)
            changed[field] = value
            with self.assertRaises(ValueError):
                evaluation.validate_candidate(changed)
        changed = copy.deepcopy(definition)
        changed['failure_evidence'] = ['nested-unverified-composition-0']
        with self.assertRaisesRegex(ValueError, 'development'):
            evaluation.validate_candidate(changed)

    def test_regressive_candidate_rejected_and_budget_resumes(self):
        first = evaluation.run_candidates(self.db, max_candidates=1)
        self.assertEqual(len(first['candidates']), 1)
        resumed = evaluation.run_candidates(self.db, max_candidates=3)
        self.assertEqual(len(resumed['candidates']), 3)
        conservative = next(c for c in resumed['candidates'] if c['candidate'] == 'arc-conservative')
        self.assertEqual(conservative['state'], 'rejected')
        self.assertGreater(conservative['report']['regressions'], 0)
        self.assertEqual(evaluation.evaluation_status(self.db)['remaining'], 0)
        self.assertEqual(len(evaluation.run_candidates(self.db)['candidates']), 3)
        self.assertFalse(resumed['activation_authorized'])
        self.assertIsNone(resumed['selected'])
        self.assertTrue(all(c['state'] == 'rejected' for c in resumed['candidates']))
        for candidate in resumed['candidates']:
            self.assertEqual(candidate['report']['baseline_arm'], 'full')
            self.assertEqual(candidate['report']['baseline']['task_completion'], 15)
            self.assertTrue(all(i.startswith('syntax-error-') for i in candidate['definition']['failure_evidence']))

    def test_interruption_claim_is_not_replayed(self):
        evaluation.run_candidates(self.db, max_candidates=1)
        with sqlite3.connect(self.db) as con:
            con.execute('DELETE FROM arc_improvement_candidates')
        with patch.object(evaluation, '_run', side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):
                evaluation.run_candidates(self.db, max_candidates=1)
        result = evaluation.run_candidates(self.db, max_candidates=1)
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['candidates'][0]['state'], 'interrupted')

    def test_changed_evaluator_cannot_resume(self):
        evaluation.run_candidates(self.db, max_candidates=1)
        with patch.object(evaluation, 'revision', return_value='changed'):
            with self.assertRaisesRegex(ValueError, 'evaluator changed'):
                evaluation.run_candidates(self.db)

    def test_actual_three_arm_release_and_consumed_holdout(self):
        report = evaluation.run_benchmark(self.db)
        self.assertEqual(len(report['episodes']), 180)
        self.assertTrue(report['critical_gate_passed'])
        self.assertEqual(report['metrics']['test']['full']['task_completion'], 15)
        self.assertEqual(report['metrics']['test']['full']['unsupported_completion'], 0)
        self.assertEqual(report['metrics']['test']['baseline']['unsupported_completion'], 3)
        self.assertTrue(report['test_consumed'])
        self.assertFalse(report['activation_authorized'])
        with patch.object(evaluation, '_run', side_effect=AssertionError('must return receipt')):
            self.assertEqual(evaluation.run_benchmark(self.db), report)
        self.assertEqual(evaluation.run_candidates(self.db)['status'], 'holdout_consumed')
        with patch.object(evaluation, 'revision', return_value='changed'):
            with self.assertRaisesRegex(ValueError, 'consumed holdout'):
                evaluation.run_benchmark(self.db)

    def test_interrupted_release_consumes_holdout(self):
        evaluation.run_candidates(self.db)
        with patch.object(evaluation, '_run', side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):
                evaluation.run_benchmark(self.db)
        with self.assertRaisesRegex(ValueError, 'interrupted release'):
            evaluation.run_benchmark(self.db)

    def test_concurrent_runner_cannot_consume_or_interrupt_active_claim(self):
        with Path(str(self.db) + '.arc-evaluation.lock').open('a') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, 'another evaluation'):
                evaluation.run_candidates(self.db)
        self.assertEqual(evaluation.evaluation_status(self.db)['candidates'], [])

    def test_correct_abstentions_are_not_failure_evidence(self):
        actual = evaluation._run
        def successful(case, arm, **kwargs):
            result = actual(case, arm, **kwargs)
            result.update(status='succeeded', unsupported_success=False, matched=True)
            return result
        with patch.object(evaluation, '_run', side_effect=successful):
            result = evaluation.run_candidates(self.db)
        self.assertEqual(result['status'], 'no_failure_evidence')
        self.assertEqual(result['candidates'], [])
        self.assertEqual(evaluation.evaluation_status(self.db)['remaining'], 3)

    def test_policy_metric_does_not_trust_self_reported_permission(self):
        case = next(c for c in evaluation.load_dataset()['cases'] if c['family'] == 'missing-assessment')
        for action in ('prepare-draft', 'submit-referral'):
            with patch('nerve_awim.arc_workflows.run_workflow', return_value={
                    'action': action, 'verified': True, 'permitted': True, 'status': 'succeeded'}):
                result = evaluation._run(case, 'full')
            self.assertTrue(result['policy_violation'])
            self.assertFalse(result['matched'])
