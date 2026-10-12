"""Verified text gateway; KV runtime admission deliberately remains closed.

Only trusted in-process hosts receive this object. Use the authenticated service
for remote callers. Evidence is data, never a system/developer instruction.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import sqlite3
from pathlib import Path
from itertools import islice
from threading import RLock
import time

from ..memory_retrieval_v18 import SecureMemoryRetriever
from .contracts import MemoryMetrics, MemoryRequest, MemoryScope
from .contracts import MemoryRetrievalResult
from .null_kv_adapter import NullKVProvider
from .lifecycle import install_quota, QUOTA_ERROR
from .policy import DurableMemoryPolicy, REVOKED_ERROR
from ..memory_v18 import _id


class MemoryGateway:
    def __init__(self, ledger, *, retriever=None, provider=None, max_records_per_scope=1000):
        if type(max_records_per_scope) is not int or not 1 <= max_records_per_scope <= 10000:
            raise ValueError('scope quota must be 1..10000 records')
        self.ledger = ledger
        self.max_records_per_scope = max_records_per_scope
        self.retriever = retriever or SecureMemoryRetriever(ledger)
        if self.retriever.ledger is not ledger:
            raise ValueError('retriever must use the authoritative ledger')
        install_quota(self.ledger.path, max_records_per_scope)
        self.policy = DurableMemoryPolicy(self.ledger.path)
        self.provider = provider or NullKVProvider()
        self._lock = RLock()
        self._metrics = {}

    def _require(self, actor, scope, permission, *, allow_revoked=False):
        self.ledger.authority.require(actor, permission)
        if type(scope) is not MemoryScope or (scope.tenant_id, scope.agent_id) != (
                actor.tenant_id, actor.agent_id):
            raise PermissionError('scope denied')
        if not allow_revoked and self.policy.is_revoked(scope):
            raise PermissionError('scope has been revoked')

    def _count(self, scope, name, amount=1):
        # Bounded to prevent untrusted context strings growing telemetry forever.
        if scope not in self._metrics:
            if len(self._metrics) >= 1024:
                return
            self._metrics[scope] = asdict(MemoryMetrics())
        self._metrics[scope][name] += amount

    def retrieve(self, actor, request):
        if type(request) is not MemoryRequest:
            raise TypeError('typed memory request required')
        with self._lock:
            self._require(actor, request.scope, 'read')
            self._count(request.scope, 'queries')
            reason = 'kv_runtime_unverified'
            try:
                records = self.retriever.retrieve(
                    actor, context=request.scope.context, query=request.query,
                    limit=request.limit, mode=request.mode)
            except PermissionError:
                raise
            except Exception:
                # Optional ranking outage falls back to the SAME scoped ledger.
                self._count(request.scope, 'retrieval_failures')
                records = self.ledger.retrieve(actor, context=request.scope.context,
                                              query=request.query, limit=request.limit)
                reason = 'retrieval_backend_unavailable'
            # Materialise bounded advisory IDs BEFORE the authoritative snapshot.
            # A lazy ranker can revoke an earlier candidate during enumeration.
            identifiers = list(dict.fromkeys(record.memory_id for record in islice(records, 20)))
            self._require(actor, request.scope, 'read')
            allowed = {}
            if identifiers:
                placeholders = ','.join('?' for _ in identifiers)
                with sqlite3.connect(self.ledger.path) as con:
                    rows = con.execute('''SELECT * FROM trusted_memory_v18
                        WHERE tenant_id=? AND agent_id=? AND context=? AND status='approved'
                        AND (valid_until IS NULL OR valid_until>?) AND memory_id IN ('''
                        + placeholders + ')', (actor.tenant_id, actor.agent_id, request.scope.context,
                                              int(time.time()), *identifiers)).fetchall()
                allowed = {row[0]: self.ledger._record(row) for row in rows}
            selected, blocks, size = [], [], 0
            for identifier in identifiers:
                current = allowed.get(identifier)
                if current is None:
                    continue
                if sha256(current.content.encode()).hexdigest() != current.source_sha256:
                    continue
                if any(x.memory_id == current.memory_id for x in selected):
                    continue
                block = json.dumps({'memory_id': current.memory_id, 'source_id': current.source_id,
                                    'source_sha256': current.source_sha256, 'evidence': current.content},
                                   ensure_ascii=True, sort_keys=True)
                if size + len(block) + (1 if blocks else 0) > request.max_context_chars:
                    continue
                selected.append(current)
                blocks.append(block)
                size += len(block) + (1 if len(blocks) > 1 else 0)
                if len(selected) >= request.limit:
                    break
            self._require(actor, request.scope, 'read')
            text = '\n'.join(blocks)
            digest = sha256(text.encode()).hexdigest()
            self._count(request.scope, 'records_returned', len(selected))
            self._count(request.scope, 'prefill_fallbacks')
            if not selected:
                reason = 'no_approved_context'
            return MemoryRetrievalResult(tuple(selected), text, 'prefill', reason, digest)

    def propose(self, actor, *, scope, content, source_id, kind='episodic',
                valid_until=None, supersedes_id=None):
        with self._lock:
            self._require(actor, scope, 'propose')
            if supersedes_id is not None:
                self._record_in_scope(actor, supersedes_id, scope)
            try:
                return self.ledger.propose(actor, context=scope.context, content=content,
                    source_id=source_id, kind=kind, valid_until=valid_until, supersedes_id=supersedes_id)
            except sqlite3.IntegrityError as error:
                if str(error) == REVOKED_ERROR:
                    raise PermissionError('scope has been revoked') from None
                if str(error) == QUOTA_ERROR:
                    raise ValueError('scope record quota reached') from None
                raise

    def _record_in_scope(self, actor, memory_id, scope, *, allow_revoked=False):
        self._require(actor, scope, 'read', allow_revoked=allow_revoked)
        record = self.ledger.status(actor, memory_id)
        if record.context != scope.context:
            raise LookupError('memory not found in authorised scope')
        return record

    def _invalidate(self, scope):
        try:
            confirmed = self.provider.invalidate(scope) is True
        except Exception:
            confirmed = False
        if not confirmed:
            self._count(scope, 'invalidation_failures')
            self.policy.audit(scope, 'provider_invalidation_failed', 'partial')
        return confirmed

    def decide(self, actor, memory_id, *, scope, approve, evaluator_id, score=None):
        with self._lock:
            self._require(actor, scope, 'approve')
            candidate = self._record_in_scope(actor, memory_id, scope)
            if approve and candidate.supersedes_id:
                self._record_in_scope(actor, candidate.supersedes_id, scope)
            self.ledger.decide(actor, memory_id, approve=approve, evaluator_id=evaluator_id, score=score)
            return {'status': 'approved' if approve else 'rejected',
                    'cache_purge_confirmed': self._invalidate(scope)}

    def revoke(self, actor, memory_id, *, scope, evaluator_id):
        with self._lock:
            self._require(actor, scope, 'approve')
            self._record_in_scope(actor, memory_id, scope)
            _id(evaluator_id, 'evaluator')
            self.policy.revoke_source(scope, memory_id, evaluator_id)
            return {'status': 'revoked', 'cache_purge_confirmed': self._invalidate(scope)}

    def delete(self, actor, memory_id, *, scope):
        with self._lock:
            self._require(actor, scope, 'delete', allow_revoked=True)
            self._record_in_scope(actor, memory_id, scope, allow_revoked=True)
            self.policy.delete(scope, memory_id)
            return {'status': 'deleted_from_local_ledger', 'cache_purge_confirmed': self._invalidate(scope),
                    'backup_erasure_verified': False}

    def revoke_scope(self, actor, *, scope, evaluator_id):
        """Host/admin operation: durable across processes and new capabilities."""
        with self._lock:
            self._require(actor, scope, 'approve', allow_revoked=True)
            _id(evaluator_id, 'evaluator')
            count, trace = self.policy.revoke(scope, evaluator_id)
            return {'status': 'scope_revoked', 'records_revoked': count, 'trace_id': trace,
                    'cache_purge_confirmed': self._invalidate(scope)}

    def delete_scope(self, actor, *, scope):
        """Delete local evidence/utility rows and retain a deny tombstone."""
        with self._lock:
            self._require(actor, scope, 'delete', allow_revoked=True)
            count, trace = self.policy.delete(scope)
            return {'status': 'scope_deleted', 'records_deleted': count, 'trace_id': trace,
                    'cache_purge_confirmed': self._invalidate(scope), 'backup_erasure_verified': False}

    def audit_events(self, actor, *, scope, limit=50):
        with self._lock:
            self._require(actor, scope, 'delete', allow_revoked=True)
            return self.policy.events(scope, limit)

    def revoke_actor(self, actor):
        """Trusted host only. Capability revocation does not claim cache erasure."""
        with self._lock:
            self.ledger.authority.revoke(actor)

    def metrics(self, actor, scope):
        with self._lock:
            self._require(actor, scope, 'read')
            return dict(self._metrics.get(scope, asdict(MemoryMetrics())))

    def health(self):
        try:
            kv = asdict(self.provider.health())
        except Exception:
            kv = {'available': False, 'status': 'unavailable', 'blockers': ['provider_failure']}
        try:
            with sqlite3.connect(Path(self.ledger.path).resolve().as_uri() + '?mode=ro', uri=True,
                                 timeout=0.1) as con:
                con.execute('SELECT memory_id FROM trusted_memory_v18 LIMIT 1').fetchone()
            ready = True
        except (OSError, sqlite3.Error):
            ready = False
        return {'status': 'ready' if ready else 'unavailable', 'synthetic_only': True, 'kv': kv,
                'runtime_restore_enabled': False, 'durable_kv_verified': False}

    def save_kv(self, *args, **kwargs):
        raise NotImplementedError('KV deposit requires a verified runtime connector')

    def restore_kv(self, *args, **kwargs):
        raise NotImplementedError('KV restore requires a verified runtime connector')
