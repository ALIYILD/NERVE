import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nerve_awim.memory_gateway import discount_research as study
from nerve_awim.memory_gateway import policy_research_loop as loop


def result(seed, scenario, config, fixed=None, hits=3):
    return {'seed': seed, 'scenario': scenario,
            'window': None if fixed else config[0], 'tie_break': config[1],
            'discount_half_life': config[2], 'decay_half_life': None, 'fixed_strategy': fixed,
            'feedback_outcomes': [True] * 20,
            'probe_outcomes': [True] * hits + [False] * (5 - hits),
            'probe_hits': hits, 'executions': 25, 'feedback_executions': 20,
            'probe_executions': 5, 'feedback_writes': 0 if fixed else 20,
            'probe_feedback_writes': 0, 'frozen_probe_state_unchanged': True}


class DiscountResearchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'study.sqlite'

    def run_mock(self, evaluator=result, name='discount'):
        return loop._run(self.path, name, evaluator, manifest=study.protocol_manifest(), validator=study._validate)

    def test_preregistered_grid_and_disjoint_payloads(self):
        manifest = study.protocol_manifest()
        self.assertEqual(manifest, study.protocol_manifest())
        self.assertEqual(len(manifest['candidates']), 7)
        self.assertEqual(manifest['max_trial_calls'], 272)
        self.assertEqual(manifest['candidate_fields'][2], 'discount_half_life')
        self.assertFalse({s for _, ss in study.SPLITS for s in ss} &
                         {s for _, ss in loop.SPLITS for s in ss})
        self.assertNotEqual(manifest['dataset_sha256'], loop.protocol_manifest()['dataset_sha256'])
        with self.assertRaises(ValueError):
            study._cases(3001, 'stationary')

    def test_no_gain_retains_baseline_and_stops(self):
        report = self.run_mock()
        self.assertEqual(report['selected'], list(study.BASELINE))
        self.assertEqual(report['recommendation'], 'retain_baseline')
        self.assertEqual(report['trial_calls'], 232)
        self.assertEqual(report['tool_executions'], 5800)
        self.assertEqual(len(report['candidate_results']), 7)
        self.assertEqual(len(report['cycles']), 2)
        self.assertFalse(report['promotion_authorized'])
        self.assertFalse(report['deployed'])
        self.assertEqual(len(report['holdout']['selected']), 40)

    def test_frozen_selection_and_max_budget(self):
        candidate = (10, 'relevance', 3)
        seen_holdout = False
        def evaluate(seed, scenario, config, fixed):
            nonlocal seen_holdout
            if seed >= 6000:
                seen_holdout = True
                with sqlite3.connect(self.path) as con:
                    status, raw = con.execute('SELECT status,report FROM policy_research_runs_v2').fetchone()
                self.assertEqual(status, 'holdout_claimed')
                self.assertEqual(json.loads(raw)['selected'], list(candidate))
            else:
                self.assertFalse(seen_holdout)
            return result(seed, scenario, config, fixed, 4 if config == candidate else 3)
        report = self.run_mock(evaluate)
        self.assertEqual(report['trial_calls'], 272)
        self.assertEqual(report['recommendation'], 'candidate_for_review')
        self.assertFalse(report['model_weights_trained'])

    def test_holdout_failure_is_not_retuned(self):
        def evaluate(seed, scenario, config, fixed):
            hits = 3 if config == study.BASELINE else (4 if seed < 6000 else 2)
            return result(seed, scenario, config, fixed, hits)
        report = self.run_mock(evaluate)
        self.assertEqual(report['recommendation'], 'retain_baseline')
        self.assertNotEqual(report['selected'], list(study.BASELINE))
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            self.run_mock(evaluate, name='renamed')

    def test_invalid_feedback_evidence_consumes_claim(self):
        def invalid(seed, scenario, config, fixed):
            row = result(seed, scenario, config, fixed)
            row['feedback_outcomes'][0] = 1
            return row
        with self.assertRaisesRegex(ValueError, 'invalid feedback outcomes'):
            self.run_mock(invalid)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            self.run_mock(name='second')

    def test_wrong_arm_evidence_rejected(self):
        def wrong(seed, scenario, config, fixed):
            row = result(seed, scenario, config, fixed)
            row['discount_half_life'] = 10
            return row
        with self.assertRaisesRegex(ValueError, 'does not match requested arm'):
            self.run_mock(wrong)

    def test_single_actual_training_trial(self):
        row = study._evaluate(4001, 'abrupt', (3, 'relevance', 3))
        loop._validate(row, 4001, 'abrupt')
        self.assertEqual(row['discount_half_life'], 3)
        self.assertEqual(row['feedback_writes'], 20)
        self.assertTrue(row['frozen_probe_state_unchanged'])
        self.assertEqual(len(row['feedback_outcomes']), 20)


if __name__ == '__main__':
    unittest.main()
