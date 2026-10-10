import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from nerve_awim.agent_bridge_v13 import DemoAgentBridge
from nerve_awim.learn_mcp import create_server


def document(email):
    return json.dumps({"email": email}, sort_keys=True)


class FakeMCP:
    def __init__(self, name):
        self.name = name
        self.tools = {}

    def tool(self):
        def register(handler):
            self.tools[handler.__name__] = handler
            return handler
        return register


class DemoBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "demo.sqlite")
        self.bridge = DemoAgentBridge(self.path, agent_id="agent-a")

    def test_feedback_changes_two_stage_executable_plan(self):
        source = document("  USER@EXAMPLE.COM  ")
        cold = self.bridge.run_pipeline(
            task_id="cold", email_document=source,
        )
        self.assertNotEqual(cold["result"], "user@example.com")
        learning = self.bridge.train_fixed_fixtures()
        self.assertEqual(learning["verified_training_observations"], 8)
        result = self.bridge.run_pipeline(
            task_id="post", email_document=source,
        )
        self.assertEqual(result["result"], "user@example.com")
        self.assertEqual(result["strategies"], {
            "extract": "json-field", "normalise": "trim-lower"
        })
        self.assertTrue(result["used_feedback"])

    def test_both_policies_use_same_recorded_experience(self):
        self.bridge.train_fixed_fixtures()
        source = document("  USER@EXAMPLE.ORG  ")
        good = self.bridge.run_pipeline(
            task_id="a", email_document=source, policy="utility")
        recent = self.bridge.run_pipeline(
            task_id="b", email_document=source, policy="recency")
        self.assertEqual(good["result"], "user@example.org")
        self.assertNotEqual(recent["result"], "user@example.org")
        self.assertEqual(recent["strategies"]["extract"], "raw")

    def test_parallel_pipelines_preserve_task_order(self):
        self.bridge.train_fixed_fixtures()
        output = self.bridge.run_pipelines([
            {"task_id": "last", "email_document": document("  B@EXAMPLE.COM  ")},
            {"task_id": "first", "email_document": document("  A@EXAMPLE.COM  ")},
        ])
        self.assertEqual([r["task_id"] for r in output], ["last", "first"])
        self.assertEqual([r["result"] for r in output],
                         ["b@example.com", "a@example.com"])

    def test_untrusted_memory_cannot_register_code(self):
        self.bridge.agent.memory.record(
            "agent-a", "extract", "__import__('os').system('echo test')", 1.0)
        self.bridge.train_fixed_fixtures()
        plan = self.bridge.choose("extract")
        self.assertEqual(plan["strategy_id"], "json-field")
        self.assertEqual(set(self.bridge.agent.registry), {
            ("extract", "raw"), ("extract", "json-field"),
            ("normalise", "lower-only"), ("normalise", "trim-lower"),
        })

    def test_bad_inputs_fail_without_partial_batch_result(self):
        self.bridge.train_fixed_fixtures()
        with self.assertRaises(RuntimeError):
            self.bridge.run_pipelines([
                {"task_id": "a", "email_document": document("  GOOD@TEST.ORG  ")},
                {"task_id": "b", "email_document": "not-json"},
            ])
        with self.assertRaises(ValueError):
            self.bridge.run_pipelines([
                {"task_id": "a", "email_document": document("A@X.COM")},
                {"task_id": "a", "email_document": document("B@X.COM")},
            ])
        with self.assertRaises(ValueError):
            self.bridge.run_pipeline(task_id="a", email_document="x" * 513)

    def test_restart_preserves_training_history(self):
        self.bridge.train_fixed_fixtures()
        restarted = DemoAgentBridge(self.path, agent_id="agent-a")
        result = restarted.run_pipeline(
            task_id="persist", email_document=document("  B@EXAMPLE.COM  ")
        )
        self.assertEqual(result["result"], "b@example.com")

    def test_other_agent_namespace_stays_cold(self):
        self.bridge.train_fixed_fixtures()
        other = DemoAgentBridge(self.path, agent_id="agent-b")
        self.assertFalse(other.choose("extract")["used_feedback"])
        self.assertNotEqual(other.run_pipeline(
            task_id="other", email_document=document("  B@EXAMPLE.COM  ")
        )["result"], "b@example.com")

    def test_mcp_contract_with_mock_sdk(self):
        mcp = types.ModuleType("mcp")
        server = types.ModuleType("mcp.server")
        fastmcp = types.ModuleType("mcp.server.fastmcp")
        fastmcp.FastMCP = FakeMCP
        with patch.dict(sys.modules, {
            "mcp": mcp, "mcp.server": server,
            "mcp.server.fastmcp": fastmcp
        }):
            adapter = create_server(db_path=self.path)
        self.assertIn("train_demo_agent_on_fixtures", adapter.tools)
        self.assertIn("run_demo_agent_pipeline", adapter.tools)
        self.assertIn("run_demo_agent_pipelines", adapter.tools)
        self.assertIn("choose_demo_agent_strategy", adapter.tools)
        self.assertIn("list_demo_agent_capabilities", adapter.tools)
        self.assertEqual(
            adapter.tools["train_demo_agent_on_fixtures"]()[
                "verified_training_observations"], 8)
        out = adapter.tools["run_demo_agent_pipeline"](
            "mcp-test", document("  C@TEST.ORG  "))
        self.assertEqual(out["result"], "c@test.org")
        self.assertEqual(
            adapter.tools["choose_demo_agent_strategy"]("extract")[
                "strategy_id"], "json-field"
        )

    def test_mcp_can_execute_multiple_independent_tasks(self):
        mcp = types.ModuleType("mcp")
        server = types.ModuleType("mcp.server")
        fastmcp = types.ModuleType("mcp.server.fastmcp")
        fastmcp.FastMCP = FakeMCP
        with patch.dict(sys.modules, {
            "mcp": mcp, "mcp.server": server,
            "mcp.server.fastmcp": fastmcp
        }):
            adapter = create_server(db_path=self.path)
        adapter.tools["train_demo_agent_on_fixtures"]()
        out = adapter.tools["run_demo_agent_pipelines"]([
            {"task_id": "one", "email_document": document("  A@TEST.ORG  ")},
            {"task_id": "two", "email_document": document("  B@TEST.ORG  ")},
        ])
        self.assertEqual([r["result"] for r in out],
                         ["a@test.org", "b@test.org"])


if __name__ == "__main__":
    unittest.main()
