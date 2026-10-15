"""No-storage CPU provider. It never claims a cache hit."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .kv_adapter import KVCapabilities, KVHealth

if TYPE_CHECKING:
    from .contracts import KVCacheIdentity, MemoryScope


class NullKVProvider:
    def health(self) -> KVHealth:
        return KVHealth(False, "disabled")

    def capabilities(self) -> KVCapabilities:
        return KVCapabilities("null", False, False, True, False)

    def validate_identity(self, identity: KVCacheIdentity) -> bool:
        return False

    def invalidate(self, scope: MemoryScope) -> bool:
        # This provider never creates any state, so nothing remains to remove.
        return True
