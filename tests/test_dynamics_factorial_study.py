import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import dynamics_factorial_study as study


def fixture(seed, scenario, arm, timeout=30):
    adaptive = arm.startswith('adaptive')
    error = .7 if arm == 'adaptive_consistent_h3' else .9 if adaptive else 1.
    return {'arm': arm, 'elapsed_seconds': .1, 'planning_sequences': 2160 if arm.endswith('h3') else 0,
            'episode': {'seed': seed, 'scenario': scenario, 'adaptive': adaptive,
                        'learning_updates': int(adaptive), 'metrics': {
                            'active_steps': 80, 'supervisor_steps': 0, 'violations': 0,
                            'successful_recoveries': 0, 'mean_goal_error': error,
                            'mean_prediction_error': .1}}}


class DynamicsFactorialStudyTests(unittest.TestCase):
    def setUp(self):
        for target, name, kwargs in ((study, '_verified_predecessor', {'return_value': 'fixture'}),
                                      (study.worker, 'validate', {})):
            mock = patch.object(target, name, **kwargs)
            mock.start(); self.addCleanup(mock.stop)

    def test_manifest_fresh_disjoint_and_bounded(self):
        p = study.manifest()
        values = [set(v) for v in p['splits'].values()]
        self.assertEqual(sum(map(len, values)), len(set.union(*values)))
        self.assertEqual(p['max_plant_steps'], p['max_episodes']*80)
        self.assertFalse(p['promotion_authorized'])
        original = study._dataset(p)
        p['arms'] = ['renamed']
        p['protocol'] = 'renamed'
        self.assertEqual(original, study._dataset(p))

    def test_train_selection_and_matched_controls(self):
        rows = [fixture(1, scenario, arm) for scenario in study.SCENARIOS for arm in study.ARMS]
        self.assertEqual(study.select(rows)['candidate'], 'adaptive_consistent_h3')
        for row in rows:
            if row['arm'] == 'frozen_h3': row['episode']['metrics']['mean_goal_error'] = .6
        self.assertFalse(study.compare(rows, 'adaptive_consistent_h3')['passed'])
        with self.assertRaises(ValueError): study.select(rows[:-1])

    def test_actual_claim_selection_freeze_and_full_graph(self):
        with tempfile.TemporaryDirectory() as temp:
            root, claims = Path(temp)/'run', Path(temp)/'claims.sqlite'
            def execute(seed, scenario, arm, timeout):
                self.assertGreater(timeout, 0)
                self.assertLessEqual(timeout, 30)
                with sqlite3.connect(root/'ledger.sqlite') as db:
                    self.assertEqual(db.execute('SELECT status FROM trials ORDER BY ordinal DESC LIMIT 1').fetchone()[0], 'claimed')
                    if seed >= 36001:
                        selection = json.loads(db.execute('SELECT evidence FROM selection').fetchone()[0])
                        self.assertEqual(selection['candidate'], 'adaptive_consistent_h3')
                return fixture(seed, scenario, arm)
            result = study._run(root, claims, (), execute)
            self.assertEqual(result['episodes'], 240)
            self.assertTrue(result['holdout_consumed'])
            self.assertEqual(result['recommendation'], 'candidate_for_review')
            self.assertTrue(study.validate_receipt(root, claims, ()))
            result['rows'][0]['elapsed_seconds'] = 99
            (root/'report.json').write_text(json.dumps(result))
            with self.assertRaises(ValueError): study.validate_receipt(root, claims, ())
            with self.assertRaisesRegex(ValueError, 'already_consumed'):
                study._run(Path(temp)/'renamed', claims, (), execute)

    def test_validation_rejection_does_not_try_runner_up_or_holdout(self):
        def reject(seed, scenario, arm, timeout):
            self.assertLess(seed, 37001)
            row = fixture(seed, scenario, arm)
            if seed >= 36001 and arm.startswith('adaptive'):
                self.assertEqual(arm, 'adaptive_consistent_h3')
                row['episode']['metrics']['mean_goal_error'] = 2.
            return row
        with tempfile.TemporaryDirectory() as temp:
            result = study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), reject)
            self.assertEqual(result['episodes'], 144)
            self.assertFalse(result['holdout_consumed'])
            self.assertEqual(result['recommendation'], 'retain_baseline')

    def test_no_training_gain_stops_after_96(self):
        def reject(seed, scenario, arm, timeout):
            row = fixture(seed, scenario, arm)
            row['episode']['metrics']['mean_goal_error'] = 1.
            return row
        with tempfile.TemporaryDirectory() as temp:
            result = study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), reject)
            self.assertEqual(result['episodes'], 96)
            self.assertIsNone(result['selection']['candidate'])

    def test_child_failure_consumes_trial_and_study(self):
        with tempfile.TemporaryDirectory() as temp:
            root, claims = Path(temp)/'run', Path(temp)/'claims.sqlite'
            def fail(*args): raise RuntimeError('child_failed')
            with self.assertRaises(RuntimeError): study._run(root, claims, (), fail)
            with sqlite3.connect(root/'ledger.sqlite') as db:
                self.assertEqual(db.execute('SELECT status FROM trials').fetchone()[0], 'failed_consumed')
                self.assertEqual(db.execute('SELECT status FROM state').fetchone()[0], 'failed_consumed')
            with self.assertRaisesRegex(ValueError, 'already_consumed'):
                study._run(Path(temp)/'other', claims, (), fail)

    def test_budget_and_source_drift_stop_before_child(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(study.time, 'monotonic', side_effect=[0, 901]):
            with self.assertRaisesRegex(RuntimeError, 'budget_exhausted'):
                study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), lambda *args: self.fail('no child'))
        with tempfile.TemporaryDirectory() as temp, patch.object(study, '_sources', side_effect=[{'a':1}, {'a':2}]):
            with self.assertRaisesRegex(ValueError, 'source_drift'):
                study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), lambda *args: self.fail('no child'))
