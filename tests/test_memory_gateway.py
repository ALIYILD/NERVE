import json
from pathlib import Path
import tempfile
import time
import unittest
from dataclasses import replace

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_retrieval_v18 import SecureMemoryRetriever
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope, MemoryRequest


class MemoryGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.authority = MemoryAuthority()
        self.ledger = TrustedMemoryLedger(Path(self.tmp.name) / 'memory.sqlite', self.authority)
        self.actor = self.authority.issue('tenant-a', 'agent-a',
            permissions=('read', 'propose', 'approve', 'delete'))
        self.reader = self.authority.issue('tenant-a', 'agent-a', permissions=('read', 'propose'))
        self.scope = MemoryScope('tenant-a', 'agent-a', 'synthetic-patient-a')
        self.gateway = MemoryGateway(self.ledger)

    def record(self, *, scope=None, content='Synthetic evidence about sorting', approve=True, **kwargs):
        scope = scope or self.scope
        mid = self.gateway.propose(self.actor, scope=scope, content=content,
                                   source_id='fixture', **kwargs)
        if approve:
            self.gateway.decide(self.actor, mid, scope=scope, approve=True, evaluator_id='frozen-fixture')
        return mid

    def retrieve(self, **kwargs):
        return self.gateway.retrieve(self.reader, MemoryRequest(self.scope, 'evidence', **kwargs))

    def test_pending_rejected_and_unprivileged_approval(self):
        mid = self.record(approve=False)
        self.assertEqual(self.retrieve().records, ())
        with self.assertRaises(PermissionError):
            self.gateway.decide(self.reader, mid, scope=self.scope, approve=True, evaluator_id='agent')
        self.gateway.decide(self.actor, mid, scope=self.scope, approve=False, evaluator_id='host')
        self.assertEqual(self.retrieve().records, ())

    def test_evidence_provenance_and_no_kv_claim(self):
        mid = self.record()
        result = self.retrieve()
        self.assertEqual(result.records[0].memory_id, mid)
        self.assertEqual(json.loads(result.context_text)['source_id'], 'fixture')
        self.assertEqual(result.kv_status, 'prefill')
        self.assertEqual(len(result.source_digest), 64)
        self.assertFalse(self.gateway.health()['runtime_restore_enabled'])
        with self.assertRaises(NotImplementedError):
            self.gateway.save_kv()
        with self.assertRaises(NotImplementedError):
            self.gateway.restore_kv()

    def test_scope_actor_forgery_and_revoked_capability(self):
        self.record()
        for scope in (replace(self.scope, tenant_id='other'), replace(self.scope, agent_id='other')):
            with self.assertRaises(PermissionError):
                self.gateway.retrieve(self.reader, MemoryRequest(scope, 'evidence'))
        with self.assertRaises(PermissionError):
            self.gateway.retrieve(replace(self.reader), MemoryRequest(self.scope, 'evidence'))
        self.gateway.revoke_actor(self.reader)
        with self.assertRaises(PermissionError):
            self.retrieve()

    def test_context_isolation_even_for_administrative_operations(self):
        other = replace(self.scope, context='synthetic-patient-b')
        mid = self.record(scope=other)
        self.assertEqual(self.retrieve().records, ())
        for call in (lambda: self.gateway.revoke(self.actor, mid, scope=self.scope, evaluator_id='host'),
                     lambda: self.gateway.delete(self.actor, mid, scope=self.scope),
                     lambda: self.record(supersedes_id=mid)):
            with self.assertRaises(LookupError):
                call()

    def test_revocation_deletion_supersession(self):
        old = self.record()
        new = self.record(content='New synthetic evidence', supersedes_id=old)
        self.assertEqual([r.memory_id for r in self.retrieve().records], [new])
        self.assertTrue(self.gateway.revoke(self.actor, new, scope=self.scope, evaluator_id='host')['cache_purge_confirmed'])
        self.assertEqual(self.retrieve().records, ())
        result = self.gateway.delete(self.actor, new, scope=self.scope)
        self.assertFalse(result['backup_erasure_verified'])
        with self.assertRaises(LookupError):
            self.ledger.status(self.reader, new)

    def test_expiry_and_context_budget(self):
        self.record(content='evidence ' * 200)
        self.assertEqual(self.retrieve(max_context_chars=256).records, ())
        mid = self.record(valid_until=int(time.time()) + 100)
        import sqlite3
        with sqlite3.connect(self.ledger.path) as con:
            con.execute('UPDATE trusted_memory_v18 SET valid_until=0 WHERE memory_id=?', (mid,))
        self.assertNotIn(mid, [r.memory_id for r in self.retrieve().records])

    def test_optional_ranking_failure_falls_back_to_authorised_text(self):
        self.record()
        self.assertEqual(self.retrieve(mode='semantic').fallback_reason, 'retrieval_backend_unavailable')
        self.assertEqual(len(self.retrieve(mode='adaptive').records), 1)

    def test_ranker_cannot_return_foreign_or_revoked_content(self):
        mid = self.record()
        stale = self.ledger.status(self.reader, mid)
        ledger, actor = self.ledger, self.actor
        class StaleRanker:
            def retrieve(self, *args, **kwargs):
                ledger.revoke(actor, mid, evaluator_id='host')
                return [stale]
        ranker = StaleRanker()
        ranker.ledger = ledger
        self.gateway.retriever = ranker
        self.assertEqual(self.retrieve().records, ())

    def test_provider_failure_cannot_reenable_cache_or_claim_erasure(self):
        class BrokenProvider:
            def health(self):
                raise RuntimeError('secret-error-payload')
            def invalidate(self, scope):
                raise OSError('disk unavailable')
        mid = self.record()
        self.gateway.provider = BrokenProvider()
        self.assertNotIn('secret', json.dumps(self.gateway.health()))
        self.assertEqual(len(self.retrieve().records), 1)
        result = self.gateway.revoke(self.actor, mid, scope=self.scope, evaluator_id='host')
        self.assertFalse(result['cache_purge_confirmed'])
        self.assertEqual(self.retrieve().records, ())
        self.assertEqual(self.gateway.metrics(self.reader, self.scope)['invalidation_failures'], 1)

    def test_restart_restores_verified_ledger_not_kv(self):
        mid = self.record()
        authority = MemoryAuthority()
        reader = authority.issue('tenant-a', 'agent-a', permissions=('read',))
        gateway = MemoryGateway(TrustedMemoryLedger(self.ledger.path, authority))
        result = gateway.retrieve(reader, MemoryRequest(self.scope, 'evidence'))
        self.assertEqual(result.records[0].memory_id, mid)
        self.assertEqual(result.kv_status, 'prefill')

    def test_corrupt_ledger_not_reported_ready_or_silently_ignored(self):
        Path(self.ledger.path).write_bytes(b'corrupt fixture')
        self.assertEqual(self.gateway.health()['status'], 'unavailable')
        with self.assertRaises(Exception):
            self.retrieve()

    def test_metrics_sanitised_and_scoped(self):
        self.record()
        self.retrieve()
        metrics = self.gateway.metrics(self.reader, self.scope)
        self.assertEqual(metrics['queries'], 1)
        self.assertNotIn('evidence', json.dumps(metrics))
        metrics['queries'] = 999
        self.assertEqual(self.gateway.metrics(self.reader, self.scope)['queries'], 1)
        with self.assertRaises(PermissionError):
            self.gateway.metrics(self.reader, replace(self.scope, tenant_id='other'))

    def test_corrupted_content_cannot_claim_original_provenance(self):
        import sqlite3
        mid = self.record()
        with sqlite3.connect(self.ledger.path) as con:
            con.execute('UPDATE trusted_memory_v18 SET content=? WHERE memory_id=?',
                        ('forged evidence', mid))
        self.assertEqual(self.retrieve().records, ())

    def test_legacy_cross_context_supersession_rejected(self):
        other = replace(self.scope, context='synthetic-patient-b')
        old = self.record(scope=other)
        candidate = self.ledger.propose(self.actor, context=self.scope.context,
            content='evidence', source_id='fixture', supersedes_id=old)
        with self.assertRaises(LookupError):
            self.gateway.decide(self.actor, candidate, scope=self.scope, approve=True, evaluator_id='host')
        self.assertEqual(self.ledger.status(self.actor, old).status, 'approved')

    def test_advisory_ranker_cannot_expand_candidate_or_output_budget(self):
        mids = [self.record() for _ in range(3)]
        records = [self.ledger.status(self.actor, mid) for mid in mids]
        class OversizedRanker:
            def retrieve(self, *args, **kwargs):
                return iter(records * 100)
        ranker = OversizedRanker()
        ranker.ledger = self.ledger
        self.gateway.retriever = ranker
        self.assertEqual(len(self.retrieve(limit=1).records), 1)

    def test_strict_bounded_requests(self):
        for changes in ({'limit': True}, {'limit': 21}, {'query': ''}, {'query': 'x'*257},
                        {'mode': 'invented'}, {'max_context_chars': 100000}):
            with self.assertRaises(ValueError):
                MemoryRequest(**dict({'scope': self.scope, 'query': 'evidence'}, **changes))

    def test_scope_quota_counts_pending_and_rejected_records(self):
        self.ledger = TrustedMemoryLedger(Path(self.tmp.name) / 'quota.sqlite', self.authority)
        self.gateway = MemoryGateway(self.ledger, max_records_per_scope=1)
        mid = self.record(approve=False)
        with self.assertRaises(ValueError):
            self.record(approve=False)
        self.gateway.decide(self.actor, mid, scope=self.scope, approve=False, evaluator_id='host')
        with self.assertRaises(ValueError):
            self.record(approve=False)
        self.gateway.delete(self.actor, mid, scope=self.scope)
        self.record(approve=False)

    def test_lazy_ranker_revocation_rechecked_after_materialisation(self):
        first, second = self.record(), self.record()
        records = [self.ledger.status(self.actor, mid) for mid in (first, second)]
        ledger, actor = self.ledger, self.actor
        class LazyRanker:
            def retrieve(self, *args, **kwargs):
                yield records[0]
                ledger.revoke(actor, first, evaluator_id='host')
                yield records[1]
        ranker = LazyRanker()
        ranker.ledger = ledger
        self.gateway.retriever = ranker
        self.assertEqual([r.memory_id for r in self.retrieve().records], [second])


if __name__ == '__main__':
    unittest.main()
