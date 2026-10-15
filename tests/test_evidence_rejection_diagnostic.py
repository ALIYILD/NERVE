import copy
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import evidence_rejection_diagnostic as diagnostic


def fixture_report():
    # Arithmetic/roster fixtures only: not simulated proof of a real experiment.
    rows = []
    for seed in diagnostic.study.SPLITS['train']:
        for scenario in diagnostic.study.SCENARIOS:
            for index, arm in enumerate(diagnostic.study.ARMS):
                trace = [{'learning_updates': index % 2, 'action_source': 'controller',
                          'sensor': None, 'estimated_gain': 0.25, 'true_gain': 0.5,
                          'goal_error': float(index + step), 'prediction_error': float(2*index),
                          'phase': 'active'} for step in range(80)]
                rows.append({'split': 'train', 'arm': arm,
                             'episode': {'seed': seed, 'scenario': scenario, 'trace': trace}})
    return {'status': 'complete', 'rows': rows}


class EvidenceRejectionDiagnosticTests(unittest.TestCase):
    def test_complete_roster_windows_pairs_and_validation_delegation(self):
        report = fixture_report()
        with patch.object(diagnostic.worker, 'validate') as validate:
            result = diagnostic.diagnose(report)
        self.assertEqual(validate.call_count, 128)
        for call, row in zip(validate.call_args_list, report['rows']):
            self.assertEqual(call.args, ({k: v for k, v in row.items() if k != 'split'},
                                         row['episode']['seed'], row['episode']['scenario'], row['arm']))
        self.assertEqual(result['training_episodes'], 128)
        self.assertEqual(result['totals']['steps'], 10240)
        self.assertEqual(result['totals']['learning_updates'], 5120)
        self.assertEqual(result['totals']['mean_absolute_gain_error'], 0.25)
        self.assertEqual(len(result['windows']), 64)
        self.assertEqual(len(result['paired_windows']), 128)
        for window in result['windows']:
            index = diagnostic.study.ARMS.index(window['arm'])
            self.assertEqual(window['summary']['mean_goal_error'], index+window['start_step']+9.5)
            self.assertEqual(window['summary']['steps'], 160)
            self.assertEqual(window['phases']['active'], window['summary'])
            self.assertIsNone(window['phases']['awaiting_approval']['mean_goal_error'])
        for pair in result['paired_windows']:
            delta = diagnostic.study.ARMS.index(pair['arm']) - diagnostic.study.ARMS.index(pair['control'])
            self.assertEqual(pair['mean_goal_error_delta'], delta)
            self.assertEqual(pair['mean_prediction_error_delta'], 2*delta)
            self.assertEqual(len(pair['paired_episodes']), 8)
            for episode in pair['paired_episodes']:
                self.assertEqual(episode['mean_goal_error_delta'], delta)
        self.assertEqual(result['next_action'], 'register_prediction_calibration_study')
        self.assertEqual(result['new_episodes'], 0)
        for key in ('validation_holdout_used', 'parameters_tuned', 'gates_changed',
                    'promotion_authorized', 'deployed', 'goal_achieved'):
            self.assertIs(result[key], False)

    def test_deterministic_immutable_no_execution_or_later_outcome_inspection(self):
        report = fixture_report()
        original = copy.deepcopy(report)
        with patch.object(diagnostic.worker, 'validate'), patch.object(
                diagnostic.worker, 'execute', side_effect=AssertionError('no new trials')):
            expected = diagnostic.diagnose(report)
            self.assertEqual(report, original)
            report['rows'].reverse()
            report['rows'] += [{'split': 'holdout'}, {'split': 'validation', 'episode': object()}]
            self.assertEqual(diagnostic.diagnose(report), expected)

    def test_missing_duplicate_unregistered_and_malformed_training_rows(self):
        for mutation in ('missing', 'duplicate', 'seed', 'bool_seed', 'scenario', 'arm', 'episode'):
            report = fixture_report()
            if mutation == 'missing': report['rows'].pop()
            elif mutation == 'duplicate': report['rows'].append(copy.deepcopy(report['rows'][0]))
            elif mutation == 'seed': report['rows'][0]['episode']['seed'] = 1
            elif mutation == 'bool_seed': report['rows'][0]['episode']['seed'] = True
            elif mutation == 'scenario': report['rows'][0]['episode']['scenario'] = []
            elif mutation == 'arm': report['rows'][0]['arm'] = 'unknown'
            else: report['rows'][0]['episode'] = None
            with self.subTest(mutation=mutation), patch.object(diagnostic.worker, 'validate'), self.assertRaises(ValueError):
                diagnostic.diagnose(report)

    def test_validation_failure_propagates(self):
        with patch.object(diagnostic.worker, 'validate', side_effect=ValueError('tampered_trace')), self.assertRaisesRegex(ValueError, 'tampered_trace'):
            diagnostic.diagnose(fixture_report())

    def test_rejects_invalid_container_and_bounds(self):
        for report in (None, {}, {'status': 'failed', 'rows': []},
                       {'status': 'complete', 'rows': None},
                       {'status': 'complete', 'rows': [None]},
                       {'status': 'complete', 'rows': [{'split': []}]},
                       {'status': 'complete', 'rows': [{'split': 'unknown'}]},
                       {'status': 'complete', 'rows': [{'split': 'holdout'}]*321}):
            with self.subTest(report=str(report)[:80]), self.assertRaises(ValueError):
                diagnostic.diagnose(report)

    def test_real_worker_validation_rejects_unvalidated_fixture(self):
        # Real validator must reject fake rows; mocked arithmetic tests above
        # cannot be mistaken for evidence of restore/plant correctness.
        with self.assertRaises(ValueError):
            diagnostic.diagnose(fixture_report())


if __name__ == '__main__':
    unittest.main()
