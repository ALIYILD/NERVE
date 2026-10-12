"""Optional synthetic research memory gateway; no clinical deployment authority."""
from .contracts import MemoryRequest, MemoryScope, KVCacheIdentity
from .gateway import MemoryGateway

__all__ = ['MemoryGateway', 'MemoryRequest', 'MemoryScope', 'KVCacheIdentity']
