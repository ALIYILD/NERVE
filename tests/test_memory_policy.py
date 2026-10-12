from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.adaptive_memory import OutcomeMemoryRanker
from nerve_awim.memory_gateway import MemoryGateway, MemoryRequest, MemoryScope
from nerve_awim.memory_gateway.session import BoundMemorySession


class DurableMemoryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.authority = MemoryAuthority()
        self.path = Path(self.tmp.name) / 'synthetic.sqlite'
        self.ledger = TrustedMemoryLedger(self.path, self.authority)
        self.gateway = MemoryGateway(self.ledger)
        self.host = self.authority.issue('tenant', 'agent', permissions=('read','propose','approve','delete'))
        self.reader = self.authority.issue('tenant', 'agent', permissions=('read','propose'))
        self.scope = MemoryScope('tenant', 'agent', 'synthetic-patient')

    def record(self, scope=None, approved=True):
        scope = scope or self.scope
        mid = self.gateway.propose(self.host, scope=scope, content='synthetic evidence', source_id='fixture')
        if approved:
            self.gateway.decide(self.host, mid, scope=scope, approve=True, evaluator_id='host')
        return mid

    def test_scope_revocation_survives_new_authority_and_sessions(self):
        self.record()
        result = self.gateway.revoke_scope(self.host, scope=self.scope, evaluator_id='host')
        self.assertEqual(result['records_revoked'], 1)
        authority = MemoryAuthority()
        actor = authority.issue('tenant', 'agent', permissions=('read','propose'))
        gateway = MemoryGateway(TrustedMemoryLedger(self.path, authority))
        session = BoundMemorySession(gateway, actor, self.scope)
        for operation in (lambda: session.query('evidence'), lambda: session.propose('fixture', 'fixture'), session.health):
            with self.assertRaises(PermissionError):
                operation()

    def test_revocation_does_not_affect_other_context_and_legacy_read_filters(self):
        self.record()
        other = replace(self.scope, context='synthetic-other')
        self.record(other)
        self.gateway.revoke_scope(self.host, scope=self.scope, evaluator_id='host')
        self.assertEqual(self.ledger.retrieve(self.reader, context=self.scope.context, query='evidence'), [])
        self.assertEqual(len(self.gateway.retrieve(self.reader, MemoryRequest(other,'evidence')).records), 1)

    def test_legacy_writes_and_late_approval_cannot_reanimate_scope(self):
        pending = self.record(approved=False)
        self.gateway.revoke_scope(self.host, scope=self.scope, evaluator_id='host')
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.propose(self.host, context=self.scope.context, content='synthetic evidence', source_id='fixture')
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.decide(self.host, pending, approve=True, evaluator_id='host')
        self.assertEqual(self.ledger.status(self.host, pending).status, 'pending')

    def test_scope_delete_cascades_current_utility_and_keeps_tombstone(self):
        mid = self.record()
        ranker = OutcomeMemoryRanker(self.ledger, evaluator=lambda *_: True, evaluator_revision='fixture')
        ranker.observe(self.host, memory_id=mid, episode_id='episode', task={'fixture':1}, output='synthetic')
        result = self.gateway.delete_scope(self.host, scope=self.scope)
        self.assertEqual(result['records_deleted'], 1)
        self.assertFalse(result['backup_erasure_verified'])
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0], 0)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_scope_revocations_v1').fetchone()[0], 1)
        with self.assertRaises(PermissionError):
            self.gateway.retrieve(self.reader, MemoryRequest(self.scope,'evidence'))

    def test_admin_can_delete_record_after_scope_revocation(self):
        mid = self.record()
        self.gateway.revoke_scope(self.host, scope=self.scope, evaluator_id='host')
        self.gateway.delete(self.host, mid, scope=self.scope)
        with self.assertRaises(LookupError):
            self.ledger.status(self.host, mid)

    def test_admin_required_and_cross_tenant_denied(self):
        for method in (lambda actor,scope: self.gateway.revoke_scope(actor,scope=scope,evaluator_id='host'),
                       lambda actor,scope: self.gateway.delete_scope(actor,scope=scope),
                       lambda actor,scope: self.gateway.audit_events(actor,scope=scope)):
            with self.assertRaises(PermissionError):
                method(self.reader,self.scope)
            with self.assertRaises(PermissionError):
                method(self.host,replace(self.scope,tenant_id='other'))

    def test_failed_provider_purge_persists_denial_and_sanitised_audit(self):
        class Broken:
            def invalidate(self,scope):
                raise RuntimeError('secret fixture error must not log')
        self.gateway.provider = Broken()
        self.record()
        result = self.gateway.revoke_scope(self.host,scope=self.scope,evaluator_id='host')
        self.assertFalse(result['cache_purge_confirmed'])
        events = self.gateway.audit_events(self.host,scope=self.scope)
        self.assertIn('provider_invalidation_failed',[e['event'] for e in events])
        self.assertTrue(all(set(e)=={'trace_id','event','status','created_at'} for e in events))
        encoded = json.dumps(events)
        for sentinel in ('synthetic-patient','tenant','secret fixture','synthetic evidence'):
            self.assertNotIn(sentinel, encoded)
        with self.assertRaises(PermissionError):
            self.gateway.retrieve(self.reader,MemoryRequest(self.scope,'evidence'))

    def test_repeat_scope_operations_idempotent(self):
        self.record()
        self.gateway.revoke_scope(self.host,scope=self.scope,evaluator_id='host')
        self.assertEqual(self.gateway.revoke_scope(self.host,scope=self.scope,evaluator_id='host')['records_revoked'],0)
        self.gateway.delete_scope(self.host,scope=self.scope)
        self.assertEqual(self.gateway.delete_scope(self.host,scope=self.scope)['records_deleted'],0)


    def test_source_revoke_and_audit_are_atomic_on_sqlite_failure(self):
        mid = self.record()
        with sqlite3.connect(self.path) as con:
            con.execute("CREATE TRIGGER fail_source_audit BEFORE INSERT ON memory_lifecycle_audit_v1 WHEN NEW.event='source_revoked' BEGIN SELECT RAISE(ABORT,'synthetic audit failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.gateway.revoke(self.host, mid, scope=self.scope, evaluator_id='host')
        self.assertEqual(self.ledger.status(self.host, mid).status, 'approved')
        self.assertEqual(self.gateway.audit_events(self.host, scope=self.scope), [])
        with sqlite3.connect(self.path) as con:
            con.execute('DROP TRIGGER fail_source_audit')
        self.gateway.revoke(self.host, mid, scope=self.scope, evaluator_id='host')
        self.assertEqual(self.ledger.status(self.host, mid).status, 'revoked')
        self.assertEqual(self.gateway.audit_events(self.host, scope=self.scope)[0]['event'], 'source_revoked')

    def test_policy_reads_do_not_recreate_missing_database(self):
        self.path.unlink()
        for operation in (lambda: self.gateway.policy.is_revoked(self.scope),
                          lambda: self.gateway.policy.events(self.scope),
                          lambda: self.gateway.retrieve(self.reader, MemoryRequest(self.scope, 'evidence'))):
            with self.assertRaises(sqlite3.Error):
                operation()
            self.assertFalse(self.path.exists())

    def test_late_ranker_legacy_delete_cleans_utility_without_other_scope_loss(self):
        mid = self.record()
        other_scope = replace(self.scope, context='synthetic-other')
        other = self.record(other_scope)
        ranker = OutcomeMemoryRanker(self.ledger, evaluator=lambda *_: True, evaluator_revision='fixture')
        for index, memory in enumerate((mid, other)):
            ranker.observe(self.host, memory_id=memory, episode_id='episode'+str(index),
                           task={'synthetic': index}, output='synthetic')
        self.ledger.forget(self.host, mid)
        self.gateway.delete_scope(self.host, scope=self.scope)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT memory FROM memory_utility').fetchall(), [(other,)])

    def test_existing_ranker_gains_cleanup_when_gateway_is_installed(self):
        path = Path(self.tmp.name)/'legacy-first.sqlite'
        ledger = TrustedMemoryLedger(path, self.authority)
        ranker = OutcomeMemoryRanker(ledger, evaluator=lambda *_: True, evaluator_revision='fixture')
        mid = ledger.propose(self.host, context=self.scope.context, content='synthetic evidence', source_id='fixture')
        ledger.decide(self.host, mid, approve=True, evaluator_id='host')
        ranker.observe(self.host, memory_id=mid, episode_id='episode', task={'synthetic': 1}, output='synthetic')
        with sqlite3.connect(path) as con:
            self.assertFalse(con.execute("SELECT 1 FROM sqlite_master WHERE name='memory_utility_delete_v1'").fetchone())
        MemoryGateway(ledger)
        ledger.forget(self.host, mid)
        with sqlite3.connect(path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0], 0)

    def test_gateway_without_ranker_legacy_delete_still_works(self):
        mid = self.record()
        self.ledger.forget(self.host, mid)
        with self.assertRaises(LookupError):
            self.ledger.status(self.host, mid)


if __name__ == '__main__':
    unittest.main()
