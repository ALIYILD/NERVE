"""Host-reviewed utility changes preferences without broadening access."""
import sqlite3
import unittest
from dataclasses import replace

import test_memory_gateway as fixtures
from nerve_awim.memory_gateway import MemoryGateway, MemoryRequest
from nerve_awim.memory_gateway.learning import VerifiedOutcomeLearning
from nerve_awim.memory_gateway.session import BoundMemorySession
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


class MemoryLearningTests(unittest.TestCase):
    setUp = fixtures.MemoryGatewayTests.setUp
    record = fixtures.MemoryGatewayTests.record

    def learning(self, evaluator=None, revision='host-v1'):
        # This answer key is frozen by the host, never accepted from the agent.
        expected = {n: n * 2 for n in range(100)}
        return VerifiedOutcomeLearning(self.gateway, self.actor, self.scope,
            evaluator or (lambda record, task, output: output == expected[task['case']]),
            revision, window=3)

    def observe(self, learning, mid, case, success=True):
        return learning.observe(mid, 'episode-' + str(case), {'case': case},
                                case * 2 if success else -1)

    def test_recent_verified_outcomes_reverse_preference_without_approval_changes(self):
        a, b = self.record(content='sorting a'), self.record(content='sorting b')
        learning = self.learning()
        session = learning.session(self.reader)
        for n in range(3):
            self.observe(learning, a, n)
            self.observe(learning, b, n + 10, False)
        self.assertEqual(session.query('sorting')['records'][0]['memory_id'], a)
        for n in range(3):
            self.observe(learning, a, n + 20, False)
            self.observe(learning, b, n + 30)
        self.assertEqual(session.query('sorting')['records'][0]['memory_id'], b)
        self.assertEqual(session.query('unrelated')['records'], [])
        self.assertTrue(all(self.ledger.status(self.reader, mid).status == 'approved' for mid in (a, b)))

    def test_legacy_session_remains_lexical_when_learning_is_installed(self):
        a, b = self.record(content='sorting a'), self.record(content='sorting b')
        legacy = BoundMemorySession(self.gateway, self.reader, self.scope)
        before = [r['memory_id'] for r in legacy.query('sorting')['records']]
        learning = self.learning()
        self.observe(learning, before[-1], 0)
        self.assertEqual([r['memory_id'] for r in legacy.query('sorting')['records']], before)
        self.assertEqual(learning.session(self.reader).query('sorting')['records'][0]['memory_id'], before[-1])

    def test_reviewer_is_not_exposed_to_session_and_untrusted_observation_denied(self):
        learning = self.learning()
        with self.assertRaises(PermissionError):
            learning.session(self.actor)
        other = self.authority.issue('other', 'agent-a', permissions=('read',))
        with self.assertRaises(PermissionError):
            learning.session(other)
        session = learning.session(self.reader)
        self.assertFalse(hasattr(session, 'observe'))
        with self.assertRaises(PermissionError):
            VerifiedOutcomeLearning(self.gateway, self.reader, self.scope, lambda *a: True, 'other')

    def test_exact_context_and_pending_sources_are_denied(self):
        learning = self.learning()
        foreign = self.record(scope=replace(self.scope, context='other-context'))
        pending = self.record(approve=False)
        for mid, error in ((foreign, LookupError), (pending, ValueError)):
            with self.assertRaises(error):
                self.observe(learning, mid, 0)

    def test_replay_and_renamed_task_are_consumed_without_duplicate_credit(self):
        mid, learning = self.record(), self.learning()
        self.observe(learning, mid, 0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.observe(learning, mid, 0)
        with self.assertRaises(sqlite3.IntegrityError):
            learning.observe(mid, 'renamed', {'case': 0}, 0)

    def test_nonboolean_or_failed_evaluator_never_credits(self):
        mid = self.record()
        learning = self.learning(lambda *args: 'success')
        self.assertEqual(self.observe(learning, mid, 0), {'status': 'evaluator_failed', 'success': None})
        with self.assertRaises(sqlite3.IntegrityError):
            self.observe(learning, mid, 0)

    def test_corrupted_source_denied_before_and_during_evaluation(self):
        mid = self.record()
        def corrupt(*args):
            with sqlite3.connect(self.ledger.path) as con:
                con.execute('UPDATE trusted_memory_v18 SET content=? WHERE memory_id=?', ('tampered', mid))
            return True
        learning = self.learning(corrupt)
        with self.assertRaises(ValueError):
            self.observe(learning, mid, 0)
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT status,success FROM memory_utility').fetchone(),
                             ('memory_unavailable', None))
        with self.assertRaises(ValueError):
            self.observe(learning, mid, 1)
        self.assertEqual(learning.session(self.reader).query('tampered')['records'], [])

    def test_scope_revocation_during_evaluation_cannot_credit_or_retrieve(self):
        mid = self.record()
        def revoke(*args):
            self.gateway.revoke_scope(self.actor, scope=self.scope, evaluator_id='host')
            return True
        learning = self.learning(revoke)
        session = learning.session(self.reader)
        with self.assertRaises(PermissionError):
            self.observe(learning, mid, 0)
        with self.assertRaises(PermissionError):
            session.query('evidence')
        with sqlite3.connect(self.ledger.path) as con:
            self.assertIsNone(con.execute('SELECT success FROM memory_utility').fetchone()[0])

    def test_deletion_during_evaluation_removes_utility_and_prevents_credit(self):
        mid = self.record()
        def delete(*args):
            self.gateway.delete(self.actor, mid, scope=self.scope)
            return True
        learning = self.learning(delete)
        with self.assertRaises(LookupError):
            self.observe(learning, mid, 0)
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0], 0)

    def test_expired_source_cannot_receive_credit(self):
        mid, learning = self.record(), self.learning()
        with sqlite3.connect(self.ledger.path) as con:
            con.execute('UPDATE trusted_memory_v18 SET valid_until=1 WHERE memory_id=?', (mid,))
        with self.assertRaises(ValueError):
            self.observe(learning, mid, 0)

    def test_restart_persists_utility_and_revision_change_resets_preference(self):
        a, b = self.record(content='sorting a'), self.record(content='sorting b')
        learning = self.learning()
        initial = self.gateway.retrieve(self.reader, MemoryRequest(self.scope, 'sorting')).records[0].memory_id
        preferred = b if initial == a else a
        self.observe(learning, preferred, 0)
        authority = MemoryAuthority()
        reviewer = authority.issue('tenant-a', 'agent-a', permissions=('read', 'approve'))
        reader = authority.issue('tenant-a', 'agent-a', permissions=('read',))
        ledger = TrustedMemoryLedger(self.ledger.path, authority)
        gateway = MemoryGateway(ledger)
        restored = VerifiedOutcomeLearning(gateway, reviewer, self.scope, lambda *args: True, 'host-v1')
        self.assertEqual(restored.session(reader).query('sorting')['records'][0]['memory_id'], preferred)
        newer = VerifiedOutcomeLearning(MemoryGateway(ledger), reviewer, self.scope, lambda *args: True, 'host-v2')
        self.assertEqual(newer.session(reader).query('sorting')['records'][0]['memory_id'], initial)

    def test_existing_evaluator_cannot_be_overwritten_and_raw_outcomes_not_stored(self):
        mid, learning = self.record(), self.learning()
        self.observe(learning, mid, 0)
        with self.assertRaises(ValueError):
            self.learning(revision='new')
        with sqlite3.connect(self.ledger.path) as con:
            columns = [row[1] for row in con.execute('PRAGMA table_info(memory_utility)')]
        self.assertNotIn('task', columns)
        self.assertNotIn('output', columns)
        self.assertNotIn('content', columns)

    def test_ranker_failure_falls_back_to_same_scoped_lexical_sources(self):
        mid, learning = self.record(), self.learning()
        def fail(*args, **kwargs):
            raise RuntimeError('unavailable')
        learning.ranker.rank = fail
        result = learning.session(self.reader).query('evidence')
        self.assertEqual([r['memory_id'] for r in result['records']], [mid])
        self.assertEqual(result['fallback_reason'], 'retrieval_backend_unavailable')

    def test_durable_quota_blocks_new_observations_without_trimming_replay_history(self):
        mid = self.record()
        learning = VerifiedOutcomeLearning(self.gateway, self.actor, self.scope,
            lambda *args: True, 'quota-v1', max_observations=1)
        self.observe(learning, mid, 0)
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'learning_observation_quota_reached'):
            self.observe(learning, mid, 1)
        restarted = VerifiedOutcomeLearning(MemoryGateway(self.ledger), self.actor, self.scope,
            lambda *args: True, 'quota-v1', max_observations=100)
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'learning_observation_quota_reached'):
            self.observe(restarted, mid, 2)
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0], 1)

    def test_authorised_deletion_removes_replay_history_with_source(self):
        mid, learning = self.record(), self.learning()
        self.observe(learning, mid, 0)
        with self.assertRaises(PermissionError):
            self.gateway.delete(self.reader, mid, scope=self.scope)
        with self.assertRaises(sqlite3.IntegrityError):
            self.observe(learning, mid, 0)
        self.gateway.delete(self.actor, mid, scope=self.scope)
        replacement = self.record()
        self.assertEqual(self.observe(learning, replacement, 0)['status'], 'judged')
