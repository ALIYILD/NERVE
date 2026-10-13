"""Recorded six-case evidence only; no simulator or registered stream runs."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import standard_learning_diagnostic as subject

ARTIFACT = subject.demo.ROOT/'docs/galahad/evidence/standard-learning-development-v1.json.gz'


class StandardLearningDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.report = subject._read(ARTIFACT)

    def test_real_receipt_full_validation_and_no_episode_execution(self):
        with patch.object(subject.demo, '_execute', side_effect=AssertionError('no reruns')), patch.object(subject.demo, 'run_demo', side_effect=AssertionError('no reruns')):
            result = subject.run(ARTIFACT)
        self.assertEqual(result['episodes_analyzed'], 6)
        self.assertEqual(result['recorded_steps_analyzed'], 480)
        self.assertEqual(result['new_episodes'], 0)
        self.assertEqual(len(result['source_sha256']), 23)
        self.assertFalse(result['candidate_promoted'])
        self.assertFalse(result['control_improvement_established'])

    def test_signed_identity_and_absolute_cancellation_hold_separately(self):
        result = subject.analyze(self.report)
        for case in result['cases']:
            for item in case['steps']:
                self.assertAlmostEqual(item['state_term']+item['gain_term'], item['signed_error'], places=12)
                self.assertAlmostEqual(item['absolute_error']+item['cancellation'],
                    item['absolute_state_term']+item['absolute_gain_term'], places=12)
                self.assertGreaterEqual(item['cancellation'], -1e-12)
                self.assertLessEqual(abs(item['identity_residual']), 1e-12)
        self.assertTrue(any(item['cancellation'] > 1e-8 for case in result['cases'] for item in case['steps']))

    def test_source_strata_partition_whole_episode_without_additive_mae_claim(self):
        result = subject.analyze(self.report)
        self.assertEqual(len(result['decomposition']), 18)
        for index in range(0, 18, 3):
            whole, controller, external = result['decomposition'][index:index+3]
            self.assertEqual(whole['steps'], 80)
            self.assertEqual(controller['steps']+external['steps'], 80)
            for field in ('absolute_error','state_term','gain_term','cancellation'):
                self.assertAlmostEqual(whole[field],
                    (controller[field]*controller['steps']+external[field]*external['steps'])/80)

    def test_fixed_state_action_counterfactual_zero_actions_have_no_gain_effect(self):
        result = subject.analyze(self.report)
        rows = result['fixed_state_action_gain_counterfactuals']
        self.assertEqual(len(rows), 8)
        for scenario in subject.demo.SCENARIOS:
            subset = [row for row in rows if row['scenario'] == scenario]
            self.assertEqual(sum(row['steps'] for row in subset), 80)
            for row in subset:
                if row['action_group'] == 'zero':
                    self.assertEqual(row['learned_mae'], row['nominal_mae'])
                    self.assertEqual(row['learned_minus_nominal'], 0.)
        for case in result['cases']:
            original = next(row['episode'] for row in self.report['rows']
                            if row['arm'] == case['arm'] and row['episode']['scenario'] == case['scenario'])
            recovery = next(event['step'] for event in original['recovery_events'] if event['authorised'])
            self.assertTrue(all(item['recovery_period'] == ('pre_recovery' if item['step'] < recovery else 'post_recovery')
                                for item in case['steps']))

    def test_source_pins_roster_seed_and_elapsed_tampering_rejected(self):
        for change in ('pins','rowpins','missing','duplicate','seed','elapsed','flag'):
            report = deepcopy(self.report)
            if change == 'pins': report['source_sha256'].pop(next(iter(report['source_sha256'])))
            if change == 'rowpins': report['rows'][0]['source_sha256'] = {}
            if change == 'missing': report['rows'].pop()
            if change == 'duplicate': report['rows'][1] = deepcopy(report['rows'][0])
            if change == 'seed': report['rows'][0]['episode']['seed'] = 10
            if change == 'elapsed': report['rows'][0]['elapsed_seconds'] = True
            if change == 'flag': report['heldout_outcomes_analyzed'] = 0
            with self.subTest(change=change), self.assertRaises(ValueError): subject.analyze(report)

    def test_physical_trace_independent_audit_and_screen_are_verified(self):
        for change in ('truth','audit','screen','recommendation'):
            report = deepcopy(self.report)
            if change == 'truth': report['rows'][0]['episode']['trace'][5]['true_velocity'] += .1
            if change == 'audit': report['rows'][1]['audit']['ema_applications'] += 1
            if change == 'screen': report['screen']['passed'] = True
            if change == 'recommendation': report['recommendation'] = 'register_fresh_study'
            with self.subTest(change=change), self.assertRaises(ValueError): subject.analyze(report)

    def test_arithmetic_residual_check_survives_mocked_outer_validator(self):
        for change in ('signed','absolute'):
            report = deepcopy(self.report)
            step = report['rows'][0]['episode']['trace'][2]
            if change == 'signed': step['estimated_velocity'] += .1
            else: step['prediction_error'] += .1
            with patch.object(subject, 'validate'), self.assertRaises(ValueError): subject.analyze(report)

    def test_artifact_or_source_change_during_analysis_rejected(self):
        with patch.object(subject, '_read', side_effect=[(self.raw,self.report),(self.raw+b'x',self.report)]):
            with self.assertRaisesRegex(ValueError, 'artifact_changed'): subject.run(ARTIFACT)
        with patch.object(subject, '_sources', side_effect=[{'a':'before'},{'a':'after'}]):
            with self.assertRaisesRegex(ValueError, 'source_code_changed'): subject.run(ARTIFACT)

    def test_bounded_input_and_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'fixture.gz'
            path.write_bytes(gzip.compress(b'{"a":1,"a":2}'))
            with self.assertRaisesRegex(ValueError, 'duplicate_json_key'): subject._read(path)
            path.write_bytes(gzip.compress(b' '*100))
            with patch.object(subject, 'MAX_EXPANDED', 20), self.assertRaises(ValueError): subject._read(path)
            with patch.object(subject, 'MAX_COMPRESSED', 1), self.assertRaises(ValueError): subject._read(path)

    def test_receipt_and_analysis_are_not_mutated(self):
        before = deepcopy(self.report)
        subject.analyze(self.report)
        self.assertEqual(self.report, before)


if __name__ == '__main__': unittest.main()
