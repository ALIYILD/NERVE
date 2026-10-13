from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import phase_forecast_study as study

PATHS = {'study':'fixture-study','claims':'fixture-claims',
         'coordinator_directory':'fixture-coordinator','coordinator_journal':'fixture-journal'}


def fixture(seed,scenario,arm,timeout=30):
    return {'control':{'arm':arm,'episode':{'seed':seed,'scenario':scenario}},
            'forecasts':[],'metrics':{'legacy_mae':1.,'routed_mae':.9,
            'controller_predictions_preserved':True,'actions_changed':False,'missing_forecasts':0},
            'elapsed_seconds':.1}


class PhaseForecastStudyTests(unittest.TestCase):
    def setUp(self):
        for target,name,kwargs in (
            (study,'SPLITS',{'new':{'train':(1,), 'validation':(2,), 'holdout':(3,4)}}),
            (study,'_sources',{'return_value':{'fixture':'pin'}}),
            (study,'_verified_predecessor',{'return_value':'fixture'}),
            (study.worker,'validate',{})):
            mock = patch.object(target,name,**kwargs); mock.start(); self.addCleanup(mock.stop)

    def test_manifest_and_dataset_exclude_labels_and_source_versions(self):
        p = study.manifest(); original = study._dataset(p)
        self.assertEqual(p['max_episodes'],512)
        self.assertEqual(p['max_plant_steps'],40960)
        self.assertFalse(p['promotion_authorized'])
        p.update(protocol='other',arms=['renamed'],source_sha256={'other':'revision'})
        self.assertEqual(original,study._dataset(p))
        p['plant'] = {'changed':True}
        self.assertNotEqual(original,study._dataset(p))

    def test_gate_requires_each_arm_regime_and_strict_gain(self):
        rows = [fixture(1,s,a) for s in study.SCENARIOS for a in study.ARMS]
        self.assertTrue(study.compare(rows)['passed'])
        rows[0]['metrics']['routed_mae'] = 1.001
        self.assertFalse(study.compare(rows)['passed'])
        for row in rows: row['metrics']['routed_mae'] = 1.
        self.assertFalse(study.compare(rows)['passed'])
        with self.assertRaises(ValueError): study.compare(rows[:-1])
        with self.assertRaises(ValueError): study.compare(rows+[rows[0]])

    def test_exact_controller_preservation_action_and_missing_gates(self):
        for name,value in (('controller_predictions_preserved',False),('actions_changed',True),('missing_forecasts',1)):
            rows = [fixture(1,s,a) for s in study.SCENARIOS for a in study.ARMS]
            rows[0]['metrics'][name] = value
            self.assertFalse(study.compare(rows)['passed'])
        for name,value in (('legacy_mae',float('nan')),('routed_mae',True),('missing_forecasts',False),('actions_changed',0)):
            rows = [fixture(1,s,a) for s in study.SCENARIOS for a in study.ARMS]
            rows[0]['metrics'][name] = value
            with self.assertRaises(ValueError): study.compare(rows)

    def test_missing_forecasts_reject_without_fabricated_zero_score(self):
        rows = [fixture(1,s,a) for s in study.SCENARIOS for a in study.ARMS]
        rows[0]['metrics'].update(missing_forecasts=1,routed_mae=None)
        result = study.compare(rows)
        self.assertFalse(result['passed'])
        self.assertIsNone(result['sum_stratum_mae_gain'])
        self.assertIsNone(result['strata'][0]['routed_mae'])

    def test_full_graph_claim_before_dispatch_and_stage_freeze(self):
        with tempfile.TemporaryDirectory() as temp:
            root,claims = Path(temp)/'run',Path(temp)/'claims.sqlite'
            def execute(seed,scenario,arm,timeout):
                self.assertGreater(timeout,0); self.assertLessEqual(timeout,30)
                with sqlite3.connect(root/'ledger.sqlite') as db:
                    self.assertEqual(db.execute('SELECT status FROM trials ORDER BY ordinal DESC LIMIT 1').fetchone()[0],'claimed')
                    stages = dict(db.execute('SELECT split,evidence FROM stages'))
                if seed >= 2: self.assertTrue(json.loads(stages['train'])['passed'])
                if seed >= 3: self.assertTrue(json.loads(stages['validation'])['passed'])
                return fixture(seed,scenario,arm)
            result = study._run(root,claims,'prior',PATHS,execute)
            self.assertEqual(result['episodes'],64)
            self.assertEqual(result['recommendation'],'forecast_candidate_for_review')
            self.assertTrue(result['holdout_consumed'])
            self.assertFalse(result['candidate_promoted'])
            self.assertTrue(study.validate_receipt(root,claims,'prior',PATHS))
            with self.assertRaisesRegex(ValueError,'already_consumed'):
                study._run(Path(temp)/'renamed',claims,'prior',PATHS,execute)

    def test_training_and_validation_failure_do_not_advance(self):
        for failed_seed,episodes in ((1,16),(2,32)):
            with self.subTest(seed=failed_seed), tempfile.TemporaryDirectory() as temp:
                def execute(seed,scenario,arm,timeout):
                    self.assertLessEqual(seed,failed_seed)
                    row = fixture(seed,scenario,arm)
                    if seed == failed_seed: row['metrics']['routed_mae'] = 1.
                    return row
                result = study._run(Path(temp)/'run',Path(temp)/'claims','prior',PATHS,execute)
                self.assertEqual(result['episodes'],episodes)
                self.assertFalse(result['holdout_consumed'])
                self.assertEqual(result['recommendation'],'retain_legacy_forecast')

    def test_holdout_failure_never_promotes(self):
        with tempfile.TemporaryDirectory() as temp:
            def execute(seed,scenario,arm,timeout):
                row = fixture(seed,scenario,arm)
                if seed >= 3: row['metrics']['routed_mae'] = 2.
                return row
            result = study._run(Path(temp)/'run',Path(temp)/'claims','prior',PATHS,execute)
            self.assertTrue(result['holdout_consumed'])
            self.assertEqual(result['recommendation'],'retain_legacy_forecast')

    def test_failure_consumes_claim_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            root,claims = Path(temp)/'run',Path(temp)/'claims'
            with self.assertRaisesRegex(RuntimeError,'child_failed'):
                study._run(root,claims,'prior',PATHS,lambda *args: (_ for _ in ()).throw(RuntimeError('child_failed')))
            with sqlite3.connect(root/'ledger.sqlite') as db:
                self.assertEqual(db.execute('SELECT status FROM trials').fetchone()[0],'failed_consumed')
            with self.assertRaisesRegex(ValueError,'already_consumed'):
                study._run(Path(temp)/'again',claims,'prior',PATHS,fixture)

    def test_budget_and_source_changes_stop_dispatch(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(study.time,'monotonic',side_effect=[0,1801]):
            with self.assertRaisesRegex(RuntimeError,'budget_exhausted'):
                study._run(Path(temp)/'run',Path(temp)/'claims','prior',PATHS,lambda *a:self.fail('dispatched'))
        with tempfile.TemporaryDirectory() as temp, patch.object(study,'_sources',side_effect=[{'a':1},{'a':2}]):
            with self.assertRaisesRegex(ValueError,'source_drift'):
                study._run(Path(temp)/'run',Path(temp)/'claims','prior',PATHS,lambda *a:self.fail('dispatched'))

    def test_tampered_report_journal_freeze_and_claim_rejected(self):
        for target in ('report','trial','stage','claim'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                root,claims = Path(temp)/'run',Path(temp)/'claims'
                result = study._run(root,claims,'prior',PATHS,fixture)
                if target == 'report':
                    result['candidate_promoted'] = True
                    (root/'report.json').write_text(study.recovery._json(result)+'\n')
                elif target == 'claim':
                    with sqlite3.connect(claims) as db: db.execute("UPDATE phase_forecast_studies SET status='claimed'")
                else:
                    with sqlite3.connect(root/'ledger.sqlite') as db:
                        db.execute("DELETE FROM stages WHERE split='train'" if target == 'stage' else "UPDATE trials SET seed=999 WHERE ordinal=1")
                with self.assertRaises(ValueError): study.validate_receipt(root,claims,'prior',PATHS)

    def test_explicit_predecessor_paths_required(self):
        with self.assertRaises(ValueError): study._paths({'study':'only'})
        with self.assertRaises(ValueError): study._paths({**PATHS,'extra':'field'})


class ForecastPredecessorTests(unittest.TestCase):
    def test_byte_exact_reanalysis_and_sources_are_required(self):
        result = {'source_sha256':{'fixture':'pin'},'status':'complete'}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'prior.json'; encoded = study.recovery._json(result)+'\n'
            path.write_text(encoded)
            with patch.object(study.predecessor,'run',return_value=result) as run, patch.object(study.predecessor,'_sources',return_value=result['source_sha256']):
                self.assertEqual(study._verified_predecessor(path,PATHS),sha256(encoded.encode()).hexdigest())
                expected = study._paths(PATHS)
                run.assert_called_once_with(expected['study'],expected['claims'],expected['coordinator_directory'],expected['coordinator_journal'])
                path.write_text(json.dumps(result,indent=2))
                with self.assertRaisesRegex(ValueError,'invalid_observer_predecessor'): study._verified_predecessor(path,PATHS)
                path.write_text(encoded)
                with patch.object(study.predecessor,'_sources',return_value={'changed':'source'}):
                    with self.assertRaisesRegex(ValueError,'invalid_observer_predecessor'): study._verified_predecessor(path,PATHS)
