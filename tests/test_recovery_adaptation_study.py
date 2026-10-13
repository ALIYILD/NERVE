import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import recovery_adaptation_study as study


def fixture(seed,scenario,adaptive):
    return {'seed':seed,'scenario':scenario,'adaptive':adaptive,
        'learning_updates':2 if adaptive else 0,'metrics':{'active_steps':60,
        'supervisor_steps':20,'violations':0,'mean_goal_error':.9 if adaptive else 1.,
        'mean_prediction_error':.1,'successful_recoveries':1}}


class RecoveryAdaptationStudyTests(unittest.TestCase):
    def setUp(self):
        # Only graph tests use synthetic preflight/episode fixtures.
        mock=patch.object(study,'_validate_preflight')
        mock.start()
        self.addCleanup(mock.stop)

    def test_gate_matched_nonregression_and_learning(self):
        rows=[fixture(1,s,a) for s in study.SCENARIOS for a in (False,True)]
        self.assertTrue(study.compare(rows)['passed'])
        self.assertEqual(len(study.compare(rows)['paired_deltas']),2)
        rows[-1]['metrics']['supervisor_steps']=21
        rows[-1]['metrics']['active_steps']=59
        self.assertIn('drift:regression:supervisor_steps',study.compare(rows)['reasons'])
        with self.assertRaises(ValueError):study.compare(rows[:-1])
        rows[-1]['metrics']['supervisor_steps']=20
        rows[-1]['metrics']['active_steps']=60
        for row in rows:row['learning_updates']=0
        self.assertFalse(study.compare(rows)['passed'])

    def test_source_manifest_disjoint_bounded_explicit(self):
        p=study.manifest()
        self.assertFalse(set(p['splits']['validation']) & set(p['splits']['holdout']))
        self.assertEqual(p['plant']['sensor_delay_steps'],1)
        self.assertEqual(p['max_episodes']*80,p['max_plant_steps'])
        self.assertFalse(p['promotion_authorized'])

    def test_claim_before_execute_and_holdout_after_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'study'
            def execute(seed,scenario,adaptive):
                with sqlite3.connect(root/'ledger.sqlite') as db:
                    self.assertEqual(db.execute('SELECT status FROM trials ORDER BY ordinal DESC LIMIT 1').fetchone()[0],'claimed')
                    if seed>=34001:
                        status,report=db.execute('SELECT status,report FROM study').fetchone()
                        self.assertEqual(status,'holdout_claimed')
                        self.assertTrue(json.loads(report)['selection_frozen'])
                return fixture(seed,scenario,adaptive)
            # Orchestration fixture only; production validates full plant traces.
            with patch.object(study.episode,'validate'):
                report=study._run(root,execute,lambda path:{'fixture':True},Path(temp)/'claims.sqlite')
            self.assertEqual(report['episodes'],96)
            self.assertTrue(report['holdout_consumed'])
            self.assertEqual(report['recommendation'],'candidate_for_review')
            self.assertFalse(report['deployed'])
            with self.assertRaises(FileExistsError):
                study._run(root,execute,lambda path:{},Path(temp)/'claims.sqlite')

    def test_failed_validation_preserves_final_streams(self):
        def reject(seed,scenario,adaptive):
            row=fixture(seed,scenario,adaptive)
            row['metrics']['mean_goal_error']=1.
            return row
        with tempfile.TemporaryDirectory() as temp,patch.object(study.episode,'validate'):
            report=study._run(Path(temp)/'study',reject,lambda path:{},Path(temp)/'claims.sqlite')
            self.assertEqual(report['episodes'],32)
            self.assertFalse(report['holdout_consumed'])
            self.assertEqual(report['recommendation'],'retain_baseline')

    def test_failure_consumes_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'study'
            def fail(*args):raise RuntimeError('fixture')
            with self.assertRaises(RuntimeError):study._run(root,fail,lambda path:{},Path(temp)/'claims.sqlite')
            with sqlite3.connect(root/'ledger.sqlite') as db:
                self.assertEqual(db.execute('SELECT status FROM study').fetchone()[0],'failed_consumed')
                self.assertEqual(db.execute('SELECT status FROM trials').fetchone()[0],'failed_consumed')

    def test_source_drift_blocks_first_trial(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(study,'_sources',side_effect=[{'a':1},{'a':1},{'a':2}]):
            with self.assertRaises(ValueError):study._run(Path(temp)/'study',lambda *args:self.fail('must not execute'),lambda path:{},Path(temp)/'claims.sqlite')

    def test_renamed_output_cannot_reuse_consumed_dataset(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(study.episode,'validate'):
            def reject(seed,scenario,adaptive):
                row=fixture(seed,scenario,adaptive);row['metrics']['mean_goal_error']=1.
                return row
            claims=Path(temp)/'claims.sqlite'
            study._run(Path(temp)/'first',reject,lambda path:{},claims)
            with self.assertRaisesRegex(ValueError,'already_consumed'):
                study._run(Path(temp)/'renamed',reject,lambda path:{},claims)

    def test_nonfinite_metrics_and_boolean_counts_rejected(self):
        for value in (float('nan'),float('inf'),True):
            rows=[fixture(1,s,a) for s in study.SCENARIOS for a in (False,True)]
            rows[0]['metrics']['mean_goal_error']=value
            with self.assertRaises(ValueError):study.compare(rows)

    def test_child_timeout_cleanup(self):
        from unittest.mock import MagicMock
        process=MagicMock();process.pid=123;process.is_alive.return_value=True
        reader=MagicMock();reader.poll.return_value=False
        context=MagicMock();context.Pipe.return_value=(reader,MagicMock());context.Process.return_value=process
        with patch.object(study.multiprocessing,'get_context',return_value=context):
            with self.assertRaises(TimeoutError):study._execute(1,'stationary',False)
        process.terminate.assert_called_once();process.kill.assert_called_once()


class PreflightReceiptTests(unittest.TestCase):
    def test_false_preflight_check_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                study._validate_preflight({'status':'passed','checks':{},'identity_provider':'synthetic_fixture'},Path(temp))
