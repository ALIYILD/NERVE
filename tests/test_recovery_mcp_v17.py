import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from nerve_awim.recovery_mcp_v17 import RecoveryMCPDemo
from nerve_awim.learn_mcp import create_server


class FakeServer:
    def __init__(self, name):
        self.tools = {}

    def tool(self):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register


class MCPRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "memory.sqlite"
        self.demo = RecoveryMCPDemo(self.path)

    def test_fixed_demo_recovers_and_does_not_hide_irrecoverable_case(self):
        result = self.demo.run(policy="no_memory")
        self.assertEqual(result["synthetic_cases"], 4)
        self.assertEqual(result["completed"], 3)
        self.assertEqual(result["recovered_after_failure"], 3)
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual(result["registered_attempts"], 8)

    def test_train_then_memory_reduces_attempts_not_final_accuracy(self):
        baseline = self.demo.run(policy="no_memory")
        learned = self.demo.run(policy="memory", train_on_fixtures=True)
        self.assertEqual(learned["completed"], baseline["completed"])
        self.assertEqual(learned["new_training_observations"], 6)
        self.assertLess(learned["registered_attempts"],
                        baseline["registered_attempts"])
        self.assertEqual(learned["unresolved"], 1)
        self.assertGreaterEqual(learned["memory_used"], 3)

    def test_input_data_cannot_replace_judge_or_register_handlers(self):
        with self.assertRaises(TypeError):
            self.demo.run(policy="memory", train_on_fixtures="true")
        with self.assertRaises(ValueError):
            self.demo.run(policy="unknown")
        self.assertEqual(len(self.demo.coordinator.coordinator.registry), 6)

    def test_exposure_with_mock_mcp(self):
        modules = {
            "mcp": types.ModuleType("mcp"),
            "mcp.server": types.ModuleType("mcp.server"),
            "mcp.server.fastmcp": types.ModuleType("mcp.server.fastmcp"),
        }
        modules["mcp.server.fastmcp"].FastMCP = FakeServer
        with patch.dict(sys.modules, modules):
            server = create_server(db_path=str(self.path))
        self.assertIn("run_bounded_recovery_demo", server.tools)
        result = server.tools["run_bounded_recovery_demo"](
            policy="memory", train_on_fixtures=True)
        self.assertEqual(result["completed"], 3)
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual(result["registered_attempts"], 5)


if __name__ == "__main__":
    unittest.main()
