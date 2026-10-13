import copy
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway.recovery_adaptation import (
    ISSUER, STEPS, SyntheticVerifier, episode, validate,
)


class RecoveryAdaptationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {(seed, scenario, adaptive): episode(seed, scenario, adaptive)
                    for seed in (1, 2) for scenario in ('stationary', 'drift')
                    for adaptive in (False, True)}

    def test_matched_exogenous_and_complete_physics(self):
        for seed in (1, 2):
            for scenario in ('stationary', 'drift'):
                a, b = (self.rows[seed, scenario, flag] for flag in (False, True))
                self.assertEqual(a['schedule_sha256'], b['schedule_sha256'])
                self.assertEqual([x['exogenous'] for x in a['trace']],
                                 [x['exogenous'] for x in b['trace']])
                for row in (a, b):
                    self.assertEqual(len(row['trace']), STEPS)
                    self.assertEqual(row['metrics']['active_steps'] + row['metrics']['supervisor_steps'], STEPS)
                    self.assertGreater(row['metrics']['supervisor_steps'], 0)
                    self.assertGreater(row['metrics']['successful_recoveries'], 0)
                    self.assertIsNone(validate(row, seed, scenario, row['adaptive']))

    def test_real_updates_and_retention_across_recovery(self):
        for (seed, scenario, adaptive), row in self.rows.items():
            if adaptive:
                self.assertGreater(row['learning_updates'], 0)
                self.assertNotEqual(row['final_gain'], row['initial_gain'])
            else:
                self.assertEqual(row['learning_updates'], 0)
                self.assertEqual(row['final_gain'], row['initial_gain'])
            for event in row['recovery_events']:
                self.assertTrue(event['authorised'])
                self.assertEqual(event['gain_before'], event['gain_after'])

    def test_prospective_predictions_all_steps(self):
        for row in self.rows.values():
            for item in row['trace']:
                self.assertEqual(item['predicted_velocity'],
                                 .82 * item['estimated_velocity'] + item['estimated_gain'] * item['action'])
                self.assertEqual(item['prediction_error'], abs(item['predicted_velocity'] - item['true_velocity']))
                self.assertEqual(item['goal_error'], abs(item['true_position'] - 1.2))
                self.assertEqual(item['history_after'] - item['history_before'],
                                 int(item['action_source'] == 'controller'))
                if item['action_source'] == 'external_supervisor':
                    self.assertEqual(item['action'], 0)
                    self.assertEqual(item['history_after'], item['history_before'])

    def test_approval_is_required(self):
        # Counterfactual removes host authentication without changing observations.
        with patch.object(SyntheticVerifier, 'verify', return_value=None):
            row = episode(1, 'drift', True)
        self.assertEqual(row['metrics']['successful_recoveries'], 0)
        self.assertLess(row['metrics']['active_steps'], self.rows[1, 'drift', True]['metrics']['active_steps'])
        self.assertTrue(all(not e['authorised'] for e in row['recovery_events']))

    def test_synthetic_verifier_denies_other_tokens(self):
        self.assertIsNone(SyntheticVerifier().verify('agent-approval', 1))
        self.assertEqual(SyntheticVerifier().verify('synthetic-host-approval', 1).issuer, ISSUER)

    def test_falsified_summaries_and_trace_rejected(self):
        original = self.rows[1, 'drift', True]
        for key in ('active_steps', 'supervisor_steps', 'violations',
                    'mean_goal_error', 'mean_prediction_error', 'successful_recoveries'):
            bad = copy.deepcopy(original)
            bad['metrics'][key] += 1
            with self.assertRaises(ValueError):
                validate(bad, 1, 'drift', True)
        for key in ('true_velocity', 'predicted_velocity', 'goal_error', 'history_after'):
            bad = copy.deepcopy(original)
            bad['trace'][5][key] += 1
            with self.assertRaises(ValueError):
                validate(bad, 1, 'drift', True)
        bad = copy.deepcopy(original)
        bad['trace'][1]['sensor']['position'] += 1
        with self.assertRaises(ValueError):
            validate(bad, 1, 'drift', True)

    def test_strict_inputs_schema_and_nonfinite(self):
        for values in ((True, 'drift', True), (-1, 'drift', True),
                       (1, 'other', True), (1, 'drift', 1)):
            with self.assertRaises(ValueError):
                episode(*values)
        for key, value in (('seed', True), ('adaptive', 1), ('promoted', True),
                           ('extra', None), ('final_gain', float('nan'))):
            bad = copy.deepcopy(self.rows[1, 'drift', True])
            bad[key] = value
            with self.assertRaises(ValueError):
                validate(bad, 1, 'drift', True)

    def test_no_credentials_in_evidence(self):
        import json
        serialized = json.dumps(list(self.rows.values()))
        for marker in ('signature', 'synthetic-host-approval', 'secret', 'nonce'):
            self.assertNotIn(marker, serialized)


if __name__ == '__main__':
    unittest.main()
