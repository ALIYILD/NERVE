import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('external_reconcile', ROOT/'scripts/reconcile_external_methods.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class ExternalReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.galahad = self.root/'galahad'
        for name in ('scripts/run_external_methods.py', 'src/nerve_awim/external_methods/__init__.py', 'configs/external-methods-protected.json'):
            path = self.galahad/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}')
        self.receipt, self.dev = self.root/'receipt.json', self.root/'dev.json'
        self.receipt.write_text('{}'); self.dev.write_text('[]')
        self.result = dict(status='development_audit_complete', new_model_calls=0, holdout_accessed=False, promotion_authorized=False)

    def run_bridge(self, **changes):
        value = dict(self.result, **changes)
        completed = subprocess.CompletedProcess([], 0, stdout=json.dumps(value))
        with patch.object(bridge.subprocess, 'run', return_value=completed) as worker:
            result = bridge.run(self.galahad, self.root/'state', self.receipt, self.dev)
        return result, worker.call_count

    def test_success_replays_without_worker(self):
        result, calls = self.run_bridge()
        self.assertEqual('complete', result['status']); self.assertEqual(1, calls)
        replay, calls = self.run_bridge()
        self.assertEqual(result, replay); self.assertEqual(0, calls)

    def test_changed_inputs_refused(self):
        self.run_bridge()
        self.dev.write_text('[1]')
        with self.assertRaisesRegex(ValueError, 'binding_changed'): self.run_bridge()

    def test_changed_source_refused(self):
        self.run_bridge()
        (self.galahad/'scripts/run_external_methods.py').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'binding_changed'): self.run_bridge()

    def test_model_call_or_promotion_cannot_complete_goal(self):
        for field, value in [('new_model_calls', 1), ('holdout_accessed', True), ('promotion_authorized', True)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                completed = subprocess.CompletedProcess([], 0, stdout=json.dumps(dict(self.result, **{field: value})))
                with patch.object(bridge.subprocess, 'run', return_value=completed):
                    result = bridge.run(self.galahad, Path(directory), self.receipt, self.dev)
                self.assertNotEqual('complete', result['status'])


if __name__ == '__main__': unittest.main()
