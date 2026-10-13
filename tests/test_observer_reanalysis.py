"""Synthetic projection fixtures only; never execute registered plant streams."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import observer_reanalysis as subject


def inputs():
    return [{'step': step, 'action': (step % 3)-1, 'gain': .27, 'sensor': None}
            for step in range(80)]


def trace():
    return [dict(row, estimated_gain=row['gain'], action_source=(
                'controller' if row['step'] < 60 else 'external_supervisor'),
                prediction_error=2., true_velocity=3., true_gain=.9,
                true_position=999., goal_error=999.) for row in inputs()]


def report():
    return {'status': 'complete', 'rows': [
        {'split': 'train', 'arm': arm,
         'episode': {'seed': seed, 'scenario': scenario, 'trace': trace()}}
        for seed in subject.study.SPLITS['train']
        for scenario in subject.study.SCENARIOS for arm in subject.study.ARMS]}


def fake_replay(projected):
    return [{'step': row['step'], 'position': 0., 'velocity': 2.,
             'status': 'observed_action_forecast'} for row in projected]


class ObserverProjectionTests(unittest.TestCase):
    def test_projection_excludes_truth_outcomes_and_rejected_sensor(self):
        original = trace()
        original[2]['sensor'] = {'timestamp': 1, 'position': .2, 'velocity': .1,
                                  'accepted': True, 'route': 'online', 'secret': 42}
        original[3]['sensor'] = {'accepted': False, 'timestamp': 1000}
        before = deepcopy(original)
        projected = subject.project(original)
        self.assertEqual(projected[2]['sensor'], {'timestamp': 1, 'position': .2, 'velocity': .1})
        self.assertIsNone(projected[3]['sensor'])
        self.assertTrue(all(set(row) == {'step', 'action', 'gain', 'sensor'} for row in projected))
        self.assertEqual(original, before)
        projected[2]['sensor']['position'] = 10
        self.assertEqual(original, before)

    def test_known_physics_deterministic_and_no_mutation(self):
        rows = inputs(); before = deepcopy(rows)
        first = subject.replay(rows)
        self.assertEqual(first, subject.replay(rows))
        self.assertEqual(rows, before)
        position = velocity = 0.
        for row, forecast in zip(rows, first):
            velocity = .82 * velocity + row['gain'] * row['action']
            position += velocity
            self.assertAlmostEqual(forecast['velocity'], velocity)
            self.assertAlmostEqual(forecast['position'], position)
            self.assertEqual(forecast['status'], 'observed_action_forecast')

    def test_historical_sensor_allowed_but_future_and_current_rejected(self):
        rows = inputs()
        rows[2]['sensor'] = {'timestamp': 1, 'position': -.27, 'velocity': -.1}
        self.assertEqual(len(subject.replay(rows)), 80)
        for timestamp in (2, 3):
            rows[2]['sensor']['timestamp'] = timestamp
            with self.assertRaisesRegex(ValueError, 'invalid sensor step'):
                subject.replay(rows)

    def test_fixed_roster_rejects_missing_extra_or_non_list(self):
        for rows in (inputs()[:-1], inputs()+[inputs()[0]], tuple(inputs()), None):
            with self.assertRaisesRegex(ValueError, 'bounded_observation_roster_required'):
                subject.replay(rows)

    def test_projection_rejects_unknown_fields_and_step_gaps(self):
        for change in ({'step': True}, {'step': 5}, {'true_velocity': 1.}, {'sensor': {'timestamp': 0}}):
            rows = inputs(); rows[1].update(change)
            with self.assertRaises(ValueError): subject.replay(rows)

    def test_invalid_action_gain_and_sensor_numbers_rejected(self):
        for change in ({'action': None}, {'action': True}, {'gain': float('nan')},
                       {'gain': 0.}, {'sensor': {'timestamp': 0, 'position': float('inf'), 'velocity': 0.}}):
            rows = inputs(); rows[1].update(change)
            with self.assertRaises(ValueError): subject.replay(rows)


class ObserverAnalysisTests(unittest.TestCase):
    def setUp(self):
        # Development fixture IDs differ from all registered evaluation seeds.
        seeds = patch.object(subject.study, 'SPLITS', {'train': (1, 2), 'validation': (3,), 'holdout': (4,)})
        seeds.start(); self.addCleanup(seeds.stop)
        worker = patch.object(subject.study.worker, 'validate')
        self.validate = worker.start(); self.addCleanup(worker.stop)
        replay = patch.object(subject, 'replay', side_effect=fake_replay)
        self.replay = replay.start(); self.addCleanup(replay.stop)

    def test_all_eight_arms_exact_counts_and_matched_deltas(self):
        self.assertEqual(len(subject.study.ARMS), 8)
        fixture = report(); before = deepcopy(fixture)
        result = subject.analyze(fixture)
        count = 2 * len(subject.study.SCENARIOS) * 8
        self.assertEqual(result['training_episodes'], count)
        self.assertEqual(result['observed_steps'], count * 80)
        self.assertEqual(self.validate.call_count, count)
        self.assertEqual(self.replay.call_count, count)
        self.assertEqual(len(result['summaries']), len(subject.study.SCENARIOS)*8*3)
        for summary in result['summaries']:
            self.assertEqual(summary['episodes'], 2)
            self.assertEqual(summary['steps'], {'all': 160, 'controller': 120, 'external_supervisor': 40}[summary['action_source']])
            self.assertEqual(summary['legacy_mae'], 2.)
            self.assertEqual(summary['observer_mae'], 1.)
            self.assertEqual(summary['observer_minus_legacy'], -1.)
        self.assertEqual(result['new_episodes'], 0)
        for flag in ('heldout_outcomes_analyzed', 'actions_changed', 'candidate_promoted', 'model_weights_trained'):
            self.assertIs(result[flag], False)
        self.assertEqual(fixture, before)

    def test_heldout_and_validation_outcomes_are_not_touched(self):
        baseline = subject.analyze(report())
        fixture = report()
        fixture['rows'] += [{'split': 'holdout', 'episode': object()},
                            {'split': 'validation', 'episode': object()}]
        self.assertEqual(subject.analyze(fixture), baseline)

    def test_incomplete_duplicate_unregistered_and_unknown_split_rejected(self):
        for mutation in ('missing', 'duplicate', 'seed', 'split'):
            fixture = report()
            if mutation == 'missing': fixture['rows'].pop()
            if mutation == 'duplicate': fixture['rows'].append(deepcopy(fixture['rows'][0]))
            if mutation == 'seed': fixture['rows'][0]['episode']['seed'] = 900
            if mutation == 'split': fixture['rows'][0]['split'] = 'secret'
            with self.assertRaises(ValueError): subject.analyze(fixture)

    def test_worker_rejection_precedes_observer_replay(self):
        self.validate.side_effect = ValueError('invalid source trace')
        with self.assertRaisesRegex(ValueError, 'invalid source trace'): subject.analyze(report())
        self.replay.assert_not_called()

    def test_empty_stratum_and_oversized_or_unfinished_reports_rejected(self):
        fixture = report()
        for row in fixture['rows']:
            for step in row['episode']['trace']: step['action_source'] = 'controller'
        with self.assertRaisesRegex(ValueError, 'empty_registered_stratum'): subject.analyze(fixture)
        for value in ({'status': 'failed', 'rows': []}, {'status': 'complete', 'rows': [None]*321}, None):
            with self.assertRaises(ValueError): subject.analyze(value)


class ObserverReceiptTests(unittest.TestCase):
    def test_source_code_drift_during_analysis_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'report.json').write_text('{}')
            with patch.object(subject, '_sources', side_effect=[{'worker': 'before'}, {'worker': 'after'}]), patch.object(subject.study, 'validate_receipt'), patch.object(subject, 'analyze', return_value={}):
                with self.assertRaisesRegex(ValueError, 'source_code_changed'):
                    subject.run(tmp, 'claims', 'coordinator', 'journal')

    def test_full_receipt_validator_required_before_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'report.json').write_text('{}')
            with patch.object(subject.study, 'validate_receipt', side_effect=ValueError('bad receipt')) as validate, patch.object(subject, 'analyze') as analyze:
                with self.assertRaisesRegex(ValueError, 'bad receipt'):
                    subject.run(tmp, 'claims', 'coordinator', 'journal')
                validate.assert_called_once_with(tmp, 'claims', 'coordinator', 'journal')
                analyze.assert_not_called()

    def test_receipt_changes_during_validation_or_analysis_rejected(self):
        for phase in ('validation', 'analysis'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'report.json'; path.write_text('{}')
                def mutate(*args):
                    path.write_text('{"changed": true}')
                    return {}
                with patch.object(subject.study, 'validate_receipt', side_effect=mutate if phase == 'validation' else None), patch.object(subject, 'analyze', side_effect=mutate if phase == 'analysis' else None):
                    with self.assertRaisesRegex(ValueError, 'source_receipt_changed'):
                        subject.run(tmp, 'claims', 'coordinator', 'journal')

    def test_success_binds_exact_source_receipt_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = b'{ "fixture": true }\n'
            (Path(tmp)/'report.json').write_bytes(raw)
            with patch.object(subject.study, 'validate_receipt') as validate, patch.object(subject, 'analyze', return_value={'complete': True}) as analyze:
                result = subject.run(tmp, 'claims', 'coordinator', 'journal')
            self.assertEqual(result['source_receipt_sha256'], sha256(raw).hexdigest())
            analyze.assert_called_once_with({'fixture': True})
            self.assertIn('src/nerve_awim/actual_action_observer.py', result['source_sha256'])
            self.assertIn('src/nerve_awim/memory_gateway/observer_reanalysis.py', result['source_sha256'])


if __name__ == '__main__':
    unittest.main()
