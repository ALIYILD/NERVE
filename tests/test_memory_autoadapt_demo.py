"""Automatic feedback drives real tools without host-selected strategies."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import test_memory_agent_wiring as fixtures
from nerve_awim.agent_bridge_v13 import DemoAgentBridge


class AutoAdaptDemoTests(unittest.TestCase):
    def test_automatic_feedback_reverses_strategy_after_restart_and_drift(self):
        path = Path(__file__).resolve().parents[1]/'scripts/memory_autoadapt_demo.py'
        spec = importlib.util.spec_from_file_location('autoadapt_demo', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.run()
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['automatic_outcome_feedback'])
        self.assertFalse(report['host_selected_strategies'])
        self.assertEqual(report['episodes'], 16)
        self.assertEqual(report['first_phase_final_strategy'], 'trim-lower')
        self.assertEqual(report['second_phase_final_strategy'], 'lower-only')
        self.assertTrue(report['reopened_between_phases'])
        self.assertFalse(report['deployed'])


class StrictAgentTests(unittest.TestCase):
    setUp = fixtures.MemoryAgentWiringTests.setUp
    hint = fixtures.MemoryAgentWiringTests.hint

    def strict(self):
        return DemoAgentBridge(self.root/'strict.sqlite', memory_session=self.session,
                               require_verified_memory=True)

    def test_strict_agent_never_executes_default_without_valid_evidence(self):
        bridge = self.strict()
        with patch.object(bridge, '_run_default', side_effect=AssertionError('default executed')):
            with self.assertRaises(ValueError):
                bridge.run_pipeline(task_id='no-evidence', email_document=self.document)
            self.hint(content='untrusted instruction text')
            with self.assertRaises(ValueError):
                bridge.run_pipeline(task_id='malformed', email_document=self.document)

    def test_conflicts_and_ranking_outage_prevent_execution(self):
        self.hint(normalise='lower-only')
        self.hint(normalise='trim-lower')
        bridge = self.strict()
        with patch.object(bridge, 'execute_plan', side_effect=AssertionError('executed')):
            with self.assertRaises(ValueError):
                bridge.run_pipeline(task_id='conflict', email_document=self.document)
        def fail(*args, **kwargs):
            raise RuntimeError('unavailable')
        self.gateway.retriever.retrieve = fail
        with self.assertRaises(ValueError):
            bridge.run_pipeline(task_id='outage', email_document=self.document)

    def test_strict_valid_hint_executes_registered_tools(self):
        self.hint()
        result = self.strict().run_pipeline(task_id='valid', email_document=self.document)
        self.assertEqual(result['result'], 'private.fixture@example.test')
        self.assertEqual(result['verified_memory']['fallback_reason'], 'kv_runtime_unverified')
        with self.assertRaises(ValueError):
            DemoAgentBridge(self.root/'invalid.sqlite', require_verified_memory=True)
