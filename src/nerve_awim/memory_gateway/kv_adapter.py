"""Metadata-only provider admission boundary; tensors belong to the runtime."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .contracts import KVCacheIdentity, MemoryScope


@dataclass(frozen=True)
class KVHealth:
    available: bool
    status: str
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class KVCapabilities:
    provider: str
    persistent: bool
    restore: bool
    scope_invalidation: bool
    runtime_managed: bool


class PersistentKVProvider(Protocol):
    def health(self) -> KVHealth: ...
    def capabilities(self) -> KVCapabilities: ...
    def validate_identity(self, identity: KVCacheIdentity) -> bool: ...
    def invalidate(self, scope: MemoryScope) -> bool:
        """True only if provider-owned scoped state has been invalidated."""
        ...
