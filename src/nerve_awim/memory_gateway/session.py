"""Host-bound agent facade. Never pass its backing authority to a tool caller."""
from dataclasses import asdict, dataclass, field

from ..memory_v18 import MemoryActor
from .contracts import MemoryRequest, MemoryScope
from .gateway import MemoryGateway


@dataclass(frozen=True)
class BoundMemorySession:
    _gateway: MemoryGateway = field(repr=False)
    _actor: MemoryActor = field(repr=False)
    _scope: MemoryScope = field(repr=False)
    can_read: bool = True
    can_propose: bool = True

    def __post_init__(self):
        if (type(self._gateway) is not MemoryGateway or type(self._actor) is not MemoryActor
                or type(self._scope) is not MemoryScope
                or type(self.can_read) is not bool or type(self.can_propose) is not bool):
            raise TypeError('trusted gateway, actor, scope and explicit permissions required')
        if self.can_read:
            self._gateway._require(self._actor, self._scope, 'read')
        if self.can_propose:
            self._gateway._require(self._actor, self._scope, 'propose')

    def query(self, query, limit=5):
        if not self.can_read:
            raise PermissionError('session read denied')
        result = self._gateway.retrieve(self._actor, MemoryRequest(self._scope, query, limit=limit))
        return {'records': [asdict(record) for record in result.records],
                'source_digest': result.source_digest, 'kv_status': result.kv_status,
                'fallback_reason': result.fallback_reason, 'synthetic_only': True}

    def propose(self, content, source_id):
        if not self.can_propose:
            raise PermissionError('session proposal denied')
        mid = self._gateway.propose(self._actor, scope=self._scope, content=content,
                                    source_id=source_id, kind='episodic')
        return {'memory_id': mid, 'status': 'pending', 'synthetic_only': True}

    def health(self):
        if not self.can_read:
            raise PermissionError('session read denied')
        self._gateway._require(self._actor, self._scope, 'read')
        return self._gateway.health()
