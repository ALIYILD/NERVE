"""Actual scoped asymmetric retention checks; no fixture signing key/inference."""
import base64
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.retained_skill_contract import signing_payload

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('real_retention_adapter', ROOT / 'scripts/retained_scientific_skill.py')
adapter = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(adapter)
except ModuleNotFoundError as error:
    if error.name != "cryptography":
        raise
    adapter = None


@unittest.skipIf(adapter is None, "install the retention extra for Ed25519 adapter tests")
class ActualTrustTests(unittest.TestCase):
    def setUp(self):
        self.inputs = adapter.load_selection_inputs(ROOT / 'registry/scientific-v3-7b')

    def test_actual_ed25519_signature(self):
        record = self.inputs['record']
        signer = record['signed_by']
        self.assertTrue(self.inputs['verify_signature'](signer['key_id'], signing_payload(record), signer['signature']))

    def test_key_substitution_rejected_at_loader(self):
        trust = json.loads(adapter.TRUST_PATH.read_bytes())
        trust['public_key_base64'] = base64.b64encode(bytes(32)).decode()
        with tempfile.TemporaryDirectory() as d:
            replacement = Path(d) / 'trust.json'
            replacement.write_text(json.dumps(trust))
            with patch.object(adapter, 'TRUST_PATH', replacement):
                with self.assertRaises(ValueError):
                    adapter.load_selection_inputs(ROOT / 'registry/scientific-v3-7b')

    def test_scope_substitution_rejected_at_loader(self):
        trust = json.loads(adapter.TRUST_PATH.read_bytes())
        trust['model_digest'] = '0' * 64
        with tempfile.TemporaryDirectory() as d:
            replacement = Path(d) / 'trust.json'
            replacement.write_text(json.dumps(trust))
            with patch.object(adapter, 'TRUST_PATH', replacement):
                with self.assertRaises(ValueError):
                    adapter.load_selection_inputs(ROOT / 'registry/scientific-v3-7b')

    def test_scope_mismatch_rejected_by_signature(self):
        for field, value in [('skill_id', 'different'), ('version', 'v2'), ('config_hash', '0' * 64)]:
            record = deepcopy(self.inputs['record'])
            record[field] = value
            signer = record['signed_by']
            self.assertFalse(self.inputs['verify_signature'](signer['key_id'], signing_payload(record), signer['signature']))

    def test_missing_trust_after_load_fails_closed(self):
        record = self.inputs['record']; signer = record['signed_by']
        with patch.object(adapter, 'TRUST_PATH', Path('/nonexistent-nerve-trust')):
            self.assertFalse(self.inputs['verify_signature'](signer['key_id'], signing_payload(record), signer['signature']))


if __name__ == '__main__':
    unittest.main()
