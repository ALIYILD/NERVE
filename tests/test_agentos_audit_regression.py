import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('audit_regression', Path(__file__).resolve().parents[1] / 'scripts/agentos_audit_regression.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditRegressionTests(unittest.TestCase):
    def test_reject_all_does_not_pass_positive_controls(self):
        result = audit.evaluate(dict.fromkeys(audit.EXPECTED, 'unknown'))
        self.assertFalse(result['accepted'])
        self.assertEqual(result['passed'], 4)
        self.assertTrue(audit.evaluate(dict(audit.EXPECTED))['accepted'])

    def test_false_reachability_and_circular_qa_fail(self):
        value = dict(audit.EXPECTED, b='supported', f='supported')
        result = audit.evaluate(value)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['passed'], 6)

    def test_schema_is_exact_and_types_fail_closed(self):
        for value in (None, [], {}, dict(audit.EXPECTED, extra='unknown'),
                      dict(audit.EXPECTED, a=True), dict(audit.EXPECTED, a='pass')):
            self.assertFalse(audit.evaluate(value)['valid_schema'])

    def test_frozen_receipt_precedes_call_and_repeat_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = audit.bridge.AgentOSLearning(Path(tmp))
            def invoke(*args, **kwargs):
                self.assertTrue((Path(tmp) / audit.RECEIPT_NAME).exists())
                return {'value': dict(audit.EXPECTED), 'tools': 0}
            result = audit.run(host, invoke)
            self.assertTrue(result['evaluation']['accepted'])
            self.assertFalse(result['promotion_authorized'])
            forbidden = Mock(side_effect=AssertionError('must not infer again'))
            with self.assertRaises(ValueError):
                audit.run(host, forbidden)
            forbidden.assert_not_called()

    def test_failure_is_durable_and_cannot_silently_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = audit.bridge.AgentOSLearning(Path(tmp))
            with self.assertRaises(RuntimeError):
                audit.run(host, Mock(side_effect=RuntimeError('failure')))
            self.assertIn('"status": "failed"', (Path(tmp) / audit.RECEIPT_NAME).read_text())
            with self.assertRaises(ValueError):
                audit.run(host, Mock())


if __name__ == '__main__':
    unittest.main()
