import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from nerve_awim.agent_bridge_v13 import DemoAgentBridge
from nerve_awim.learn_mcp import create_server
from nerve_awim.llm_agent_v14 import FixturePlanner
from nerve_awim.agent_learning_v12 import AgentTask


class FakeMCP:
    def __init__(self, name):
        self.tools = {}

    def tool(self):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register


class ExplicitAgentPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "memory.sqlite")
        self.bridge = DemoAgentBridge(self.db)

    def document(self):
        return json.dumps({"email": "  HELLO@EXAMPLE.ORG  "})

    def test_registered_model_plan_is_executable(self):
        self.bridge.train_fixed_fixtures()
        advice = {
            c: self.bridge.choose(c)["strategy_id"]
            for c in ("extract", "normalise")
        }
        plan = FixturePlanner().plan(advice=advice).plan
        result = self.bridge.execute_plan(
            task_id="eval", email_document=self.document(),
            extract_strategy=plan.extract_strategy,
            normalise_strategy=plan.normalise_strategy,
        )
        self.assertEqual(result["result"], "hello@example.org")
        self.assertFalse(result["feedback_written"])

    def test_bad_strategy_is_rejected_before_any_unsafe_execution(self):
        with self.assertRaises(ValueError):
            self.bridge.execute_plan(
                task_id="bad", email_document=self.document(),
                extract_strategy="__import__('os').system('echo unsafe')",
                normalise_strategy="trim-lower",
            )

    def test_explicit_execution_never_trains_on_holdout(self):
        self.bridge.train_fixed_fixtures()
        before = len(self.bridge.agent.memory.store.rated_history(
            "external-demo", "extract"))
        self.bridge.execute_plan(
            task_id="heldout", email_document=self.document(),
            extract_strategy="json-field", normalise_strategy="trim-lower",
        )
        self.assertEqual(before, len(
            self.bridge.agent.memory.store.rated_history(
                "external-demo", "extract")))

    def test_incorrect_plan_does_not_get_automatic_success(self):
        out = self.bridge.execute_plan(
            task_id="bad-choice", email_document=self.document(),
            extract_strategy="raw", normalise_strategy="lower-only",
        )
        self.assertNotEqual(out["result"], "hello@example.org")

    def test_mcp_registers_explicit_allowlisted_plan_tool(self):
        modules = {
            "mcp": types.ModuleType("mcp"),
            "mcp.server": types.ModuleType("mcp.server"),
            "mcp.server.fastmcp": types.ModuleType("mcp.server.fastmcp"),
        }
        modules["mcp.server.fastmcp"].FastMCP = FakeMCP
        with patch.dict(sys.modules, modules):
            host = create_server(db_path=self.db)
        self.assertIn("run_demo_agent_plan", host.tools)
        result = host.tools["run_demo_agent_plan"](
            task_id="wired", email_document=self.document(),
            extract_strategy="json-field",
            normalise_strategy="trim-lower",
        )
        self.assertEqual(result["result"], "hello@example.org")


if __name__ == "__main__":
    unittest.main()
