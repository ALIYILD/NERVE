import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from nerve_awim.safety_control.cli import _owner_key


class SafetyCliTests(unittest.TestCase):
    def test_real_process_owner_stop_and_recovery_demo(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'fresh'
            command = [sys.executable, '-m', 'nerve_awim', 'safety-control', 'demo', '--directory', str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['status'], 'passed')
            self.assertTrue(all(report['checks'].values()))
            self.assertEqual(report['actual_alerts_sent'], 0)
            self.assertFalse(report['os_identity_separation_verified'])
            self.assertEqual(report, json.loads((output/'report.json').read_text()))
            again = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(again.returncode, 0)

    def test_owner_key_rejects_shared_readable_and_symlink_files(self):
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory)/'owner.key'
            key.write_text('k'*64)
            key.chmod(0o644)
            with self.assertRaises(PermissionError):
                _owner_key(key)
            key.chmod(0o600)
            self.assertEqual(_owner_key(key), 'k'*64)
            alias = Path(directory)/'alias'
            alias.symlink_to(key)
            with self.assertRaises(OSError):
                _owner_key(alias)

    def test_doctor_never_claims_deployment_is_verified(self):
        result = subprocess.run([sys.executable, '-m', 'nerve_awim', 'safety-control', 'doctor'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)['production_ready'])
