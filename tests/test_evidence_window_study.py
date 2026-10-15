import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import evidence_window_study as study


def fixture(seed, scenario, arm, timeout=30):
    adaptive = not arm.startswith('frozen')
    error = .7 if arm == 'evidence_forget_h3' else .9 if arm.startswith('evidence') else 1.
    return {'arm': arm, 'elapsed_seconds': .1, 'planning_sequences': 2160 if arm.endswith('h3') else 0,
            'episode': {'seed': seed, 'scenario': scenario, 'adaptive': adaptive,
                        'learning_updates': int(adaptive), 'metrics': {
                            'active_steps': 80, 'supervisor_steps': 0, 'violations': 0,
                            'successful_recoveries': 0, 'mean_goal_error': error,
                            'mean_prediction_error': .1}}}


class EvidenceWindowStudyTests(unittest.TestCase):
    def setUp(self):
        for target, name, kwargs in ((study, 'SPLITS', {'new': {'train': tuple(range(1,9)), 'validation': tuple(range(11,19)), 'holdout': tuple(range(21,37))}}),
                                      (study, '_verified_predecessor', {'return_value': 'fixture'}),
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
        self.assertEqual(study.select(rows)['candidate'], 'evidence_forget_h3')
        for row in rows:
            if row['arm'] == 'frozen_h3': row['episode']['metrics']['mean_goal_error'] = .6
        self.assertFalse(study.compare(rows, 'evidence_forget_h3')['passed'])
        with self.assertRaises(ValueError): study.select(rows[:-1])

    def test_actual_claim_selection_freeze_and_full_graph(self):
        with tempfile.TemporaryDirectory() as temp:
            root, claims = Path(temp)/'run', Path(temp)/'claims.sqlite'
            def execute(seed, scenario, arm, timeout):
                self.assertGreater(timeout, 0)
                self.assertLessEqual(timeout, 30)
                with sqlite3.connect(root/'ledger.sqlite') as db:
                    self.assertEqual(db.execute('SELECT status FROM trials ORDER BY ordinal DESC LIMIT 1').fetchone()[0], 'claimed')
                    if seed >= 11:
                        selection = json.loads(db.execute('SELECT evidence FROM selection').fetchone()[0])
                        self.assertEqual(selection['candidate'], 'evidence_forget_h3')
                return fixture(seed, scenario, arm)
            result = study._run(root, claims, (), execute)
            self.assertEqual(result['episodes'], 320)
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
            self.assertLess(seed, 21)
            row = fixture(seed, scenario, arm)
            if seed >= 11 and arm.startswith('evidence'):
                self.assertEqual(arm, 'evidence_forget_h3')
                row['episode']['metrics']['mean_goal_error'] = 2.
            return row
        with tempfile.TemporaryDirectory() as temp:
            result = study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), reject)
            self.assertEqual(result['episodes'], 192)
            self.assertFalse(result['holdout_consumed'])
            self.assertEqual(result['recommendation'], 'retain_baseline')

    def test_no_training_gain_stops_after_128(self):
        def reject(seed, scenario, arm, timeout):
            row = fixture(seed, scenario, arm)
            row['episode']['metrics']['mean_goal_error'] = 1.
            return row
        with tempfile.TemporaryDirectory() as temp:
            result = study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), reject)
            self.assertEqual(result['episodes'], 128)
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
        with tempfile.TemporaryDirectory() as temp, patch.object(study.time, 'monotonic', side_effect=[0, 1201]):
            with self.assertRaisesRegex(RuntimeError, 'budget_exhausted'):
                study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), lambda *args: self.fail('no child'))
        with tempfile.TemporaryDirectory() as temp, patch.object(study, '_sources', side_effect=[{'a':1}, {'a':2}]):
            with self.assertRaisesRegex(ValueError, 'source_drift'):
                study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), lambda *args: self.fail('no child'))

    def test_matched_adaptive_control_is_a_real_comparator(self):
        rows = [fixture(1, scenario, arm) for scenario in study.SCENARIOS for arm in study.ARMS]
        self.assertEqual(study.controls('evidence_forget_h1'), ('frozen_h1', 'adaptive_consistent_h1'))
        self.assertEqual(study.controls('evidence_forget_h3'), ('frozen_h1', 'frozen_h3', 'adaptive_consistent_h3'))
        for row in rows:
            if row['arm'] == 'adaptive_consistent_h3':
                row['episode']['metrics']['mean_goal_error'] = .6
        self.assertFalse(study.compare(rows, 'evidence_forget_h3')['passed'])

    def test_journal_and_roster_cannot_be_omitted_or_relabelled(self):
        with tempfile.TemporaryDirectory() as temp:
            root, claims = Path(temp)/'run', Path(temp)/'claims.sqlite'
            study._run(root, claims, (), fixture)
            with sqlite3.connect(root/'ledger.sqlite') as db:
                db.execute("UPDATE trials SET arm='frozen_h1' WHERE ordinal=2")
            with self.assertRaises(ValueError): study.validate_receipt(root, claims, ())


class PredecessorVerificationTests(unittest.TestCase):
    def test_complete_graph_required_and_journal_digest_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            paths = {key: str(root/key) for key in study.supervisor.PATH_KEYS}
            pins = {'fixture': 'source-digest'}
            protocol = {'version': 'research-supervisor-v1', 'paths': paths,
                        'nodes': study.supervisor.NODES, 'max_nodes': 4,
                        'source_sha256': pins, 'promotion_authorized': False}
            completed = [{'node': node, 'status': 'complete', 'origin': 'adopted',
                          'artifact_sha256': node+'-digest'} for node in study.supervisor.NODES]
            report = {'status': 'new_registered_experiment_required', 'protocol': protocol,
                      'completed_nodes': completed, 'automatic_retry': False, 'deployed': False,
                      'model_weights_trained': False, 'goal_achieved': False,
                      'next_action': 'register_observation_aware_adaptation_study'}
            (root/'report.json').write_text(study.recovery._json(report))
            with sqlite3.connect(root/'supervisor.sqlite') as db:
                db.executescript('CREATE TABLE config(id INTEGER PRIMARY KEY,evidence TEXT); CREATE TABLE nodes(name TEXT PRIMARY KEY,status TEXT,digest TEXT,origin TEXT,error TEXT);')
                db.execute('INSERT INTO config VALUES (1,?)', (study.recovery._json(protocol),))
                db.executemany('INSERT INTO nodes VALUES (?,?,?,?,NULL)',
                               [(node, 'complete', node+'-digest', 'adopted') for node in study.supervisor.NODES])
            def validate(root, paths, node):
                return {'next_action': 'register_observation_aware_adaptation_study'}, node+'-digest'
            with patch.object(study.supervisor, '_sources', return_value=pins), \
                 patch.object(study.supervisor, '_validate', side_effect=validate) as check, \
                 patch.object(study.supervisor, '_stop_after', return_value=None):
                self.assertEqual(len(study._verified_predecessor(root)), 64)
                self.assertEqual(check.call_count, 4)
                with sqlite3.connect(root/'supervisor.sqlite') as db:
                    db.execute("UPDATE nodes SET digest='changed' WHERE name='factorial'")
                with self.assertRaisesRegex(ValueError, 'invalid_supervisor'):
                    study._verified_predecessor(root)
