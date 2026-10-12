import hashlib
from pathlib import Path
import tempfile
import unittest
from nerve_awim.safety_control.model_verification import verify_local_artifacts


class ModelVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'model.bin').write_bytes(b'fixture weights')
        self.manifest = {'model': 'fixture', 'revision': 'reviewed-v1',
                         'files': {'model.bin': hashlib.sha256(b'fixture weights').hexdigest()}}

    def test_verified_fixture_does_not_claim_capability_or_provider_attestation(self):
        result = verify_local_artifacts(self.root, self.manifest)
        self.assertEqual(result['status'], 'local_artifacts_verified')
        self.assertFalse(result['hidden_capability_absence_proven'])
        self.assertFalse(result['hosted_model_attested'])

    def test_changed_artifact_and_budget_denied(self):
        with self.assertRaises(ValueError):
            verify_local_artifacts(self.root, self.manifest, max_bytes=3)
        (self.root/'model.bin').write_bytes(b'changed weights')
        with self.assertRaises(PermissionError):
            verify_local_artifacts(self.root, self.manifest)

    def test_symlink_and_path_traversal_denied(self):
        (self.root/'alias').symlink_to(self.root/'model.bin')
        expected=self.manifest['files']['model.bin']
        for name in ('alias', '../model.bin', '/model.bin', 'a//b'):
            with self.subTest(name=name), self.assertRaises((OSError, ValueError)):
                verify_local_artifacts(self.root, {**self.manifest, 'files': {name: expected}})

    def test_malformed_manifest_denied(self):
        with self.assertRaises(ValueError):
            verify_local_artifacts(self.root, {**self.manifest, 'self_attested': True})
