"""Registration fixture tests; real SDK/wire smoke requires optional mcp SDK."""
import inspect
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from nerve_awim.learn_mcp import create_server
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.session import BoundMemorySession
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


class FakeMCP:
    def __init__(self, name):
        self.tools = {}

    def tool(self):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register


class MemoryGatewayMCPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.authority = MemoryAuthority()
        self.actor = self.authority.issue('research', 'agent', permissions=('read', 'propose'))
        self.reviewer = self.authority.issue('research', 'agent', permissions=('read', 'approve'))
        self.scope = MemoryScope('research', 'agent', 'synthetic')
        self.gateway = MemoryGateway(TrustedMemoryLedger(Path(self.tmp.name)/'verified.sqlite', self.authority))

    def server(self, session=None):
        mods = {name: types.ModuleType(name) for name in ('mcp', 'mcp.server', 'mcp.server.fastmcp')}
        mods['mcp.server.fastmcp'].FastMCP = FakeMCP
        with patch.dict(sys.modules, mods), patch.dict(os.environ, {}, clear=True):
            return create_server(str(Path(self.tmp.name)/'legacy.sqlite'), memory_session=session)

    def session(self):
        return BoundMemorySession(self.gateway, self.actor, self.scope)

    def test_disabled_default_preserves_legacy_tools_and_write_gate(self):
        server = self.server()
        self.assertNotIn('verified_memory_query', server.tools)
        with self.assertRaises(PermissionError):
            server.tools['record_experience']('agent', 'task', 'outcome')

    def test_registration_rejects_forged_duck_typed_session(self):
        with self.assertRaises(TypeError):
            self.server(types.SimpleNamespace(query=lambda *a: {}, propose=lambda *a: {}, health=lambda: {}))

    def test_tools_do_not_expose_scope_approval_or_kv_parameters(self):
        tools = self.server(self.session()).tools
        self.assertEqual(set(inspect.signature(tools['verified_memory_query']).parameters), {'query', 'limit'})
        self.assertEqual(set(inspect.signature(tools['propose_verified_experience']).parameters), {'content', 'source_id'})
        self.assertEqual(set(inspect.signature(tools['verified_memory_health']).parameters), set())
        added = set(tools) - set(self.server().tools)
        self.assertEqual(added, {'verified_memory_query', 'propose_verified_experience', 'verified_memory_health'})
        self.assertFalse(any('approve' in name or 'kv' in name for name in added))
        with self.assertRaises(TypeError):
            tools['verified_memory_query']('example', tenant='foreign')

    def test_proposal_pending_until_independent_review(self):
        tools = self.server(self.session()).tools
        proposed = tools['propose_verified_experience']('calibration example', 'fixture')
        mid = proposed['memory_id']
        self.assertEqual(self.gateway.ledger.status(self.actor, mid).status, 'pending')
        self.assertNotIn(mid, str(tools['verified_memory_query']('calibration')))
        self.gateway.decide(self.reviewer, mid, scope=self.scope, approve=True, evaluator_id='host-fixture')
        self.assertIn(mid, str(tools['verified_memory_query']('calibration')))
        self.gateway.revoke(self.reviewer, mid, scope=self.scope, evaluator_id='host-fixture')
        self.assertNotIn(mid, str(tools['verified_memory_query']('calibration')))

    def test_revoked_capability_blocks_each_tool(self):
        tools = self.server(self.session()).tools
        self.authority.revoke(self.actor)
        for name, args in [('verified_memory_query', ('calibration',)),
                           ('propose_verified_experience', ('calibration example', 'fixture')),
                           ('verified_memory_health', ())]:
            with self.assertRaises(PermissionError):
                tools[name](*args)

    def test_invalid_inputs_rejected_before_session(self):
        tools = self.server(self.session()).tools
        for query, limit in [('', 5), ('x'*257, 5), ('x', 0), ('x', True), ('x', 21)]:
            with self.assertRaises(ValueError):
                tools['verified_memory_query'](query, limit)
        for content, source in [('', 'fixture'), ('x'*2049, 'fixture'), ('x', ''), ('x', 'a'*97)]:
            with self.assertRaises(ValueError):
                tools['propose_verified_experience'](content, source)

    def test_existing_demo_tools_receive_same_bound_session(self):
        session = self.session()
        from nerve_awim.agent_bridge_v13 import DemoAgentBridge
        with patch('nerve_awim.learn_mcp.DemoAgentBridge', wraps=DemoAgentBridge) as bridge:
            tools = self.server(session).tools
        self.assertIs(bridge.call_args.kwargs['memory_session'], session)
        tools['train_demo_agent_on_fixtures']()
        result = tools['run_demo_agent_pipeline']('synthetic-mcp', '{"email":"EXAMPLE@EXAMPLE.COM"}')
        self.assertIn('verified_memory', result)
        self.assertEqual(result['outcome_memory']['status'], 'pending')

    def test_default_demo_execution_keeps_original_shape(self):
        tools = self.server().tools
        tools['train_demo_agent_on_fixtures']()
        result = tools['run_demo_agent_pipeline']('synthetic-default', '{"email":"EXAMPLE@EXAMPLE.COM"}')
        self.assertNotIn('verified_memory', result)
        self.assertNotIn('outcome_memory', result)

    def test_cli_requires_paired_trusted_launcher_arguments(self):
        from nerve_awim.learn_mcp import main
        for args in (['--memory-config', 'config.json'], ['--memory-subject', 'operator']):
            with patch('sys.stderr'), patch('nerve_awim.learn_mcp.create_server') as server:
                with self.assertRaises(SystemExit) as error:
                    main(args)
                self.assertEqual(error.exception.code, 2)
                server.assert_not_called()

    def test_cli_subject_resolution_is_host_configured(self):
        from nerve_awim.learn_mcp import main
        session = self.session()
        with patch('nerve_awim.memory_gateway.runtime.load_runtime', return_value=types.SimpleNamespace(
                sessions={'allowed-host': session})) as loader:
            with patch('nerve_awim.learn_mcp.create_server') as server:
                main(['--memory-config', 'trusted.json', '--memory-subject', 'allowed-host'])
                server.assert_called_once_with(memory_session=session)
                server.return_value.run.assert_called_once_with()
                loader.assert_called_once_with('trusted.json', required_subject='allowed-host')
            with patch('sys.stderr'), patch('nerve_awim.learn_mcp.create_server') as server:
                with self.assertRaises(SystemExit):
                    main(['--memory-config', 'trusted.json', '--memory-subject', 'foreign'])
                server.assert_not_called()

    def test_cli_default_and_invalid_configuration(self):
        from nerve_awim.learn_mcp import main
        with patch('nerve_awim.learn_mcp.create_server') as server:
            main([])
            server.assert_called_once_with(memory_session=None)
        with patch('nerve_awim.memory_gateway.runtime.load_runtime', side_effect=ValueError('bad')):
            with patch('sys.stderr'), patch('nerve_awim.learn_mcp.create_server') as server:
                with self.assertRaises(SystemExit):
                    main(['--memory-config', 'bad.json', '--memory-subject', 'host'])
                server.assert_not_called()

    def test_cli_expected_failures_do_not_disclose_exception_details(self):
        import io
        import sqlite3
        from nerve_awim.learn_mcp import main
        errors = (ValueError, sqlite3.OperationalError, ImportError, RuntimeError, OSError)
        for error in errors:
            for target, args in [
                    ('nerve_awim.memory_gateway.runtime.load_runtime', ['--memory-config', 'trusted.json', '--memory-subject', 'host']),
                    ('nerve_awim.learn_mcp.create_server', [])]:
                stderr = io.StringIO()
                with patch(target, side_effect=error('private-token /sensitive/path')):
                    with patch('sys.stderr', stderr), self.assertRaises(SystemExit) as raised:
                        main(args)
                self.assertEqual(raised.exception.code, 2)
                self.assertIn('memory MCP startup or runtime unavailable', stderr.getvalue())
                self.assertNotIn('private-token', stderr.getvalue())
                self.assertNotIn('/sensitive/path', stderr.getvalue())
        with patch('nerve_awim.learn_mcp.create_server') as server:
            server.return_value.run.side_effect = RuntimeError('secret-runtime')
            stderr = io.StringIO()
            with patch('sys.stderr', stderr), self.assertRaises(SystemExit):
                main([])
            self.assertNotIn('secret-runtime', stderr.getvalue())

    def test_cli_does_not_swallow_process_interrupts(self):
        from nerve_awim.learn_mcp import main
        with patch('nerve_awim.learn_mcp.create_server', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                main([])
