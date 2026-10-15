"""Execute actual agent strategy changes, not a simulated learning status."""
import importlib.util
from pathlib import Path
import unittest
from dataclasses import replace
import test_memory_agent_wiring as fixtures


class LearningDemoTests(unittest.TestCase):
    def test_actual_registered_tools_adapt_and_survive_restart(self):
        path = Path(__file__).resolve().parents[1]/'scripts/memory_learning_demo.py'
        spec = importlib.util.spec_from_file_location('memory_learning_demo', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.run()
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['host_evaluations'], 12)
        self.assertNotEqual(result['before_strategy'], result['after_strategy'])
        self.assertTrue(result['restart_retains_learning'])
        self.assertTrue(result['revocation_blocks_learned_strategy'])
        self.assertFalse(result['model_weights_trained'])


class SessionPolicyTests(unittest.TestCase):
    setUp = fixtures.MemoryAgentWiringTests.setUp
    hint = fixtures.MemoryAgentWiringTests.hint

    def test_default_policy_preserves_conflict_rejection(self):
        self.hint(normalise='lower-only')
        self.hint(normalise='trim-lower')
        self.assertEqual(len(self.session.query('email normalization')['records']), 2)
        self.assertEqual(self.bridge.run_pipeline(task_id='conflict', email_document=self.document)
                         ['verified_memory']['status'], 'conflicting_hints')

    def test_host_limit_cannot_be_expanded_by_tool_argument(self):
        self.hint(normalise='lower-only')
        self.hint(normalise='trim-lower')
        session = replace(self.session, retrieval_limit=1)
        self.assertEqual(len(session.query('email normalization', limit=20)['records']), 1)
        for limit in (True, 0, 21, '1'):
            with self.assertRaises(ValueError):
                session.query('email normalization', limit=limit)
        with self.assertRaises(ValueError):
            replace(self.session, retrieval_limit=0)
        with self.assertRaises(ValueError):
            replace(self.session, retrieval_mode='unrestricted')
