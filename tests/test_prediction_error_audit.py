import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('prediction_audit', Path(__file__).resolve().parents[1]/'scripts/audit_prediction_errors.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class PredictionErrorAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.path = self.root/'report.json'
        # First step: opposite signed components cancel exactly. Second step:
        # zero actual action removes the gain term despite a large gain mismatch.
        self.report = {'rows':[{'split':'train','arm':'fixture','episode':{'scenario':'drift','trace':[
            {'estimated_velocity':1.,'estimated_gain':.18,'true_gain':1.,'action':1,
             'predicted_velocity':1.,'true_velocity':1.,'prediction_error':0.,'action_source':'controller'},
            {'estimated_velocity':0.,'estimated_gain':.18,'true_gain':1.,'action':0,
             'predicted_velocity':0.,'true_velocity':.82,'prediction_error':.82,'action_source':'external_supervisor'}]}}]}
        self.path.write_text(json.dumps(self.report))

    def run_audit(self): return audit.audit(self.root,'claims','supervisor')

    def test_signed_identity_and_cancellation(self):
        with patch.object(audit.study,'validate_receipt') as verified:
            result = self.run_audit()
        verified.assert_called_once_with(self.root,'claims','supervisor')
        first, second = result['groups']
        self.assertAlmostEqual(first['mean_absolute_state'],.82)
        self.assertAlmostEqual(first['mean_absolute_gain'],.82)
        self.assertAlmostEqual(first['mean_cancellation'],1.64)
        self.assertAlmostEqual(first['mean_absolute_error'],0.)
        self.assertEqual(second['mean_absolute_gain'],0.)
        self.assertAlmostEqual(second['mean_absolute_state'],.82)
        self.assertLess(result['maximum_identity_residual'],1e-10)
        self.assertEqual(result['new_episodes'],0)

    def test_receipt_failure_propagates(self):
        with patch.object(audit.study,'validate_receipt',side_effect=ValueError('bad_receipt')):
            with self.assertRaisesRegex(ValueError,'bad_receipt'): self.run_audit()

    def test_receipt_change_during_validation_rejected(self):
        with patch.object(audit.study,'validate_receipt',side_effect=lambda *args:self.path.write_text('{}')):
            with self.assertRaisesRegex(ValueError,'receipt_changed'): self.run_audit()

    def test_inconsistent_forecast_rejected(self):
        self.report['rows'][0]['episode']['trace'][0]['predicted_velocity']=2.
        self.path.write_text(json.dumps(self.report))
        with patch.object(audit.study,'validate_receipt'):
            with self.assertRaisesRegex(ValueError,'identity_failed'): self.run_audit()

    def test_heldout_payloads_not_analyzed(self):
        with patch.object(audit.study,'validate_receipt'):
            before = self.run_audit()
            self.report['rows'].append({'split':'holdout','episode':None})
            self.path.write_text(json.dumps(self.report))
            self.assertEqual(self.run_audit(),before)
