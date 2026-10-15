import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import evidence_gated_study as study


def fixture(seed, scenario, arm, timeout=30):
    adaptive = not arm.startswith('frozen')
    error = .7 if arm == 'gated_forget_h3' else .9 if arm.startswith('gated') else 1.
    return {'arm': arm, 'learning_evidence': [{'gain_changes': 1}] if arm.startswith('gated') else None, 'elapsed_seconds': .1, 'planning_sequences': 2160 if arm.endswith('h3') else 0,
            'episode': {'seed': seed, 'scenario': scenario, 'adaptive': adaptive,
                        'learning_updates': int(adaptive), 'metrics': {
                            'active_steps': 80, 'supervisor_steps': 0, 'violations': 0,
                            'successful_recoveries': 0, 'mean_goal_error': error,
                            'mean_prediction_error': .1}}}


class EvidenceGatedStudyTests(unittest.TestCase):
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
        self.assertEqual(study.select(rows)['candidate'], 'gated_forget_h3')
        for row in rows:
            if row['arm'] == 'frozen_h3': row['episode']['metrics']['mean_goal_error'] = .6
        self.assertFalse(study.compare(rows, 'gated_forget_h3')['passed'])
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
                        self.assertEqual(selection['candidate'], 'gated_forget_h3')
                return fixture(seed, scenario, arm)
            result = study._run(root, claims, (), (), execute)
            self.assertEqual(result['episodes'], 320)
            self.assertTrue(result['holdout_consumed'])
            self.assertEqual(result['recommendation'], 'candidate_for_review')
            self.assertTrue(study.validate_receipt(root, claims, (), ()))
            result['rows'][0]['elapsed_seconds'] = 99
            (root/'report.json').write_text(json.dumps(result))
            with self.assertRaises(ValueError): study.validate_receipt(root, claims, (), ())
            with self.assertRaisesRegex(ValueError, 'already_consumed'):
                study._run(Path(temp)/'renamed', claims, (), (), execute)

    def test_validation_rejection_does_not_try_runner_up_or_holdout(self):
        def reject(seed, scenario, arm, timeout):
            self.assertLess(seed, 21)
            row = fixture(seed, scenario, arm)
            if seed >= 11 and arm.startswith('gated'):
                self.assertEqual(arm, 'gated_forget_h3')
                row['episode']['metrics']['mean_goal_error'] = 2.
            return row
        with tempfile.TemporaryDirectory() as temp:
            result = study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), (), reject)
            self.assertEqual(result['episodes'], 192)
            self.assertFalse(result['holdout_consumed'])
            self.assertEqual(result['recommendation'], 'retain_baseline')

    def test_no_training_gain_stops_after_128(self):
        def reject(seed, scenario, arm, timeout):
            row = fixture(seed, scenario, arm)
            row['episode']['metrics']['mean_goal_error'] = 1.
            return row
        with tempfile.TemporaryDirectory() as temp:
            result = study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), (), reject)
            self.assertEqual(result['episodes'], 128)
            self.assertIsNone(result['selection']['candidate'])

    def test_child_failure_consumes_trial_and_study(self):
        with tempfile.TemporaryDirectory() as temp:
            root, claims = Path(temp)/'run', Path(temp)/'claims.sqlite'
            def fail(*args): raise RuntimeError('child_failed')
            with self.assertRaises(RuntimeError): study._run(root, claims, (), (), fail)
            with sqlite3.connect(root/'ledger.sqlite') as db:
                self.assertEqual(db.execute('SELECT status FROM trials').fetchone()[0], 'failed_consumed')
                self.assertEqual(db.execute('SELECT status FROM state').fetchone()[0], 'failed_consumed')
            with self.assertRaisesRegex(ValueError, 'already_consumed'):
                study._run(Path(temp)/'other', claims, (), (), fail)

    def test_budget_and_source_drift_stop_before_child(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(study.time, 'monotonic', side_effect=[0, 1201]):
            with self.assertRaisesRegex(RuntimeError, 'budget_exhausted'):
                study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), (), lambda *args: self.fail('no child'))
        with tempfile.TemporaryDirectory() as temp, patch.object(study, '_sources', side_effect=[{'a':1}, {'a':2}]):
            with self.assertRaisesRegex(ValueError, 'source_drift'):
                study._run(Path(temp)/'run', Path(temp)/'claims.sqlite', (), (), lambda *args: self.fail('no child'))

    def test_matched_adaptive_control_is_a_real_comparator(self):
        rows = [fixture(1, scenario, arm) for scenario in study.SCENARIOS for arm in study.ARMS]
        self.assertEqual(study.controls('gated_forget_h1'), ('frozen_h1', 'adaptive_consistent_h1'))
        self.assertEqual(study.controls('gated_forget_h3'), ('frozen_h1', 'frozen_h3', 'adaptive_consistent_h3'))
        for row in rows:
            if row['arm'] == 'adaptive_consistent_h3':
                row['episode']['metrics']['mean_goal_error'] = .6
        self.assertFalse(study.compare(rows, 'gated_forget_h3')['passed'])

    def test_journal_and_roster_cannot_be_omitted_or_relabelled(self):
        with tempfile.TemporaryDirectory() as temp:
            root, claims = Path(temp)/'run', Path(temp)/'claims.sqlite'
            study._run(root, claims, (), (), fixture)
            with sqlite3.connect(root/'ledger.sqlite') as db:
                db.execute("UPDATE trials SET arm='frozen_h1' WHERE ordinal=2")
            with self.assertRaises(ValueError): study.validate_receipt(root, claims, (), ())



class PredecessorVerificationTests(unittest.TestCase):
    def test_predecessor_is_read_only_and_requires_complete_matching_evidence(self):
        from hashlib import sha256
        from dataclasses import asdict
        from nerve_awim.memory_gateway.research_memory_planner import ResearchPlan
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            memory, journal = root/'memory.sqlite', root/'journal.sqlite'
            with sqlite3.connect(memory) as db:
                db.execute('CREATE TABLE original(value TEXT)')
                db.execute("INSERT INTO original VALUES('preserve')")
            original_memory = memory.read_bytes()
            scope = study.MemoryScope('synthetic-research','scientific-coordinator','verified-experiments')
            plan = ResearchPlan('diagnose_rejection_and_register_new_hypothesis', 'receipt', 'retain_baseline', 'memory-id')
            pins = {'fixture':'source'}
            config = {'protocol': study.coordinator.PROTOCOL, 'scope': asdict(scope),
                'memory_database': str(memory), 'memory_id': plan.memory_id,
                'receipt_sha256': plan.receipt_sha256, 'study_directory': str(root/'study'),
                'study_claims': str(root/'claims'), 'supervisor_directory': str(root/'supervisor'),
                'directory': str(root), 'source_sha256': pins, 'max_nodes': 1}
            result = {'next_action':'register_prediction_calibration_study'}
            report = {'status':'new_registered_experiment_required','protocol':config,
                'plan':plan.to_dict(),'diagnostic':result,'new_episodes':0,
                'promotion_authorized':False,'model_weights_trained':False,
                'goal_achieved':False,'next_action':result['next_action']}
            encoded = study.recovery._json(report)+'\n'
            (root/'report.json').write_text(encoded)
            key = sha256(study.recovery._json([study.coordinator.PROTOCOL,asdict(scope),plan.receipt_sha256]).encode()).hexdigest()
            with sqlite3.connect(journal) as db:
                db.execute('CREATE TABLE memory_research_runs_v1(identity TEXT PRIMARY KEY,config TEXT,status TEXT,digest TEXT)')
                db.execute('INSERT INTO memory_research_runs_v1 VALUES(?,?,?,?)',
                    (key,study.recovery._json(config),'complete',sha256(encoded.encode()).hexdigest()))
            before_journal = journal.read_bytes()
            with patch.object(study.coordinator,'_sources',return_value=pins), \
                 patch.object(study.coordinator,'_read_study',return_value={'fixture':True}) as read, \
                 patch.object(study.coordinator.diagnostic,'diagnose',return_value=result) as diagnose, \
                 patch.object(study.coordinator.ResearchMemoryPlanner,'plan',return_value=plan) as planner, \
                 patch.object(study.coordinator,'run',side_effect=AssertionError('mutating coordinator forbidden')):
                self.assertEqual(len(study._verified_predecessor(root,journal)),64)
                self.assertEqual(memory.read_bytes(),original_memory)
                self.assertEqual(journal.read_bytes(),before_journal)
                read.assert_called_once_with(str(root/'study'),'receipt')
                diagnose.assert_called_once_with({'fixture':True})
                self.assertEqual(planner.call_args.args[0].permissions, frozenset({'read'}))
                with sqlite3.connect(journal) as db:
                    db.execute("UPDATE memory_research_runs_v1 SET status='claimed'")
                with self.assertRaisesRegex(ValueError,'invalid_memory_coordinator'):
                    study._verified_predecessor(root,journal)
                with sqlite3.connect(journal) as db:
                    db.execute("UPDATE memory_research_runs_v1 SET status='complete'")
                planner.return_value = ResearchPlan('verify_and_record_outcome','receipt','retain_baseline',None)
                with self.assertRaisesRegex(ValueError,'invalid_memory_coordinator'):
                    study._verified_predecessor(root,journal)
                planner.return_value = plan
                report['protocol']['scope']['tenant_id'] = 'foreign'
                (root/'report.json').write_text(study.recovery._json(report)+'\n')
                with self.assertRaisesRegex(ValueError,'invalid_memory_coordinator'):
                    study._verified_predecessor(root,journal)
                report['protocol']['scope'] = asdict(scope)
                report['diagnostic']={'forged':True}
                altered = study.recovery._json(report)+'\n'
                (root/'report.json').write_text(altered)
                with sqlite3.connect(journal) as db:
                    db.execute('UPDATE memory_research_runs_v1 SET digest=?',(sha256(altered.encode()).hexdigest(),))
                with self.assertRaisesRegex(ValueError,'invalid_memory_coordinator'):
                    study._verified_predecessor(root,journal)
