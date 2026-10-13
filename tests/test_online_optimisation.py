from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import online_optimisation as study


def fixture(seed, scenario, config, fixed):
    cases = study.online._cases(seed, scenario)
    desired = 16 if tuple(config) == study.BASELINE else 24 if config[0] == 3 and config[2] == 3 else 20
    strategies = [fixed or ('trim-lower' if (trim if i < desired else not trim) else 'lower-only')
                  for i, (_, trim) in enumerate(cases)]
    outcomes = [(strategy == 'trim-lower') == trim for strategy, (_, trim) in zip(strategies, cases)]
    writes = 0 if fixed else 1
    return {'seed': seed, 'scenario': scenario, 'arm': 'configured',
            'policy_config': asdict(study.online.OnlinePolicy(*config)), 'fixed': fixed,
            'outcomes': outcomes, 'strategies': strategies, 'hits': sum(outcomes),
            'executions': 32, 'feedback_writes': writes*32,
            'episode_feedback_writes': [writes]*32, 'wall_ms': 0,
            'payload_sha256': [study.online._digest(task) for task, _ in cases]}


class OnlineOptimisationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'study.sqlite'

    def test_protocol_fresh_disjoint_bounded(self):
        manifest = study.protocol_manifest()
        self.assertEqual(manifest, study.protocol_manifest())
        sets = [set(seeds) for _, seeds in study.SPLITS]
        self.assertFalse(sets[0] & sets[1] or sets[1] & sets[2] or sets[0] & sets[2])
        self.assertTrue(all(min(s) > 21001 for s in sets))
        self.assertEqual(len(study.CANDIDATES), 7)
        self.assertEqual(manifest['max_trial_calls']*32, 11264)
        self.assertFalse(manifest['promotion_authorized'])

    def test_selected_once_before_holdout_and_exact_accounting(self):
        calls = []
        def execute(seed, scenario, config, fixed):
            with sqlite3.connect(self.path) as db:
                self.assertEqual(db.execute('SELECT status FROM policy_research_trials_v2 ORDER BY trial_index DESC LIMIT 1').fetchone()[0], 'pending')
                if seed >= 24001:
                    status, selection = db.execute('SELECT status,report FROM policy_research_runs_v2').fetchone()
                    self.assertEqual(status, 'holdout_claimed')
                    self.assertEqual(json.loads(selection)['selected'], [3, 'relevance', 3])
            calls.append(seed)
            return fixture(seed, scenario, config, fixed)
        report = study._run(self.path, 'selection', execute)
        self.assertEqual(report['selected'], [3, 'relevance', 3])
        self.assertEqual(report['recommendation'], 'candidate_for_review')
        self.assertEqual(report['trial_calls'], 352)
        self.assertEqual(report['pipeline_episodes'], 11264)
        self.assertEqual(report['primitive_tool_invocations'], 22528)
        first = next(i for i, seed in enumerate(calls) if seed >= 24001)
        self.assertTrue(all(seed >= 24001 for seed in calls[first:]))
        with self.assertRaisesRegex(ValueError, 'consumed'):
            study._run(self.path, 'renamed', fixture)

    def test_holdout_regression_no_retuning(self):
        def execute(seed, scenario, config, fixed):
            row = fixture(seed, scenario, config, fixed)
            if seed >= 24001 and scenario == 'mixed' and tuple(config) != study.BASELINE and fixed is None:
                return fixture(seed, scenario, study.BASELINE, None) | {'policy_config': row['policy_config']}
            return row
        # Equal mixed score is allowed; a strict regression must retain baseline.
        def regress(*args):
            row = execute(*args)
            if args[0] >= 24001 and args[1] == 'mixed' and tuple(args[2]) != study.BASELINE and args[3] is None:
                row['strategies'][0] = 'trim-lower' if row['strategies'][0] == 'lower-only' else 'lower-only'
                row['outcomes'][0] = not row['outcomes'][0]
                row['hits'] = sum(row['outcomes'])
            return row
        report = study._run(self.path, 'regression', regress)
        self.assertEqual(report['selected'], [3, 'relevance', 3])
        self.assertEqual(report['recommendation'], 'retain_baseline')
        self.assertLess(report['holdout_scenario_deltas']['mixed'], 0)

    def test_source_drift_consumes_claim_without_success(self):
        with patch.object(study, '_check_sources', side_effect=[None, ValueError('drift')]):
            with self.assertRaises(ValueError):
                study._run(self.path, 'drift', fixture)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT status FROM policy_research_runs_v2').fetchone()[0], 'failed_consumed')
            self.assertEqual(db.execute('SELECT status FROM policy_research_trials_v2').fetchone()[0], 'failed_consumed')

    def test_applied_config_and_false_reward_rejected(self):
        row = fixture(22001, 'mixed', study.BASELINE, None)
        row['policy_config']['window'] = 5
        with self.assertRaises(ValueError):
            study._validate(row, 22001, 'mixed', config=study.BASELINE)
        row = fixture(22001, 'mixed', study.BASELINE, None)
        row['outcomes'][0] = not row['outcomes'][0]
        row['hits'] = sum(row['outcomes'])
        with self.assertRaises(ValueError):
            study._validate(row, 22001, 'mixed', config=study.BASELINE)

    def test_real_registered_child(self):
        row = study._execute(21999, 'mixed', (5, 'relevance', 3), None)
        study._validate(row, 21999, 'mixed', config=(5, 'relevance', 3))
        self.assertEqual(row['executions'], 32)


if __name__ == '__main__':
    unittest.main()
