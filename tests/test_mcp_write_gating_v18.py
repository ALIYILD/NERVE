import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from nerve_awim.learn_mcp import create_server


class FakeMCP:
    def __init__(self, name):
        self.tools = {}

    def tool(self):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register


def server_for(path, *, legacy=False):
    mods = {
        "mcp": types.ModuleType("mcp"),
        "mcp.server": types.ModuleType("mcp.server"),
        "mcp.server.fastmcp": types.ModuleType("mcp.server.fastmcp"),
    }
    mods["mcp.server.fastmcp"].FastMCP = FakeMCP
    env = {"NERVE_ENABLE_LEGACY_MCP_WRITES": "1"} if legacy else {}
    with patch.dict(sys.modules, mods), patch.dict(os.environ, env, clear=True):
        return create_server(db_path=str(path))


class SafeLegacyMCPWritesV18Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "m.sqlite"

    def test_unverified_record_and_rating_default_to_disabled(self):
        api = server_for(self.path)
        self.assertIn("record_experience", api.tools)
        self.assertIn("rate_experience", api.tools)
        with self.assertRaises(PermissionError):
            api.tools["record_experience"]("external", "task", "suggestion")
        with self.assertRaises(PermissionError):
            api.tools["rate_experience"]("external", "invented-id", 1.0)

    def test_explicit_trusted_local_legacy_opt_in(self):
        api = server_for(self.path, legacy=True)
        mid = api.tools["record_experience"](
            "trusted-test-agent", "planning", "summarise validated source"
        )
        self.assertEqual(
            api.tools["rate_experience"](
                "trusted-test-agent", mid, .9), "recorded")
        self.assertEqual(
            api.tools["select_evaluated_strategy"](
                "trusted-test-agent", "planning")[0]["outcome"],
            "summarise validated source",
        )

    def test_synthetic_registered_demo_still_functions_without_writes(self):
        api = server_for(self.path)
        self.assertEqual(
            api.tools["train_demo_agent_on_fixtures"]()[
                "verified_training_observations"], 8)
        self.assertEqual(
            api.tools["choose_demo_agent_strategy"](
                "extract")["strategy_id"], "json-field")


if __name__ == "__main__":
    unittest.main()
