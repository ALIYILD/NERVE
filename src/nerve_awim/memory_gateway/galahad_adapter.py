"""Optional Galahad preflight; runtime execution remains evidence-gated.

No optional dependency is imported and no licence or key material is read.
Installing packages cannot silently enable an unverified KV execution path.
"""
from __future__ import annotations

from importlib import metadata
import platform
import shutil
import sys
from typing import TYPE_CHECKING

from .kv_adapter import KVCapabilities, KVHealth

if TYPE_CHECKING:
    from .contracts import KVCacheIdentity, MemoryScope


def _version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def preflight() -> dict:
    """Observe local metadata only. Never assert GPU/licence/security verification."""
    packages = {name: _version(name) for name in ("galahad-kv", "vllm", "sglang")}
    blockers = []
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        blockers.append("unsupported_platform")
    if not (3, 10) <= sys.version_info[:2] <= (3, 14):
        blockers.append("unsupported_python")
    if packages["galahad-kv"] is None:
        blockers.append("galahad_not_installed")
    if packages["vllm"] is None:
        blockers.append("vllm_not_installed")
    if not shutil.which("nvidia-smi"):
        blockers.append("gpu_tool_unavailable")
    blockers.extend(("gpu_execution_unverified", "licence_rights_unverified",
                     "runtime_version_matrix_unverified", "runtime_identity_binding_unverified",
                     "trust_domain_isolation_unverified", "encryption_and_deletion_unverified",
                     "runtime_connector_integration_not_implemented"))
    return {
        "provider": "galahad", "available": False, "status": "blocked",
        "platform": platform.system(), "architecture": platform.machine(),
        "python": platform.python_version(), "packages": packages,
        "blockers": blockers, "gpu_verified": False, "licence_verified": False,
        "research_pins": {"galahad-kv": "1.31.4", "vllm": "0.31.0"},
        "research_pins_approved": False,
    }


def documented_vllm_config() -> dict[str, str]:
    """Upstream reference only, never an executable or activation command."""
    return {"kv_connector": "GalahadConnector", "kv_role": "kv_both",
            "kv_load_failure_policy": "recompute"}


class GalahadKVProvider:
    def health(self) -> KVHealth:
        result = preflight()
        return KVHealth(False, "blocked", tuple(result["blockers"]))

    def capabilities(self) -> KVCapabilities:
        # Effective NERVE capabilities, not vendor feature claims.
        return KVCapabilities("galahad", False, False, False, True)

    def validate_identity(self, identity: KVCacheIdentity) -> bool:
        return False

    def invalidate(self, scope: MemoryScope) -> bool:
        # No verified scoped deletion API: never claim erasure succeeded.
        return False
