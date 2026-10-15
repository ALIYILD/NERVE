"""Canonical admission identities; a digest is not runtime compatibility proof."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .contracts import KVCacheIdentity

IDENTITY_FIELDS = (
    "model_id", "architecture", "model_revision", "tokenizer_revision",
    "runtime_revision", "quantization", "kv_representation", "attention_config",
    "prompt_sha256", "tokens_sha256", "instruction_revision", "adapter_revision",
    "source_digest",
)
_UNKNOWN = frozenset(("unknown", "unset", "unspecified", "latest", "main", "master", "?", "null"))
_HASH_FIELDS = frozenset(("prompt_sha256", "tokens_sha256", "source_digest"))


def identity_is_complete(identity: KVCacheIdentity) -> bool:
    """Reject unknown metadata, mutable revision aliases and malformed hashes."""
    if not is_dataclass(identity):
        return False
    scope = getattr(identity, "scope", None)
    if not is_dataclass(scope):
        return False
    for name in ("tenant_id", "agent_id", "context"):
        value = getattr(scope, name, None)
        if not isinstance(value, str) or not value.strip():
            return False
    for name in IDENTITY_FIELDS:
        value = getattr(identity, name, None)
        if not isinstance(value, str) or not value.strip() or value.strip().lower() in _UNKNOWN:
            return False
        if name in _HASH_FIELDS and not re.fullmatch(r"[0-9a-f]{64}", value):
            return False
        if value.lower() == "none" and name not in ("quantization", "adapter_revision"):
            return False
    return True


def identity_key(identity: KVCacheIdentity) -> str:
    """Empty means ineligible, never a lookup key. Version serialization explicitly."""
    if not identity_is_complete(identity):
        return ""
    payload = {"schema": "nerve-kv-identity-v1", "identity": asdict(identity)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()
