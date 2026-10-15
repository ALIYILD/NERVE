import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import online_adaptation_study as study


def fixture(seed, scenario, arm):
    hits = 17 if arm == 'candidate' else 16
    count = 0 if arm.startswith('fixed_') else 1
    return {'seed': seed, 'scenario': scenario, 'arm': arm,
        'outcomes': [True]*hits+[False]*(32-hits), 'hits': hits, 'executions': 32,
        'feedback_writes': count*32, 'episode_feedback_writes': [count]*32,
        'payload_sha256': [study._digest(task) for task, _ in study._cases(seed, scenario)]}


class OnlineAdaptationTests(unittest.TestCase):
    def test_manifest_fixed_fresh_budget(self):
        manifest = study.protocol_manifest()
        self.assertEqual(manifest['seeds'], list(range(7001, 7017)))
        self.assertEqual(manifest['max_tool_executions'], 8192)
        self.assertEqual(manifest['max_trial_calls'], 256)
        self.assertEqual(manifest['execution_unit'], 'two-stage pipeline episode')
        self.assertEqual(manifest['pipeline_episodes'], 8192)
        self.assertEqual(manifest['primitive_tool_invocations'], 16384)
        self.assertEqual(manifest['candidate']['discount_half_life'], 1)
        self.assertIsNone(manifest['baseline']['discount_half_life'])
        self.assertEqual(manifest, study.protocol_manifest())
        self.assertIn('online_adaptation_study.py', manifest['source_sha256'])
        self.assertNotIn('holdout', manifest)

    def test_labels_not_agent_input(self):
        for task, truth in study._cases(6999, 'recurrent'):
            self.assertEqual(set(task), {'document'})
            self.assertEqual(set(json.loads(task['document'])), {'email'})
            self.assertIs(type(truth), bool)
            self.assertNotIn('6999', task['document'])

    def test_actual_trial_only_fixture_seed(self):
        row = study._trial(6999, 'recurrent', 'candidate')
        study._validate(row, 6999, 'recurrent', 'candidate')
        self.assertEqual(row['executions'], 32)
        self.assertEqual(row['feedback_writes'], 32)
        self.assertEqual(set(row['strategies']), {'lower-only', 'trim-lower'})

    def test_fixed_control_writes_no_feedback(self):
        row = study._trial(6999, 'stationary', 'fixed_lower')
        study._validate(row, 6999, 'stationary', 'fixed_lower')
        self.assertEqual(row['feedback_writes'], 0)
        self.assertEqual(set(row['strategies']), {'lower-only'})

    def test_mock_orchestration_full_budget_no_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'runs.sqlite'
            report = study._run(path, 'mock', fixture)
            self.assertEqual(report['tool_executions'], 8192)
            self.assertEqual(report['trial_calls'], 256)
            self.assertEqual(report['pipeline_episodes'], 8192)
            self.assertEqual(report['primitive_tool_invocations'], 16384)
            self.assertEqual(report['tasks_per_arm'], 2048)
            self.assertEqual(report['recommendation'], 'candidate_for_review')
            self.assertFalse(report['promotion_authorized'])
            self.assertFalse(report['deployed'])
            self.assertFalse(report['model_weights_trained'])
            with sqlite3.connect(path) as con:
                self.assertEqual(con.execute('SELECT status FROM policy_research_runs_v2').fetchone()[0], 'complete')
            with self.assertRaisesRegex(ValueError, 'consumed'):
                study._run(path, 'renamed', fixture)

    def test_scenario_loss_blocks_review_even_total_gain(self):
        def regression(seed, scenario, arm):
            row = fixture(seed, scenario, arm)
            if arm == 'candidate' and scenario == 'stationary':
                row['outcomes'] = [True]*15+[False]*17
                row['hits'] = 15
            return row
        with tempfile.TemporaryDirectory() as tmp:
            report = study._run(Path(tmp)/'runs.sqlite', 'mock', regression)
            self.assertGreater(sum(report['scenario_deltas'].values()), 0)
            self.assertEqual(report['recommendation'], 'retain_baseline')

    def test_no_gain_retains_baseline(self):
        def equal(seed, scenario, arm):
            row = fixture(seed, scenario, arm)
            row['outcomes'] = [True]*16+[False]*16
            row['hits'] = 16
            return row
        with tempfile.TemporaryDirectory() as tmp:
            report = study._run(Path(tmp)/'runs.sqlite', 'mock', equal)
            self.assertEqual(report['recommendation'], 'retain_baseline')

    def test_aborted_claim_remains_consumed(self):
        def aborted(*args):
            raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'runs.sqlite'
            with self.assertRaises(KeyboardInterrupt):
                study._run(path, 'aborted', aborted)
            with sqlite3.connect(path) as con:
                status, report = con.execute('SELECT status,report FROM policy_research_runs_v2').fetchone()
            self.assertEqual(status, 'failed_consumed')
            self.assertEqual(json.loads(report)['trial_calls'], 1)
            with self.assertRaisesRegex(ValueError, 'consumed'):
                study._run(path, 'another', fixture)

    def test_source_change_cannot_reuse_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'runs.sqlite'
            manifest = study.protocol_manifest()
            study._claim(path, 'first', manifest)
            changed = {**manifest, 'protocol_sha256': 'changed-code'}
            with patch.object(study, 'protocol_manifest', return_value=changed):
                with self.assertRaisesRegex(ValueError, 'consumed'):
                    study._run(path, 'second', fixture)

    def test_result_validation_fail_closed(self):
        good = fixture(6999, 'mixed', 'candidate')
        mutations = ({'executions': 31}, {'feedback_writes': 31}, {'hits': True},
            {'outcomes': [1]*32}, {'episode_feedback_writes': [True]*32},
            {'payload_sha256': ['wrong']*32}, {'seed': 7000})
        for change in mutations:
            with self.subTest(change=change):
                row = copy.deepcopy(good)
                row.update(change)
                with self.assertRaises(ValueError):
                    study._validate(row, 6999, 'mixed', 'candidate')

    def test_invalid_run_and_arm(self):
        with self.assertRaises(ValueError):
            study._trial(6999, 'mixed', 'tuned')
        with self.assertRaises(ValueError):
            study._run('/unused.sqlite', '../invalid', fixture)


if __name__ == '__main__':
    unittest.main()
