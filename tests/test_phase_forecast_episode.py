"""Development seed 9 only; prospective study streams are never run here."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import phase_forecast_episode as worker


class PhaseForecastEpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {arm: worker.execute(9, 'drift', arm) for arm in worker.ARMS}

    def test_all_arms_validate_and_preserve_controller_predictions(self):
        schedules = set()
        for arm, row in self.rows.items():
            worker.validate(row, 9, 'drift', arm)
            schedules.add(row['control']['episode']['schedule_sha256'])
            self.assertIs(row['metrics']['controller_predictions_preserved'], True)
            self.assertIs(row['metrics']['actions_changed'], False)
            self.assertEqual(row['metrics']['missing_forecasts'], 0)
            for step, forecast in zip(row['control']['episode']['trace'], row['forecasts']):
                if step['action_source'] == 'controller':
                    self.assertEqual(forecast['velocity'], step['predicted_velocity'])
        self.assertEqual(len(schedules), 1)

    def test_original_controller_trajectory_is_unchanged(self):
        for arm, row in self.rows.items():
            original = worker.control.execute(9, 'drift', arm)
            for key in ('episode', 'planning_sequences', 'learning_evidence', 'arm'):
                self.assertEqual(row['control'][key], original[key])

    def test_projection_excludes_truth_and_external_legacy_forecast(self):
        trace = deepcopy(self.rows['frozen_h1']['control']['episode']['trace'])
        before = deepcopy(trace)
        first = worker.project(trace)
        for step in trace:
            for field in ('true_velocity', 'true_position', 'true_gain', 'prediction_error', 'goal_error'):
                step[field] = object()
            if step['action_source'] == 'external_supervisor':
                step['predicted_velocity'] = object()
            if step['sensor'] is not None:
                step['sensor']['private_field'] = object()
        self.assertEqual(worker.project(trace), first)
        self.assertEqual(worker.replay(first), self.rows['frozen_h1']['forecasts'])
        self.assertEqual(worker.project(before), first)
        accepted = next(item for item in first if item['sensor'] is not None)
        accepted['sensor']['velocity'] = 999.
        self.assertNotEqual(first, worker.project(before))

    def test_forecast_sequence_must_be_exact(self):
        for mutation in ('velocity', 'source', 'status', 'step', 'missing', 'extra'):
            row = deepcopy(self.rows['frozen_h1'])
            if mutation == 'missing': row['forecasts'].pop()
            elif mutation == 'extra': row['forecasts'][0]['true_velocity'] = 1.
            else: row['forecasts'][0][mutation] = {'velocity': 99., 'source': 'forged',
                    'status': 'forged', 'step': False}[mutation]
            with self.assertRaisesRegex(ValueError, 'routed_forecast_mismatch'):
                worker.validate(row, 9, 'drift', 'frozen_h1')

    def test_metric_forgery_and_numeric_boolean_alias_rejected(self):
        for key, value in (('legacy_mae', 99.), ('routed_mae', 99.),
                           ('controller_predictions_preserved', 1),
                           ('actions_changed', 0), ('missing_forecasts', False)):
            row = deepcopy(self.rows['frozen_h1']); row['metrics'][key] = value
            with self.assertRaisesRegex(ValueError, 'forecast_metrics_mismatch'):
                worker.validate(row, 9, 'drift', 'frozen_h1')

    def test_original_trace_validation_precedes_forecaster_replay(self):
        with patch.object(worker.control, 'validate', side_effect=ValueError('invalid original')), patch.object(worker, 'replay') as replay:
            with self.assertRaisesRegex(ValueError, 'invalid original'):
                worker.validate(self.rows['frozen_h1'], 9, 'drift', 'frozen_h1')
            replay.assert_not_called()

    def test_invalid_elapsed_and_schema_rejected(self):
        for value in (True, -1., float('nan'), float('inf')):
            row = deepcopy(self.rows['frozen_h1']); row['elapsed_seconds'] = value
            with self.assertRaisesRegex(ValueError, 'invalid_elapsed_time'):
                worker.validate(row, 9, 'drift', 'frozen_h1')
        row = deepcopy(self.rows['frozen_h1']); row['candidate_promoted'] = False
        with self.assertRaisesRegex(ValueError, 'invalid_phase_forecast_episode'):
            worker.validate(row, 9, 'drift', 'frozen_h1')

    def test_projection_roster_and_unknown_fields_rejected(self):
        projected = worker.project(self.rows['frozen_h1']['control']['episode']['trace'])
        for value in (projected[:-1], projected+[projected[0]], tuple(projected)):
            with self.assertRaisesRegex(ValueError, 'bounded_forecast_roster_required'):
                worker.replay(value)
        for change in ({'step': True}, {'step': 12}, {'true_velocity': 1.},
                       {'sensor': {'timestamp': 0, 'position': 0., 'velocity': 0., 'secret': 3}}):
            rows = deepcopy(projected); rows[1].update(change)
            with self.assertRaises(ValueError): worker.replay(rows)

    def test_external_forecast_cannot_accept_legacy_controller_value(self):
        rows = worker.project(self.rows['frozen_h1']['control']['episode']['trace'])
        external = next(item for item in rows if item['source'] == 'external_supervisor')
        external['controller_velocity'] = 1.
        with self.assertRaises(ValueError): worker.replay(rows)

    def test_missing_forecast_is_explicit_and_never_scored_as_zero(self):
        row = self.rows['frozen_h1']
        forecasts = deepcopy(row['forecasts']); forecasts[0]['velocity'] = None
        result = worker.score(row['control']['episode']['trace'], forecasts)
        self.assertEqual(result['missing_forecasts'], 1)
        self.assertIsNone(result['routed_mae'])


if __name__ == '__main__':
    unittest.main()
