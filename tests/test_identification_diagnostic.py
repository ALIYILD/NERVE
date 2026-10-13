import copy
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import identification_diagnostic as diagnostic
from nerve_awim.memory_gateway import dynamics_factorial_episode as worker


class IdentificationDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Smoke seed only. Never run the registered prospective study roster.
        cls.report = {'status': 'complete', 'rows': [
            {'split': 'train', **worker.execute(4, scenario, arm)}
            for scenario in diagnostic.study.SCENARIOS for arm in diagnostic.study.ARMS]}

    def diagnose(self, report=None):
        with patch.dict(diagnostic.study.SPLITS, {'train': (4,)}):
            return diagnostic.diagnose(self.report if report is None else report)

    def test_exhaustive_windows_phases_and_arithmetic(self):
        result = self.diagnose()
        self.assertEqual(result['training_episodes'], 12)
        self.assertEqual(result['totals']['steps'], 960)
        self.assertEqual(len(result['windows']), 48)
        row_by_arm = {(r['episode']['scenario'], r['arm']): r for r in self.report['rows']}
        for window in result['windows']:
            trace = row_by_arm[(window['scenario'], window['arm'])]['episode']['trace']
            steps = trace[window['start_step']:window['stop_step_exclusive']]
            summary = window['summary']
            self.assertEqual(summary['steps'], 20)
            self.assertEqual(summary['learning_updates'], sum(s['learning_updates'] for s in steps))
            self.assertEqual(summary['no_update_steps'], sum(s['learning_updates'] == 0 for s in steps))
            self.assertAlmostEqual(summary['mean_absolute_gain_error'], sum(abs(s['estimated_gain'] - s['true_gain']) for s in steps) / 20)
            self.assertAlmostEqual(summary['mean_goal_error'], sum(s['goal_error'] for s in steps) / 20)
            self.assertAlmostEqual(summary['mean_prediction_error'], sum(s['prediction_error'] for s in steps) / 20)
            for key in ('steps', 'learning_updates', 'no_update_steps', 'controller_steps',
                        'external_supervisor_steps', 'sensor_present_steps', 'sensor_absent_steps',
                        'sensor_active_route_steps', 'sensor_recovery_route_steps', 'sensor_accepted_steps'):
                self.assertEqual(summary[key], sum(p[key] for p in window['phases'].values()))
            self.assertEqual(summary['steps'], summary['controller_steps'] + summary['external_supervisor_steps'])
            self.assertEqual(summary['steps'], summary['sensor_present_steps'] + summary['sensor_absent_steps'])
            self.assertEqual(summary['sensor_present_steps'], summary['sensor_active_route_steps'] + summary['sensor_recovery_route_steps'])
            for phase in window['phases'].values():
                if not phase['steps']:
                    self.assertIsNone(phase['mean_goal_error'])
        self.assertEqual(result['totals']['learning_updates'], sum(r['episode']['learning_updates'] for r in self.report['rows']))
        self.assertEqual(result['totals']['steps'], sum(w['summary']['steps'] for w in result['windows']))
        self.assertEqual(result['new_episodes'], 0)
        self.assertFalse(result['promotion_authorized'])
        self.assertEqual(result['next_action'], 'register_observation_aware_adaptation_study')

    def test_does_not_mutate_or_execute_or_read_later_outcomes(self):
        report = copy.deepcopy(self.report)
        report['rows'] += [{'split': 'validation', 'unread': object()}, {'split': 'holdout'}]
        original = copy.deepcopy(self.report)
        with patch.object(worker, 'execute', side_effect=AssertionError('must not execute')):
            result = self.diagnose(report)
        self.assertEqual(result, self.diagnose())
        self.assertEqual(original, self.report)

    def test_rejects_missing_duplicate_and_unregistered_training_rows(self):
        for mutation in ('missing', 'duplicate', 'unregistered', 'bool_seed', 'bad_scenario'):
            report = copy.deepcopy(self.report)
            if mutation == 'missing': report['rows'].pop()
            elif mutation == 'duplicate': report['rows'].append(copy.deepcopy(report['rows'][0]))
            elif mutation == 'unregistered': report['rows'][0]['episode']['seed'] = 5
            elif mutation == 'bool_seed': report['rows'][0]['episode']['seed'] = True
            else: report['rows'][0]['episode']['scenario'] = []
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.diagnose(report)

    def test_rejects_trace_tampering_and_extra_row_fields(self):
        for mutation in ('goal_error', 'true_gain', 'learning_updates', 'extra'):
            report = copy.deepcopy(self.report)
            if mutation == 'extra': report['rows'][0]['extra'] = True
            else: report['rows'][0]['episode']['trace'][0][mutation] += 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.diagnose(report)

    def test_rejects_incomplete_status_and_malformed_rows(self):
        for report in (None, {}, {'status': 'failed', 'rows': []},
                       {'status': 'complete', 'rows': None},
                       {'status': 'complete', 'rows': [None]},
                       {'status': 'complete', 'rows': [{'split': 'unknown'}]},
                       {'status': 'complete', 'rows': [{'split': []}]},
                       {'status': 'complete', 'rows': [{'split': 'train'}]}):
            with self.subTest(report=report), self.assertRaises(ValueError):
                self.diagnose(report if report is not None else {})


if __name__ == '__main__':
    unittest.main()
