import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import test_memory_gateway as fixtures
from nerve_awim.memory_gateway import MemoryGateway
from nerve_awim.memory_gateway.automation import AutomaticLearningRun
from nerve_awim.memory_gateway.learning import VerifiedOutcomeLearning
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.agent_bridge_v13 import DemoAgentBridge


class AutomaticLearningTests(unittest.TestCase):
    setUp = fixtures.MemoryGatewayTests.setUp
    record = fixtures.MemoryGatewayTests.record

    def prepare(self, evaluator=None):
        self.mid = self.record(content=json.dumps({'schema': 'nerve-demo-strategy-v1',
            'task': 'email-normalization', 'extract': 'json-field', 'normalise': 'trim-lower'}))
        self.learning = VerifiedOutcomeLearning(self.gateway, self.actor, self.scope,
            evaluator or (lambda record, task, output: output == task['expected']), 'host-v1')
        self.agent_db = Path(self.tmp.name) / 'agent.sqlite'

    def runner(self, run='run-a', **kwargs):
        return AutomaticLearningRun(self.learning, self.reader, self.agent_db, run, **kwargs)

    def task(self, n=0):
        return {'document': json.dumps({'email': f'  USER{n}@EXAMPLE.ORG  '}),
                'expected': f'user{n}@example.org'}

    def test_actual_registered_execution_and_sanitized_storage(self):
        self.prepare()
        result = self.runner().execute('episode-1', self.task())
        self.assertEqual(result['status'], 'judged')
        self.assertIs(result['success'], True)
        self.assertEqual(result['strategies'], {'extract': 'json-field', 'normalise': 'trim-lower'})
        self.assertNotIn('result', result)
        with sqlite3.connect(self.ledger.path) as con:
            rows = repr(con.execute('SELECT * FROM memory_automatic_episodes_v1').fetchall())
            self.assertNotIn('USER0', rows)
            self.assertEqual(con.execute('SELECT success FROM memory_utility').fetchone()[0], 1)

    def test_replay_same_episode_and_renamed_document_across_runs(self):
        self.prepare()
        self.runner().execute('episode-1', self.task())
        for episode, task in [('episode-1', self.task(1)), ('renamed', self.task())]:
            with self.assertRaises(sqlite3.IntegrityError):
                self.runner('other').execute(episode, task)
        task = self.task()
        task['expected'] = 'changed-label'
        with self.assertRaises(sqlite3.IntegrityError):
            self.runner('third').execute('third-episode', task)

    def test_restart_preserves_budget_and_immutable_configuration(self):
        self.prepare()
        self.runner(max_episodes=1).execute('episode-1', self.task())
        authority = MemoryAuthority()
        reviewer = authority.issue('tenant-a', 'agent-a', permissions=('read', 'approve'))
        self.reader = authority.issue('tenant-a', 'agent-a', permissions=('read',))
        gateway = MemoryGateway(TrustedMemoryLedger(self.ledger.path, authority))
        self.learning = VerifiedOutcomeLearning(gateway, reviewer, self.scope, lambda *args: True, 'host-v1')
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.runner(max_episodes=1).execute('episode-2', self.task(1))
        with self.assertRaisesRegex(ValueError, 'configuration'):
            self.runner(max_episodes=2)

    def test_failure_streak_stops_and_success_resets(self):
        self.prepare()
        runner = self.runner(max_failures=2)
        bad = self.task(); bad['expected'] = 'wrong'
        self.assertFalse(runner.execute('bad', bad)['success'])
        self.assertTrue(runner.execute('good', self.task(1))['success'])
        for n in (2, 3):
            task = self.task(n); task['expected'] = 'wrong'
            runner.execute(f'bad-{n}', task)
        with self.assertRaisesRegex(ValueError, 'budget'):
            runner.execute('stopped', self.task(4))

    def test_invalid_input_does_not_reserve_budget(self):
        self.prepare()
        runner = self.runner(max_episodes=1)
        for task in ({}, {'document': 'x' * 513}, {'document': 'ok', 'field': float('nan')}, {'document': 'ok', 'field': object()}):
            with self.assertRaises(ValueError):
                runner.execute('invalid', task)
        self.assertTrue(runner.execute('valid', self.task())['success'])

    def test_no_evidence_does_not_credit_fallback(self):
        self.prepare()
        self.gateway.revoke(self.actor, self.mid, scope=self.scope, evaluator_id='host')
        result = self.runner().execute('no-evidence', self.task())
        self.assertEqual(result['status'], 'no_evidence')
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0], 0)

    def test_revoked_reader_denied_before_reservation(self):
        self.prepare()
        runner = self.runner()
        self.gateway.revoke_actor(self.reader)
        with self.assertRaises(PermissionError):
            runner.execute('denied', self.task())
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT claimed FROM memory_automatic_runs_v1').fetchone()[0], 0)

    def test_source_revocation_during_execution_never_credits(self):
        self.prepare()
        real = DemoAgentBridge.run_pipeline
        def revoke(bridge, **kwargs):
            result = real(bridge, **kwargs)
            self.gateway.revoke(self.actor, self.mid, scope=self.scope, evaluator_id='host')
            return result
        with patch.object(DemoAgentBridge, 'run_pipeline', revoke):
            result = self.runner().execute('revoked', self.task())
        self.assertIn(result['status'], ('execution_failed', 'memory_unavailable'))
        self.assertIsNone(result['success'])
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0], 0)

    def test_interrupted_claim_is_never_reexecuted(self):
        self.prepare()
        runner = self.runner()
        with patch.object(DemoAgentBridge, 'run_pipeline', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                runner.execute('crash', self.task())
        restored = self.runner()
        with self.assertRaisesRegex(ValueError, 'pending'):
            restored.execute('different', self.task(1))
        with self.assertRaises(sqlite3.IntegrityError):
            self.runner('new-run').execute('renamed', self.task())

    def test_failed_evaluator_is_consumed_without_credit(self):
        self.prepare(lambda *args: 'yes')
        result = self.runner().execute('episode', self.task())
        self.assertEqual(result['status'], 'evaluator_failed')
        self.assertIsNone(result['success'])

    def test_ranker_fallback_does_not_execute_or_credit(self):
        self.prepare()
        def unavailable(*args, **kwargs):
            raise RuntimeError('offline')
        self.learning.ranker.rank = unavailable
        with patch.object(DemoAgentBridge, 'run_pipeline', side_effect=AssertionError('must not execute')):
            result = self.runner().execute('fallback', self.task())
        self.assertEqual(result['status'], 'no_evidence')

    def test_reader_revocation_during_evaluation_removes_credit(self):
        def revoke(*args):
            self.gateway.revoke_actor(self.reader)
            return True
        self.prepare(revoke)
        result = self.runner().execute('revoke-reader', self.task())
        self.assertEqual(result['status'], 'memory_unavailable')
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT status,success FROM memory_utility').fetchone(),
                             ('memory_unavailable', None))

    def test_status_and_source_deletion_do_not_reset_claims(self):
        self.prepare()
        runner = self.runner(max_episodes=1)
        runner.execute('episode', self.task())
        self.gateway.delete(self.actor, self.mid, scope=self.scope)
        state = runner.status()
        self.assertEqual(state['consumed'], 1)
        self.assertEqual(state['stop_reason'], 'episode_budget')
        with self.assertRaises(sqlite3.IntegrityError):
            self.runner('new-run').execute('new-name', self.task())

    def test_invalid_hint_never_falls_back_to_legacy_execution(self):
        self.prepare()
        self.gateway.revoke(self.actor, self.mid, scope=self.scope, evaluator_id='host')
        self.record(content='email normalization malformed strategy')
        with patch.object(DemoAgentBridge, '_run_default', side_effect=AssertionError('forbidden fallback')):
            result = self.runner().execute('invalid-hint', self.task())
        self.assertEqual(result['status'], 'execution_failed')
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0], 0)

    def test_atomic_concurrent_reservation_limits_execution(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        self.prepare()
        runner = self.runner()
        entered, proceed = Event(), Event()
        real = DemoAgentBridge.run_pipeline
        def pause(bridge, **kwargs):
            entered.set()
            self.assertTrue(proceed.wait(5))
            return real(bridge, **kwargs)
        with patch.object(DemoAgentBridge, 'run_pipeline', pause), ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(runner.execute, 'first', self.task())
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaisesRegex(ValueError, 'pending'):
                    self.runner().execute('second', self.task(1))
            finally:
                proceed.set()
            self.assertTrue(first.result()['success'])
        self.assertEqual(runner.status()['consumed'], 1)

    def test_selected_source_snapshot_cannot_change_before_feedback(self):
        from hashlib import sha256
        self.prepare()
        runner = self.runner()
        original = self.learning.observe
        def changed(*args, **kwargs):
            content = json.dumps({'schema':'nerve-demo-strategy-v1','task':'email-normalization',
                                  'extract':'json-field','normalise':'lower-only'})
            with sqlite3.connect(self.ledger.path) as con:
                con.execute('UPDATE trusted_memory_v18 SET content=?,source_sha256=? WHERE memory_id=?',
                            (content, sha256(content.encode()).hexdigest(), self.mid))
            return original(*args, **kwargs)
        with patch.object(self.learning, 'observe', side_effect=changed):
            result = runner.execute('changed', self.task())
        self.assertEqual(result['status'], 'execution_failed')
        self.assertIsNone(result['success'])
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0], 0)

    def test_durable_run_quota_allows_existing_restart(self):
        self.prepare()
        self.runner()
        with sqlite3.connect(self.ledger.path) as con:
            con.execute('''WITH RECURSIVE numbers(n) AS (
                SELECT 1 UNION ALL SELECT n+1 FROM numbers WHERE n<127)
                INSERT INTO memory_automatic_runs_v1
                SELECT 'tenant-a','agent-a','fixture-'||n,'{}',1,1,0,0 FROM numbers''')
        self.assertEqual(self.runner().status()['consumed'], 0)
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'automatic_run_quota_reached'):
            self.runner('overflow')
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_automatic_runs_v1').fetchone()[0], 128)

    def test_durable_episode_quota_covers_failed_and_pending_claims(self):
        self.prepare()
        self.runner()
        with sqlite3.connect(self.ledger.path) as con:
            con.execute('''WITH RECURSIVE numbers(n) AS (
                SELECT 1 UNION ALL SELECT n+1 FROM numbers WHERE n<10000)
                INSERT INTO memory_automatic_episodes_v1
                SELECT 'tenant-a','agent-a','fixture-run','fixture-'||n,'hash-'||n,
                    CASE WHEN n%2=0 THEN 'execution_failed' ELSE 'pending' END,NULL,NULL
                FROM numbers''')
        restored = self.runner()
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'automatic_episode_quota_reached'):
            restored.execute('overflow', self.task())
        self.assertEqual(restored.status()['consumed'], 0)
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM memory_automatic_episodes_v1').fetchone()[0], 10000)

    def test_context_changes_cannot_reuse_run_or_document(self):
        from dataclasses import replace
        self.prepare()
        self.runner().execute('first', self.task())
        self.learning = VerifiedOutcomeLearning(MemoryGateway(self.ledger), self.actor,
            replace(self.scope, context='other-context'), lambda *args: True, 'host-v1')
        with self.assertRaisesRegex(ValueError, 'configuration mismatch'):
            self.runner()
        with self.assertRaises(sqlite3.IntegrityError):
            self.runner('other-run').execute('renamed', self.task())
