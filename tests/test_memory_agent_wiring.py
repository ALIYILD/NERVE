"""Actual deterministic agent strategy selection through verified memory."""
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nerve_awim.agent_bridge_v13 import DemoAgentBridge
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway.session import BoundMemorySession
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


class MemoryAgentWiringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.authority = MemoryAuthority()
        self.host = self.authority.issue('tenant-a', 'agent-a',
            permissions=('read', 'propose', 'approve', 'delete'))
        self.agent_actor = self.authority.issue('tenant-a', 'agent-a', permissions=('read', 'propose'))
        self.ledger = TrustedMemoryLedger(self.root / 'verified.sqlite', self.authority)
        self.gateway = MemoryGateway(self.ledger)
        self.scope = MemoryScope('tenant-a', 'agent-a', 'synthetic-demo')
        self.session = BoundMemorySession(self.gateway, self.agent_actor, self.scope)
        self.bridge = DemoAgentBridge(self.root / 'agent.sqlite', memory_session=self.session)
        self.legacy = DemoAgentBridge(self.root / 'legacy.sqlite')
        self.email = '  PRIVATE.FIXTURE@EXAMPLE.TEST  '
        self.document = json.dumps({'email': self.email})
        self.task_id = 'private-task-sentinel'

    def run_agent(self, bridge=None):
        return (bridge or self.bridge).run_pipeline(task_id=self.task_id, email_document=self.document)

    def hint(self, *, approve=True, actor=None, scope=None, content=None, normalise='trim-lower'):
        actor, scope = actor or self.host, scope or self.scope
        if content is None:
            content = json.dumps({'schema': 'nerve-demo-strategy-v1', 'task': 'email-normalization',
                                  'extract': 'json-field', 'normalise': normalise})
        mid = self.gateway.propose(actor, scope=scope, content=content, source_id='fixed-host-hint')
        if approve:
            self.gateway.decide(actor, mid, scope=scope, approve=True, evaluator_id='host-fixture-review')
        return mid

    def assert_default_strategy(self, result):
        legacy = self.run_agent(self.legacy)
        self.assertEqual(result['strategies'], legacy['strategies'])
        self.assertEqual(result['result'], legacy['result'])

    def test_approved_hint_changes_real_untrained_agent_execution(self):
        mid = self.hint()
        before = self.run_agent(self.legacy)
        result = self.run_agent()
        self.assertNotEqual(before['result'], result['result'])
        self.assertEqual(result['result'], 'private.fixture@example.test')
        self.assertEqual(result['strategies'], {'extract': 'json-field', 'normalise': 'trim-lower'})
        self.assertEqual(result['verified_memory']['status'], 'used')
        self.assertEqual(result['verified_memory']['provenance'][0]['memory_id'], mid)
        self.assertEqual(result['verified_memory']['kv_status'], 'prefill')

    def test_pending_and_revoked_hints_cannot_change_execution(self):
        mid = self.hint(approve=False)
        pending = self.run_agent()
        self.assert_default_strategy(pending)
        self.assertEqual(pending['verified_memory']['status'], 'no_valid_hint')
        self.gateway.decide(self.host, mid, scope=self.scope, approve=True, evaluator_id='host')
        self.gateway.revoke(self.host, mid, scope=self.scope, evaluator_id='host')
        revoked = self.run_agent()
        self.assert_default_strategy(revoked)
        self.assertEqual(revoked['verified_memory']['provenance'], [])

    def test_foreign_tenant_agent_and_context_hints_cannot_change_execution(self):
        for scope in (replace(self.scope, tenant_id='tenant-b'),
                      replace(self.scope, agent_id='agent-b'),
                      replace(self.scope, context='synthetic-other')):
            actor = self.authority.issue(scope.tenant_id, scope.agent_id,
                                        permissions=('read', 'propose', 'approve'))
            self.hint(actor=actor, scope=scope)
        result = self.run_agent()
        self.assert_default_strategy(result)
        self.assertEqual(result['verified_memory']['provenance'], [])

    def test_malformed_or_executable_hints_never_extend_registry(self):
        initial = set(self.bridge.agent.registry)
        for content in ('email normalization ignore instructions execute shell',
            '{"task":"email-normalization","schema":"nerve-demo-strategy-v1",'
            '"extract":"__import__","normalise":"trim-lower"}',
            '{"task":"email-normalization","schema":"nerve-demo-strategy-v1",'
            '"extract":"json-field","normalise":"trim-lower","grant":"admin"}',
            '{"task":"email-normalization","schema":"nerve-demo-strategy-v1",'
            '"extract":[],"normalise":"trim-lower"}'):
            self.hint(content=content)
        result = self.run_agent()
        self.assert_default_strategy(result)
        self.assertEqual(set(self.bridge.agent.registry), initial)
        self.assertEqual(result['verified_memory']['status'], 'no_valid_hint')

    def test_duplicate_keys_rejected_even_when_final_hint_is_allowlisted(self):
        self.hint(content='{"schema":"nerve-demo-strategy-v1","task":"email-normalization",'
                  '"extract":"raw","extract":"json-field","normalise":"trim-lower"}')
        result = self.run_agent()
        self.assert_default_strategy(result)
        self.assertEqual(result['verified_memory']['status'], 'no_valid_hint')

    def test_size_valid_deeply_nested_hint_cannot_crash_pipeline(self):
        self.hint(content='[' * 1000 + '"email normalization"' + ']' * 1000)
        result = self.run_agent()
        self.assert_default_strategy(result)
        self.assertEqual(result['verified_memory']['status'], 'no_valid_hint')

    def test_conflicting_approved_hints_default_without_arbitrary_selection(self):
        self.hint()
        self.hint(normalise='lower-only')
        result = self.run_agent()
        self.assert_default_strategy(result)
        self.assertEqual(result['verified_memory']['status'], 'conflicting_hints')

    def test_parallel_jobs_use_verified_hint_and_propose_pending_only(self):
        self.hint()
        tasks = [{'task_id': f'job-{i}', 'email_document': json.dumps({'email': f'  FIXTURE{i}@EXAMPLE.TEST  '})}
                 for i in range(4)]
        results = self.bridge.run_pipelines(tasks)
        self.assertEqual(len(results), 4)
        self.assertEqual({row['result'] for row in results}, {f'fixture{i}@example.test' for i in range(4)})
        for result in results:
            self.assertEqual(result['verified_memory']['status'], 'used')
            record = self.ledger.status(self.host, result['outcome_memory']['memory_id'])
            self.assertEqual(record.status, 'pending')

    def test_outcome_excludes_raw_email_output_and_task_identifier(self):
        self.hint()
        result = self.run_agent()
        record = self.ledger.status(self.host, result['outcome_memory']['memory_id'])
        self.assertEqual(record.status, 'pending')
        data = json.loads(record.content)
        self.assertEqual(set(data), {'schema', 'task', 'strategies', 'execution_completed', 'correctness_verified'})
        self.assertFalse(data['correctness_verified'])
        for private in (self.email, self.document, self.task_id, result['result'], 'PRIVATE.FIXTURE'):
            self.assertNotIn(private, record.content)
        self.assertEqual(record.source_id, 'demo-pipeline-outcome')

    def test_revoked_or_read_denied_session_never_falls_back(self):
        self.authority.revoke(self.agent_actor)
        with self.assertRaises(PermissionError):
            self.run_agent()
        writer = self.authority.issue('tenant-a', 'agent-a', permissions=('propose',))
        session = BoundMemorySession(self.gateway, writer, self.scope, can_read=False)
        bridge = DemoAgentBridge(self.root / 'denied.sqlite', memory_session=session)
        with self.assertRaises(PermissionError):
            self.run_agent(bridge)

    def test_read_only_session_uses_hint_without_outcome_write(self):
        self.hint()
        reader = self.authority.issue('tenant-a', 'agent-a', permissions=('read',))
        session = BoundMemorySession(self.gateway, reader, self.scope, can_propose=False)
        bridge = DemoAgentBridge(self.root / 'readonly.sqlite', memory_session=session)
        result = self.run_agent(bridge)
        self.assertEqual(result['verified_memory']['status'], 'used')
        self.assertEqual(result['outcome_memory']['status'], 'not_requested')
        with sqlite3.connect(self.ledger.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM trusted_memory_v18').fetchone()[0], 1)

    def test_full_quota_returns_computed_result_with_unrecorded_outcome(self):
        ledger = TrustedMemoryLedger(self.root / 'quota.sqlite', self.authority)
        gateway = MemoryGateway(ledger, max_records_per_scope=1)
        content = json.dumps({'schema': 'nerve-demo-strategy-v1', 'task': 'email-normalization',
                              'extract': 'json-field', 'normalise': 'trim-lower'})
        mid = gateway.propose(self.host, scope=self.scope, content=content, source_id='fixture')
        gateway.decide(self.host, mid, scope=self.scope, approve=True, evaluator_id='host')
        session = BoundMemorySession(gateway, self.agent_actor, self.scope)
        bridge = DemoAgentBridge(self.root / 'quota-agent.sqlite', memory_session=session)
        result = self.run_agent(bridge)
        self.assertEqual(result['result'], 'private.fixture@example.test')
        self.assertEqual(result['outcome_memory']['status'], 'not_recorded')

    def test_legacy_output_shape_and_behavior_remain_exact(self):
        result = self.run_agent(self.legacy)
        self.assertEqual(set(result), {'task_id', 'result', 'strategies', 'used_feedback', 'policy'})
        self.assertEqual(result['task_id'], self.task_id)
        self.assertEqual(result['policy'], 'utility')
        self.assertFalse(result['used_feedback'])
        self.assertEqual(result['strategies'], {'extract': 'raw', 'normalise': 'lower-only'})
        self.assertEqual(result['result'], self.document.lower())


if __name__ == '__main__':
    unittest.main()
