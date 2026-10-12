"""Host-owned, versioned research memory contracts. No credentials or KV tensors."""
from dataclasses import dataclass
from typing import Optional

from ..memory_v18 import MemoryRecord, _id


@dataclass(frozen=True)
class MemoryScope:
    tenant_id: str
    agent_id: str
    context: str

    def __post_init__(self):
        for name in ('tenant_id', 'agent_id', 'context'):
            _id(getattr(self, name), name)


@dataclass(frozen=True)
class MemoryRequest:
    scope: MemoryScope
    query: str
    limit: int = 5
    mode: str = 'lexical'
    max_context_chars: int = 8192

    def __post_init__(self):
        if type(self.scope) is not MemoryScope:
            raise ValueError('host-owned scope required')
        if type(self.query) is not str or not 1 <= len(self.query) <= 256:
            raise ValueError('bounded query required')
        if type(self.limit) is not int or not 1 <= self.limit <= 20:
            raise ValueError('limit must be 1..20')
        if self.mode not in ('lexical', 'semantic', 'adaptive'):
            raise ValueError('unsupported retrieval mode')
        if type(self.max_context_chars) is not int or not 256 <= self.max_context_chars <= 32768:
            raise ValueError('context budget must be 256..32768 characters')


@dataclass(frozen=True)
class MemoryProvenance:
    memory_id: str
    source_id: str
    source_sha256: str
    evaluator_id: Optional[str]


@dataclass(frozen=True)
class KVCacheIdentity:
    scope: MemoryScope
    model_id: str
    architecture: str
    model_revision: str
    tokenizer_revision: str
    runtime_revision: str
    quantization: str
    kv_representation: str
    attention_config: str
    prompt_sha256: str
    tokens_sha256: str
    instruction_revision: str
    adapter_revision: str
    source_digest: str

    @property
    def key(self):
        from .compatibility import identity_key
        return identity_key(self)


@dataclass(frozen=True)
class MemoryPolicyDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class MemoryInvalidationEvent:
    reason: str
    cache_purge_confirmed: bool


@dataclass(frozen=True)
class MemoryMetrics:
    queries: int = 0
    records_returned: int = 0
    prefill_fallbacks: int = 0
    retrieval_failures: int = 0
    invalidation_failures: int = 0


@dataclass(frozen=True)
class MemoryRetrievalResult:
    records: tuple[MemoryRecord, ...]
    context_text: str
    kv_status: str
    fallback_reason: str
    source_digest: str
