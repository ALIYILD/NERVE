import gzip
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import prequential_research_coordinator as coordinator

RESULT={'status':'diagnostic_complete','new_episodes':0,'promotion_authorized':False,'goal_achieved':False,
        'next_action':'review_evidence_timing_and_register_new_hypothesis'}


class PrequentialResearchCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'run';self.journal=self.base/'journal.sqlite'
        self.artifact=self.base/'artifact.json'
        self.artifact.write_text(json.dumps({'status':'complete','screen':{'passed':False}}))
        for name,kwargs in (('sources',{'return_value':{'fixture':'pin'}}),):
            mock=patch.object(coordinator,name,**kwargs);mock.start();self.addCleanup(mock.stop)
        mock=patch.object(coordinator.diagnostic,'run',return_value=RESULT.copy())
        self.diagnose=mock.start();self.addCleanup(mock.stop)

    def run_coordinator(self):return coordinator.run(self.root,self.journal,self.artifact)
    def status(self):
        with sqlite3.connect(self.journal) as db:return db.execute('SELECT status FROM prequential_research_runs_v1').fetchone()[0]

    def test_claim_precedes_diagnosis_and_resume_preserves_bytes(self):
        def diagnose(path):
            self.assertEqual(path,self.artifact.resolve())
            self.assertIn(self.status(),('claimed','complete'))
            return RESULT.copy()
        self.diagnose.side_effect=diagnose
        first=self.run_coordinator();before=(self.root/'report.json').read_bytes()
        stat=(self.root/'report.json').stat().st_mtime_ns
        self.assertEqual(self.status(),'complete')
        self.assertEqual(self.run_coordinator(),first)
        self.assertEqual((self.root/'report.json').read_bytes(),before)
        self.assertEqual((self.root/'report.json').stat().st_mtime_ns,stat)
        self.assertEqual(first['new_episodes'],0);self.assertTrue(first['baseline_retained'])
        self.assertFalse(first['promotion_authorized'])
        self.assertEqual(len(first['completed_nodes']),2)

    def test_claimed_complete_artifact_reconciles_without_rewrite(self):
        expected=self.run_coordinator();before=(self.root/'report.json').read_bytes()
        with sqlite3.connect(self.journal) as db:db.execute("UPDATE prequential_research_runs_v1 SET status='claimed',digest=NULL")
        self.assertEqual(self.run_coordinator(),expected)
        self.assertEqual((self.root/'report.json').read_bytes(),before)
        self.assertEqual(self.status(),'complete')

    def test_missing_output_never_rebuilt_or_diagnosed_on_resume(self):
        self.run_coordinator();(self.root/'report.json').unlink();self.diagnose.reset_mock()
        with self.assertRaisesRegex(ValueError,'output_missing'):self.run_coordinator()
        self.diagnose.assert_not_called();self.assertFalse((self.root/'report.json').exists())
        self.assertEqual(self.status(),'failed_consumed')
        with self.assertRaisesRegex(RuntimeError,'failed_consumed'):self.run_coordinator()

    def test_failed_validation_consumes_claim(self):
        self.diagnose.side_effect=ValueError('invalid_evidence')
        with self.assertRaisesRegex(ValueError,'invalid_evidence'):self.run_coordinator()
        self.assertEqual(self.status(),'failed_consumed');self.diagnose.reset_mock()
        with self.assertRaises(RuntimeError):self.run_coordinator()
        self.diagnose.assert_not_called()

    def test_changed_output_rejected(self):
        self.run_coordinator();(self.root/'report.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'output_changed'):self.run_coordinator()
        self.assertEqual(self.status(),'failed_consumed')

    def test_journal_digest_mismatch_rejected(self):
        self.run_coordinator()
        with sqlite3.connect(self.journal) as db:db.execute("UPDATE prequential_research_runs_v1 SET digest='invalid'")
        with self.assertRaisesRegex(ValueError,'output_changed'):self.run_coordinator()
        self.assertEqual(self.status(),'failed_consumed')

    def test_directory_path_and_representation_cannot_escape_claim(self):
        self.run_coordinator()
        with self.assertRaisesRegex(ValueError,'configuration_changed'):
            coordinator.run(self.base/'other',self.journal,self.artifact)
        other=self.base/'copy.json';other.write_bytes(self.artifact.read_bytes())
        with self.assertRaisesRegex(ValueError,'configuration_changed'):
            coordinator.run(self.root,self.journal,other)
        self.artifact.write_text(json.dumps(json.loads(self.artifact.read_bytes()),indent=4))
        with self.assertRaisesRegex(ValueError,'configuration_changed'):self.run_coordinator()
        self.assertEqual(self.status(),'complete')

    def test_source_drift_during_diagnosis_fails_consumed(self):
        def changed(path):
            path.write_text('{"changed":true}');return RESULT.copy()
        self.diagnose.side_effect=changed
        with self.assertRaisesRegex(ValueError,'source_changed'):self.run_coordinator()
        self.assertEqual(self.status(),'failed_consumed')

    def test_code_change_blocks_resume(self):
        self.run_coordinator()
        with patch.object(coordinator,'sources',return_value={'fixture':'changed'}):
            with self.assertRaisesRegex(ValueError,'configuration_changed'):self.run_coordinator()

    def test_lock_blocks_concurrent_coordinator_and_shared_journal_required(self):
        self.root.mkdir()
        with coordinator._exclusive(self.root):
            with self.assertRaisesRegex(RuntimeError,'already_running'):self.run_coordinator()
        with self.assertRaisesRegex(ValueError,'outside_run'):
            coordinator.run(self.root,self.root/'journal.sqlite',self.artifact)

    def test_positive_study_and_authority_claims_rejected(self):
        self.artifact.write_text(json.dumps({'status':'complete','screen':{'passed':True}}))
        with self.assertRaisesRegex(ValueError,'rejected_development'):self.run_coordinator()

    def test_snapshot_gzip_canonical_identity_and_size_limit(self):
        raw=self.artifact.read_bytes();first=coordinator._snapshot(self.artifact)[2]
        self.artifact.write_bytes(gzip.compress(raw))
        self.assertEqual(coordinator._snapshot(self.artifact)[2],first)
        with patch.object(coordinator,'MAX_ARTIFACT_BYTES',4):
            with self.assertRaisesRegex(ValueError,'oversized'):coordinator._snapshot(self.artifact)
