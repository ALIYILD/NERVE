import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import adaptation_followup as followup


def fixture():
    rows = []
    for scenario in followup.study.SCENARIOS:
        for adaptive in (False, True):
            rows.append({'split': 'validation', 'seed': 1, 'scenario': scenario,
                         'adaptive': adaptive, 'learning_updates': int(adaptive),
                         'metrics': {'active_steps': 80, 'supervisor_steps': 0,
                                     'violations': 0, 'successful_recoveries': 0,
                                     'mean_goal_error': 2. if adaptive else 1.,
                                     'mean_prediction_error': .5 if adaptive else 1.},
                         'trace': [{'step': t, 'action_source': 'controller',
                                    'goal_error': 2. if adaptive else 1.,
                                    'prediction_error': .5 if adaptive else 1.} for t in range(80)]})
    return {'rows': rows, 'recommendation': 'retain_baseline'}


class AdaptationFollowupTests(unittest.TestCase):
    def test_exhaustive_decomposition_preserves_aggregate_rejection(self):
        with patch.object(followup.study.episode, 'validate'):
            result = followup.diagnose(fixture())
        self.assertEqual(result['aggregate_objective_mismatch_regimes'], ['stationary', 'drift'])
        self.assertEqual(result['matched_steps'], 160)
        self.assertEqual(sum(g['matched_steps'] for g in result['groups']), 160)
        self.assertEqual(sum(g['goal_mean_delta_contribution'] for g in result['groups']), 2.)
        self.assertEqual(sum(g['prediction_mean_delta_contribution'] for g in result['groups']), -1.)
        self.assertFalse(result['comparison']['passed'])
        self.assertFalse(result['candidate_selected'])
        self.assertEqual(result['new_plant_episodes'], 0)

    def test_holdout_is_not_diagnostic_input(self):
        report = fixture()
        report['rows'].append({'split': 'holdout', 'unreadable': object()})
        with patch.object(followup.study.episode, 'validate'):
            self.assertEqual(followup.diagnose(report)['validation_episodes_inspected'], 4)

    def test_missing_pair_and_invalid_trace_rejected(self):
        report = fixture()
        report['rows'].pop()
        with self.assertRaises(ValueError): followup.diagnose(report)
        with patch.object(followup.study.episode, 'validate', side_effect=ValueError('invalid_trace')):
            with self.assertRaisesRegex(ValueError, 'invalid_trace'): followup.diagnose(fixture())

    def test_claim_precedes_diagnosis_receipt_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root, claims = Path(temp) / 'run', Path(temp) / 'claims.sqlite'
            original = followup.diagnose
            def checked(report):
                with sqlite3.connect(claims) as db:
                    self.assertIn(db.execute('SELECT status FROM adaptation_followups').fetchone()[0], ('claimed', 'complete'))
                return original(report)
            with patch.object(followup, '_read_verified', return_value=fixture()), patch.object(followup.study.episode, 'validate'), patch.object(followup, 'diagnose', side_effect=checked):
                followup.run_followup(root, 'predecessor', 'source_claims', claims)
                self.assertTrue(followup.validate_receipt(root, 'predecessor', 'source_claims', claims))
                with self.assertRaisesRegex(ValueError, 'already_consumed'):
                    followup.run_followup(Path(temp) / 'renamed', 'predecessor', 'source_claims', claims)
                stored = json.loads((root / 'report.json').read_text())
                stored['groups'][0]['matched_steps'] += 1
                (root / 'report.json').write_text(json.dumps(stored))
                with self.assertRaisesRegex(ValueError, 'invalid_adaptation_followup_receipt'):
                    followup.validate_receipt(root, 'predecessor', 'source_claims', claims)

    def test_failed_node_remains_consumed(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(followup, '_read_verified', return_value=fixture()), patch.object(followup, 'diagnose', side_effect=RuntimeError('fixture')):
            claims = Path(temp) / 'claims.sqlite'
            with self.assertRaises(RuntimeError):
                followup.run_followup(Path(temp) / 'run', 'predecessor', 'source_claims', claims)
            with sqlite3.connect(claims) as db:
                self.assertEqual(db.execute('SELECT status FROM adaptation_followups').fetchone()[0], 'failed_consumed')
            with self.assertRaisesRegex(ValueError, 'already_consumed'):
                followup.run_followup(Path(temp) / 'renamed', 'predecessor', 'source_claims', claims)

    def test_changed_predecessor_consumes_node(self):
        changed = fixture()
        changed['recommendation'] = 'changed'
        with tempfile.TemporaryDirectory() as temp, patch.object(followup, '_read_verified', side_effect=[fixture(), changed]), patch.object(followup.study.episode, 'validate'):
            with self.assertRaisesRegex(ValueError, 'predecessor_changed'):
                followup.run_followup(Path(temp) / 'run', 'predecessor', 'source_claims', Path(temp) / 'claims.sqlite')

    def test_unverified_predecessor_never_runs_diagnosis(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(followup.study, 'validate_receipt', side_effect=ValueError('bad_receipt')), patch.object(followup, 'diagnose') as diagnosis:
            (Path(temp) / 'report.json').write_text(json.dumps(fixture()))
            with self.assertRaisesRegex(ValueError, 'bad_receipt'):
                followup.run_followup(Path(temp) / 'run', temp, 'source_claims', Path(temp) / 'claims.sqlite')
            diagnosis.assert_not_called()

    def test_snapshot_mutation_during_validation_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            path.write_text(json.dumps(fixture()))
            def mutate(*args):
                path.write_text('{}')
            with patch.object(followup.study, 'validate_receipt', side_effect=mutate):
                with self.assertRaisesRegex(ValueError, 'predecessor_changed_during_validation'):
                    followup._read_verified(temp, 'claims')
