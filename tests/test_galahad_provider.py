"""CPU contract tests; none of these execute Galahad or restore tensors."""
from dataclasses import fields, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway.compatibility import identity_is_complete, identity_key
from nerve_awim.memory_gateway.contracts import KVCacheIdentity, MemoryScope
from nerve_awim.memory_gateway.galahad_adapter import (
    GalahadKVProvider, documented_vllm_config, preflight,
)
from nerve_awim.memory_gateway.null_kv_adapter import NullKVProvider


def identity():
    digest = hashlib.sha256(b"synthetic").hexdigest()
    return KVCacheIdentity(
        scope=MemoryScope("tenant-a", "agent-a", "synthetic-patient-a"),
        model_id="synthetic-model", architecture="synthetic-transformer",
        model_revision="immutable-model-sha", tokenizer_revision="immutable-tokenizer-sha",
        runtime_revision="synthetic-runtime-1", quantization="none",
        kv_representation="bf16", attention_config="synthetic-full-attention-1",
        prompt_sha256=digest, tokens_sha256=digest, instruction_revision="policy-1",
        adapter_revision="none", source_digest=digest,
    )


class GalahadProviderTests(unittest.TestCase):
    def test_complete_identity_has_deterministic_key(self):
        value = identity()
        self.assertTrue(identity_is_complete(value))
        self.assertEqual(identity_key(value), identity_key(replace(value)))
        self.assertEqual(len(identity_key(value)), 64)

    def test_every_identity_field_changes_key(self):
        value = identity()
        key = identity_key(value)
        for field in fields(value):
            if field.name == "scope":
                continue
            changed = "a" * 64 if field.name.endswith("sha256") or field.name == "source_digest" else "different-immutable-value"
            with self.subTest(field=field.name):
                candidate = replace(value, **{field.name: changed})
                self.assertTrue(identity_is_complete(candidate))
                self.assertNotEqual(key, identity_key(candidate))
        for name in ("tenant_id", "agent_id", "context"):
            changed_scope = replace(value.scope, **{name: "other"})
            self.assertNotEqual(key, identity_key(replace(value, scope=changed_scope)))

    def test_unknown_and_malformed_metadata_cannot_have_cache_key(self):
        for bad in ("", "unknown", "latest", "main", "none", None):
            candidate = replace(identity(), model_revision=bad)
            self.assertFalse(identity_is_complete(candidate))
            self.assertEqual(identity_key(candidate), "")
        for name in ("tokens_sha256", "prompt_sha256", "source_digest"):
            self.assertEqual(identity_key(replace(identity(), **{name: "bad"})), "")
        self.assertFalse(identity_is_complete(object()))

    def test_null_never_reports_storage_or_restore(self):
        provider = NullKVProvider()
        self.assertFalse(provider.health().available)
        self.assertFalse(provider.capabilities().persistent)
        self.assertFalse(provider.capabilities().restore)
        self.assertFalse(provider.validate_identity(identity()))
        self.assertTrue(provider.invalidate(identity().scope))

    def test_missing_runtime_is_reported_without_import_or_execution(self):
        with patch("nerve_awim.memory_gateway.galahad_adapter._version", return_value=None), \
             patch("nerve_awim.memory_gateway.galahad_adapter.platform.system", return_value="Darwin"), \
             patch("nerve_awim.memory_gateway.galahad_adapter.shutil.which", return_value=None):
            report = preflight()
        self.assertFalse(report["available"])
        self.assertIn("unsupported_platform", report["blockers"])
        self.assertIn("galahad_not_installed", report["blockers"])
        self.assertIn("gpu_tool_unavailable", report["blockers"])

    def test_installed_packages_and_gpu_tool_do_not_bypass_security_gates(self):
        with patch("nerve_awim.memory_gateway.galahad_adapter._version", return_value="1.32.0"), \
             patch("nerve_awim.memory_gateway.galahad_adapter.platform.system", return_value="Linux"), \
             patch("nerve_awim.memory_gateway.galahad_adapter.platform.machine", return_value="x86_64"), \
             patch("nerve_awim.memory_gateway.galahad_adapter.shutil.which", return_value="/fake/nvidia-smi"):
            provider = GalahadKVProvider()
            self.assertFalse(provider.health().available)
            self.assertIn("runtime_identity_binding_unverified", provider.health().blockers)
            self.assertFalse(provider.validate_identity(identity()))
            self.assertFalse(provider.invalidate(identity().scope))
            self.assertFalse(provider.capabilities().restore)

    def test_no_secret_environment_values_in_preflight(self):
        with patch.dict(os.environ, {"GALAHAD_STORE_PASSPHRASE": "sentinel-secret",
                                     "GALAHAD_LICENCE_FILE": "/sentinel/private/licence"}):
            output = json.dumps(preflight())
        self.assertNotIn("sentinel", output)

    def test_documented_connector_requests_recompute_on_failure(self):
        self.assertEqual(documented_vllm_config(), {
            "kv_connector": "GalahadConnector", "kv_role": "kv_both",
            "kv_load_failure_policy": "recompute",
        })

    def test_preflight_cli_exit_does_not_claim_runtime_success(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "scripts/galahad_preflight.py"],
                                cwd=root, env={**os.environ, "PYTHONPATH": str(root / "src")},
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
