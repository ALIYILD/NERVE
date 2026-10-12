import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from nerve_awim.memory_gateway import policy_research_loop as loop


def row(seed, scenario, hits=3, fixed=None):
    return {'seed': seed, 'scenario': scenario, 'probe_outcomes': [True] * hits + [False] * (5-hits),
            'probe_hits': hits, 'executions': 25, 'feedback_executions': 20, 'probe_executions': 5,
            'feedback_writes': 0 if fixed else 20, 'probe_feedback_writes': 0,
            'frozen_probe_state_unchanged': True}


class PolicyResearchLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'research.sqlite'

    def test_manifest_frozen_and_new_splits(self):
        manifest = loop.protocol_manifest()
        self.assertEqual(manifest, loop.protocol_manifest())
        self.assertEqual(len(manifest['candidates']), 12)
        self.assertEqual(manifest['max_trial_calls'], 272)
        old = {s for _, seeds in loop.self_study.SPLITS for s in seeds}
        new = {s for _, seeds in loop.SPLITS for s in seeds}
        self.assertFalse(old & new)
        payload = [loop._digest(task) for _, seeds in loop.SPLITS for seed in seeds
                   for scenario in loop.SCENARIOS for task, _ in loop._cases(seed, scenario)]
        self.assertEqual(len(payload), len(set(payload)))

    def test_no_gain_stops_and_retains_baseline(self):
        calls = []
        def evaluate(seed, scenario, config, fixed):
            calls.append((seed, scenario, config, fixed))
            return row(seed, scenario, fixed=fixed)
        report = loop._run(self.path, 'no-gain', evaluate)
        self.assertEqual(report['recommendation'], 'retain_baseline')
        self.assertEqual(report['stop_reason'], 'patience_exhausted')
        self.assertEqual(len(report['cycles']), 2)
        self.assertEqual(len(report['candidate_results']), 8)
        self.assertEqual(report['trial_calls'], 188)
        self.assertEqual(len(calls), 188)
        self.assertFalse(report['promotion_authorized'])
        self.assertFalse(report['deployed'])
        self.assertEqual(len(calls), len(set(calls)))
        first_holdout = next(i for i, c in enumerate(calls) if c[0] >= 3000)
        self.assertTrue(all(c[0] >= 3000 for c in calls[first_holdout:]))

    def test_gain_is_only_review_and_frozen_before_holdout(self):
        def evaluate(seed, scenario, config, fixed):
            if seed >= 3000:
                with sqlite3.connect(self.path) as con:
                    status, report = con.execute('SELECT status,report FROM policy_research_runs_v2').fetchone()
                self.assertEqual(status, 'holdout_claimed')
                self.assertEqual(json.loads(report)['selected'], [3, 'relevance', 3])
            return row(seed, scenario, 4 if config == (3, 'relevance', 3) else 3, fixed=fixed)
        report = loop._run(self.path, 'gain', evaluate)
        self.assertEqual(report['recommendation'], 'candidate_for_review')
        self.assertEqual(report['trial_calls'], 272)
        self.assertEqual(report['holdout_scenario_deltas'], dict.fromkeys(loop.SCENARIOS, 5))
        self.assertFalse(report['model_weights_trained'])

    def test_validation_scenario_regression_rejected(self):
        def evaluate(seed, scenario, config, fixed):
            hits = 3
            if config != loop.BASELINE:
                hits = 2 if scenario == 'stationary' else 5
            return row(seed, scenario, hits, fixed=fixed)
        report = loop._run(self.path, 'scenario-regression', evaluate)
        self.assertEqual(report['selected'], list(loop.BASELINE))
        reasons = report['cycles'][0]['decisions'][1]['reasons']
        self.assertIn('baseline_validation_regression:stationary', reasons)

    def test_training_regression_rejected(self):
        def evaluate(seed, scenario, config, fixed):
            return row(seed, scenario, 3 if config == loop.BASELINE else (2 if seed < 2000 else 5), fixed=fixed)
        report = loop._run(self.path, 'training-regression', evaluate)
        self.assertEqual(report['selected'], list(loop.BASELINE))
        self.assertIn('baseline_training_regression', report['cycles'][0]['decisions'][1]['reasons'])

    def test_holdout_failure_retains_baseline_without_retuning(self):
        calls = []
        def evaluate(seed, scenario, config, fixed):
            calls.append(seed)
            return row(seed, scenario, 3 if config == loop.BASELINE else (4 if seed < 3000 else 2), fixed=fixed)
        report = loop._run(self.path, 'holdout-regression', evaluate)
        self.assertEqual(report['recommendation'], 'retain_baseline')
        self.assertNotEqual(report['selected'], list(loop.BASELINE))
        first = next(i for i, seed in enumerate(calls) if seed >= 3000)
        self.assertTrue(all(s >= 3000 for s in calls[first:]))

    def test_complete_run_cannot_replay(self):
        loop._run(self.path, 'once', lambda seed, scenario, config, fixed: row(seed, scenario, fixed=fixed))
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            loop._run(self.path, 'once', lambda *_: self.fail('replayed'))

    def test_renamed_run_cannot_reuse_protocol(self):
        loop._run(self.path, 'first', lambda seed, scenario, config, fixed: row(seed, scenario, fixed=fixed))
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            loop._run(self.path, 'renamed', lambda *_: self.fail('replayed protocol'))

    def test_changed_code_cannot_reuse_observed_dataset(self):
        manifest = loop.protocol_manifest()
        loop._claim(self.path, 'original', manifest)
        updated = {**manifest, 'protocol_sha256': 'a' * 64,
                   'evaluator_source_sha256': {'changed.py': 'b' * 64}}
        with self.assertRaisesRegex(ValueError, 'dataset already consumed'):
            loop._claim(self.path, 'changed-code', updated)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM policy_research_runs_v2').fetchone()[0], 1)

    def test_failed_run_claim_consumed_and_error_sanitized(self):
        def fail(*_):
            raise RuntimeError('private evaluator detail')
        with self.assertRaises(RuntimeError):
            loop._run(self.path, 'failed', fail)
        with sqlite3.connect(self.path) as con:
            status, report = con.execute('SELECT status,report FROM policy_research_runs_v2').fetchone()
        self.assertEqual(status, 'failed_consumed')
        self.assertNotIn('private', report)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            loop._run(self.path, 'failed', fail)

    def test_untrusted_evaluator_evidence_aborts(self):
        for mutation in ({'probe_hits': 5}, {'probe_outcomes': [1]*5},
                         {'probe_feedback_writes': 1}, {'frozen_probe_state_unchanged': False}):
            with self.subTest(mutation=mutation):
                def evaluate(seed, scenario, *_):
                    return {**row(seed, scenario), **mutation}
                with self.assertRaises(ValueError):
                    loop._run(self.path.with_name('invalid-' + str(len(str(mutation))) + '.sqlite'), 'invalid', evaluate)

    def test_trial_budget_consumes_claim(self):
        calls = []
        def evaluate(seed, scenario, config, fixed):
            calls.append(seed)
            return row(seed, scenario, fixed=fixed)
        with patch.object(loop, 'MAX_TRIAL_CALLS', 1):
            with self.assertRaisesRegex(RuntimeError, 'budget exhausted'):
                loop._run(self.path, 'budget', evaluate)
        self.assertEqual(len(calls), 1)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            loop._run(self.path, 'budget', evaluate)

    def test_concurrent_protocol_claim_has_single_winner(self):
        manifest = loop.protocol_manifest()
        def claim(index):
            try:
                loop._claim(self.path, 'parallel-' + str(index), manifest)
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            winners = list(pool.map(claim, range(2)))
        self.assertEqual(sum(winners), 1)

    def test_interrupt_consumes_claim(self):
        def interrupted(*_):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            loop._run(self.path, 'interrupted', interrupted)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            loop._run(self.path, 'different-name', lambda *_: self.fail('replay after interrupt'))

    def test_invalid_run_id_no_side_effect(self):
        with self.assertRaises(ValueError):
            loop.run_policy_research(self.path, '../unsafe')
        self.assertFalse(self.path.exists())

    def test_cycles_persisted_with_reasons(self):
        report = loop._run(self.path, 'cycles', lambda seed, scenario, config, fixed: row(seed, scenario, fixed=fixed))
        with sqlite3.connect(self.path) as con:
            cycles = [json.loads(r[0]) for r in con.execute('SELECT evidence FROM policy_research_cycles_v2 ORDER BY generation')]
            status = con.execute('SELECT status FROM policy_research_runs_v2').fetchone()[0]
        self.assertEqual(cycles, report['cycles'])
        self.assertEqual(status, 'complete')
        self.assertTrue(all(d['reasons'] for c in cycles for d in c['decisions']))

    def test_real_training_trial_no_holdout(self):
        result = loop._evaluate(1001, 'abrupt', (5, 'least_recent', 3))
        loop._validate(result, 1001, 'abrupt')
        self.assertEqual(result['feedback_writes'], 20)
        self.assertEqual(result['probe_feedback_writes'], 0)
        self.assertEqual(result['decay_half_life'], 3)


if __name__ == '__main__':
    unittest.main()
