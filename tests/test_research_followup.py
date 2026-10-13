import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import research_followup as followup


class ResearchFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.report = {'result': {'status': 'no_deployable_improvement'}}
        (self.source / 'report.json').write_text(json.dumps(self.report))

    def run_followup(self):
        return followup.run_followup(self.root / 'followup', self.source)

    def test_invalid_receipt_never_dispatches(self):
        with patch.object(followup.worldcore_study, 'validate_receipt', side_effect=ValueError('invalid')), patch.object(followup.worldcore_diagnostics, 'run_diagnostic') as diagnostic:
            with self.assertRaises(ValueError):
                self.run_followup()
        diagnostic.assert_not_called()

    def test_durable_claim_and_no_retry(self):
        def diagnose(path):
            with sqlite3.connect(self.root / 'followup/followup.sqlite') as db:
                self.assertEqual(db.execute("SELECT status FROM nodes WHERE name='outage_feasibility'").fetchone()[0], 'claimed')
            raise RuntimeError('failure')
        with patch.object(followup.worldcore_study, 'validate_receipt'), patch.object(followup.worldcore_diagnostics, 'run_diagnostic', side_effect=diagnose) as diagnostic:
            with self.assertRaises(RuntimeError):
                self.run_followup()
            with self.assertRaises(FileExistsError):
                self.run_followup()
            self.assertEqual(diagnostic.call_count, 1)

    def test_rejection_triggers_diagnosis_not_promotion(self):
        with patch.object(followup.worldcore_diagnostics, 'validate_receipt', create=True), patch.object(followup.worldcore_study, 'validate_receipt') as validate, patch.object(followup.worldcore_diagnostics, 'run_diagnostic', return_value={'scope': 'fixture'}) as diagnostic:
            result = self.run_followup()
        self.assertEqual(validate.call_count, 2)
        diagnostic.assert_called_once()
        self.assertEqual(result['status'], 'diagnosed')
        self.assertFalse(result['automatic_retry'])
        self.assertFalse(result['goal_achieved'])
        self.assertFalse(result['deployed'])

    def test_candidate_does_not_trigger_failure_diagnosis(self):
        self.report['result']['status'] = 'candidate_for_human_review'
        (self.source / 'report.json').write_text(json.dumps(self.report))
        with patch.object(followup.worldcore_study, 'validate_receipt'), patch.object(followup.worldcore_diagnostics, 'run_diagnostic') as diagnostic:
            result = self.run_followup()
        diagnostic.assert_not_called()
        self.assertEqual(result['status'], 'no_registered_diagnostic')

    def test_source_change_consumes_node(self):
        with patch.object(followup.worldcore_diagnostics, 'validate_receipt', create=True), patch.object(followup.worldcore_study, 'validate_receipt'), patch.object(followup.worldcore_diagnostics, 'run_diagnostic', return_value={}), patch.object(followup, '_sources', side_effect=[{'a': 1}, {'a': 2}]):
            with self.assertRaises(ValueError):
                self.run_followup()
        with sqlite3.connect(self.root / 'followup/followup.sqlite') as db:
            self.assertEqual(db.execute("SELECT status FROM nodes WHERE name='outage_feasibility'").fetchone()[0], 'failed_consumed')

    def test_malformed_diagnosis_not_accepted(self):
        with patch.object(followup.worldcore_study, 'validate_receipt'), patch.object(followup.worldcore_diagnostics, 'run_diagnostic', return_value={}):
            with self.assertRaises(ValueError):
                self.run_followup()
        with sqlite3.connect(self.root / 'followup/followup.sqlite') as db:
            self.assertEqual(db.execute("SELECT status FROM nodes WHERE name='outage_feasibility'").fetchone()[0], 'failed_consumed')
