"""Coordinator fault/state tests; model study has separate transport coverage."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_research_coordinator as c


class ScientificResearchCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.paths=[self.base/x for x in ('coordinator','journal.sqlite','development','development.sqlite','validation','validation.sqlite')]
        self.parent={'status':'complete','facts':'fixed'}
        self.child={'status':'complete','screen':{'passed':False},'summary':{'calls':16}}
        for target,value in (('sources',{'p':'fixed'}),('_adopt_development',self.parent),('_existing',self.parent)):
            p=patch.object(c,target,return_value=value);p.start();self.addCleanup(p.stop)
        self.dispatch=patch.object(c.validation,'run',return_value=self.child).start()
        self.resume=patch.object(c.validation,'validate_receipt',return_value=self.child).start()
        self.addCleanup(patch.stopall)

    def run_graph(self):return c.run(*self.paths,'a'*64)

    def test_complete_rejection_and_resume_without_dispatch_or_rewrite(self):
        report=self.run_graph();self.assertEqual(report['status'],'retain_baseline')
        self.assertFalse(report['goal_achieved']);self.assertFalse(report['promotion_authorized'])
        path=self.paths[0]/'report.json';before=(path.read_bytes(),path.stat().st_mtime_ns)
        self.assertEqual(self.run_graph(),report)
        self.dispatch.assert_called_once();self.resume.assert_called_once()
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)

    def test_passing_child_only_requests_independent_review(self):
        self.child['screen']['passed']=True
        report=self.run_graph();self.assertEqual(report['status'],'candidate_requires_independent_review')
        self.assertFalse(report['promotion_authorized'])

    def test_child_failure_is_consumed_no_retry(self):
        self.dispatch.return_value={'status':'failed_consumed'}
        with self.assertRaisesRegex(ValueError,'validation_failed'):self.run_graph()
        with self.assertRaisesRegex(ValueError,'research_failed'):self.run_graph()
        self.dispatch.assert_called_once();self.resume.assert_not_called()

    def test_interruption_after_child_complete_can_only_adopt(self):
        with patch.object(c,'_atomic_write',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.run_graph()
        # Caught interruption is terminal; no automatic retry.
        with self.assertRaisesRegex(ValueError,'research_failed'):self.run_graph()
        self.dispatch.assert_called_once()

    def test_hard_crash_claim_without_child_cannot_dispatch(self):
        self.run_graph()
        with sqlite3.connect(self.paths[1]) as db:
            db.execute("update scientific_research_runs set status='claimed',digest=NULL")
        (self.paths[0]/'report.json').unlink()
        self.resume.side_effect=ValueError('incomplete_experiment_consumed')
        with self.assertRaisesRegex(ValueError,'incomplete'):self.run_graph()
        self.dispatch.assert_called_once()

    def test_hard_crash_after_child_complete_reconciles_without_dispatch(self):
        report=self.run_graph()
        with sqlite3.connect(self.paths[1]) as db:
            db.execute("update scientific_research_runs set status='claimed',digest=NULL")
        (self.paths[0]/'report.json').unlink()
        self.assertEqual(self.run_graph(),report);self.dispatch.assert_called_once()

    def test_missing_or_tampered_completed_output_cannot_rebuild(self):
        self.run_graph();(self.paths[0]/'report.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'output_changed'):self.run_graph()
        self.dispatch.assert_called_once()

    def test_source_or_shared_claim_drift_fails_consumed(self):
        def tamper(*args):
            with sqlite3.connect(self.paths[1]) as db:db.execute("update scientific_research_runs set status='bad'")
            return self.child
        self.dispatch.side_effect=tamper
        with self.assertRaisesRegex(ValueError,'claim_changed'):self.run_graph()
        with self.assertRaisesRegex(ValueError,'failed_consumed'):self.run_graph()

    def test_new_directory_cannot_repeat_parent_identity(self):
        self.run_graph();self.paths[0]=self.base/'different'
        with self.assertRaisesRegex(ValueError,'configuration_changed'):self.run_graph()
        self.dispatch.assert_called_once()

    def test_no_predecessor_or_overlapping_paths_never_dispatch(self):
        with patch.object(c,'_adopt_development',side_effect=ValueError('missing')):
            with self.assertRaises(ValueError):self.run_graph()
        self.paths[1]=self.paths[0]/'journal.sqlite'
        with self.assertRaisesRegex(ValueError,'distinct_external'):self.run_graph()
        self.dispatch.assert_not_called()


if __name__=='__main__':unittest.main()
