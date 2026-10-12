"""One real repository-tool → learned-rule → memory/Hermes/gates episode."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from nerve_awim.integrated_learning import run

class IntegratedLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(__file__).resolve().parents[1]
        cls.directory=Path(cls.temp.name)/'fresh'
        cls.report=run(cls.root,cls.directory)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_real_verified_receipts_feed_training_and_rule_plan(self):
        r=self.report;self.assertEqual(r['status'],'offline_verified')
        self.assertEqual(len(r['arc_adaptation']['receipts']),2)
        self.assertTrue(r['arc_adaptation']['regex_probe_failed']);self.assertTrue(r['arc_adaptation']['correction_reused'])
        self.assertEqual(r['world_model']['backend'],'declarative-frame-v1')
        self.assertEqual(r['world_model']['plan']['actions'],['ast-inventory'])
        with sqlite3.connect(r['database']) as con:
            probe=r['arc_adaptation']['probe_receipt']
            probe_record,probe_outcome=con.execute('SELECT record,outcome FROM arc_decisions WHERE id=?',(probe['decision_id'],)).fetchone()
            self.assertEqual(json.loads(probe_record)['action']['registered_tool'],'regex-inventory')
            self.assertEqual(json.loads(probe_outcome)['semantic_status'],'failed')
            correction=json.loads(con.execute('SELECT record FROM adaptation_corrections WHERE id=?',(r['arc_adaptation']['reviewed_correction_id'],)).fetchone()[0])
            self.assertEqual(correction['verification_status'],'verified')
            self.assertEqual(r['arc_adaptation']['reused_correction_id'],correction['correction_id'])
            reused=json.loads(con.execute('SELECT record FROM arc_decisions WHERE id=?',(r['arc_adaptation']['receipts'][1]['decision_id'],)).fetchone()[0])
            self.assertEqual(reused['action']['registered_tool'],correction['proposed_change']['value'])
            for receipt in r['arc_adaptation']['receipts']:
                arc=json.loads(con.execute('SELECT outcome FROM arc_decisions WHERE id=?',(receipt['decision_id'],)).fetchone()[0])
                prediction_time,completion_time=con.execute('SELECT predicted_at,observed_at FROM wm_transitions WHERE id=?',(receipt['transition_id'],)).fetchone()
                self.assertEqual(arc['semantic_status'],'verified')
                self.assertLessEqual(prediction_time,arc['observed_at']);self.assertLessEqual(arc['observed_at'],completion_time)
        self.assertFalse(r['world_model']['eligibility'])
    def test_conflict_propagates_through_memory_hermes_plan_dispatch_and_restart(self):
        r=self.report;cid=r['uncertainty']['conflict_id']
        self.assertTrue(r['arc_adaptation']['third_dispatch_blocked']);self.assertTrue(r['arc_adaptation']['unaffected_dispatch_verified'])
        self.assertTrue(r['world_model']['new_conflict_blocked']);self.assertTrue(r['world_model']['restart_blocked'])
        self.assertTrue(r['uncertainty']['preserved_after_restart'])
        self.assertIn(cid,r['galahad_memory']['final_envelope']['open_conflict_ids'])
        self.assertIn(cid,r['hermes']['received_contexts'][-1]['conflicts'])
        self.assertTrue(r['uncertainty']['supported_output']['supported'])
        self.assertFalse(r['uncertainty']['qualified_output']['supported'])
        self.assertTrue(r['uncertainty']['qualified_output']['unresolved'])
        self.assertTrue(r['galahad_memory']['wrong_scope_denied']);self.assertTrue(r['galahad_memory']['omitted_adapter_denied']);self.assertTrue(r['world_model']['omitted_adapter_denied'])
    def test_cue_negative_evidence_pending_memory_and_no_paid_activation(self):
        r=self.report
        self.assertFalse(r['cce']['decision']['eligible']);self.assertIn('accuracy_gain_required',r['cce']['decision']['reasons'])
        self.assertEqual(r['cce']['pending_memory_status'],'pending');self.assertTrue(r['cce']['new_conflict_blocks_guidance'])
        self.assertEqual(r['hermes']['scripted_fixture_calls'],2);self.assertEqual(r['provider_calls'],0);self.assertEqual(r['provider_cost_usd'],0)
        self.assertFalse(r['deployment_authorized']);self.assertFalse(r['combined_improvement_claim'])
        self.assertEqual(len(r['implementation_hashes']),10)
    def test_fresh_directory_required_and_cli_help(self):
        before=(self.directory/'report.json').read_bytes()
        with self.assertRaises(ValueError):run(self.root,self.directory)
        self.assertEqual((self.directory/'report.json').read_bytes(),before)
        result=subprocess.run([sys.executable,'-m','nerve_awim.integrated_learning','--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0);self.assertIn('--repository',result.stdout)
