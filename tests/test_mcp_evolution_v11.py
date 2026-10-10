import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from nerve_awim.evolution_v01 import EvolutionMemory
from nerve_awim.learn_mcp import create_server


class FakeMCP:
    def __init__(self, name):
        self.name = name
        self.tools = {}

    def tool(self):
        def register(function):
            self.tools[function.__name__] = function
            return function
        return register


class MCPAdapterTests(unittest.TestCase):
    def test_mcp_exposes_scored_strategy_without_external_sdk(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "mem.sqlite")
            memory = EvolutionMemory(path)
            memory.record("a", "planning", "repeat-tested", .93)
            memory.record("a", "planning", "untested")

            mcp = types.ModuleType("mcp")
            server = types.ModuleType("mcp.server")
            fastmcp = types.ModuleType("mcp.server.fastmcp")
            fastmcp.FastMCP = FakeMCP
            with patch.dict(sys.modules, {
                "mcp": mcp, "mcp.server": server,
                "mcp.server.fastmcp": fastmcp,
            }):
                adapter = create_server(db_path=path)

            self.assertIn("select_evaluated_strategy", adapter.tools)
            results = adapter.tools["select_evaluated_strategy"](
                "a", "planning", limit=5
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["outcome"], "repeat-tested")
            self.assertEqual(
                adapter.tools["select_evaluated_strategy"]("other", "planning"),
                [],
            )

    def test_invalid_selection_limit_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = EvolutionMemory(Path(folder) / "m.sqlite")
            with self.assertRaises(ValueError):
                memory.select("a", "planning", limit=0)


if __name__ == "__main__":
    unittest.main()
