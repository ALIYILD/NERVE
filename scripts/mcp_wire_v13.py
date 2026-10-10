"""Real MCP SDK stdio integration smoke test for NERVE Evolution v1.3.

Requires official mcp Python SDK 2.x. Runs only fixed local demo handlers,
with a fresh temporary SQLite DB and no external model or network requests.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def returned_text(result):
    if getattr(result, "is_error", getattr(result, "isError", False)):
        raise AssertionError("MCP tool reported an error")
    content = getattr(result, "structured_content",
                      getattr(result, "structuredContent", None))
    if content is not None:
        return json.dumps(content, sort_keys=True)
    return " ".join(getattr(block, "text", "") for block in result.content)


async def smoke():
    with tempfile.TemporaryDirectory() as directory:
        # Avoid forwarding an unrelated private model credential to demo tools.
        env = dict(os.environ)
        env.pop("TYPESAFE_API_KEY", None)
        env["NERVE_LEARN_DB"] = str(Path(directory) / "mcp-demo.sqlite")
        env["NERVE_DEMO_AGENT_ID"] = "sdk-integration-demo"
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        settings = StdioServerParameters(
            command=sys.executable,
            args=["-m", "nerve_awim.learn_mcp"],
            env=env,
        )
        async with stdio_client(settings) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {tool.name for tool in
                         (await session.list_tools()).tools}
                required = {
                    "list_demo_agent_capabilities",
                    "train_demo_agent_on_fixtures",
                    "choose_demo_agent_strategy",
                    "run_demo_agent_pipeline",
                    "run_demo_agent_pipelines",
                    "select_evaluated_strategy",
                }
                if not required.issubset(names):
                    raise AssertionError("missing actual MCP tool registrations")
                trained = await session.call_tool(
                    "train_demo_agent_on_fixtures", arguments={}
                )
                if "8" not in returned_text(trained):
                    raise AssertionError("fixture training did not complete")
                record = await session.call_tool(
                    "run_demo_agent_pipeline",
                    arguments={
                        "task_id": "stdio-example",
                        "email_document": json.dumps(
                            {"email": "  HELLO@EXAMPLE.ORG  "}),
                    },
                )
                if "hello@example.org" not in returned_text(record):
                    raise AssertionError("two-stage learning was not applied")
                parallel = await session.call_tool(
                    "run_demo_agent_pipelines",
                    arguments={
                        "tasks": [
                            {
                                "task_id": "one",
                                "email_document": json.dumps(
                                    {"email": "  FIRST@EXAMPLE.ORG  "}),
                            },
                            {
                                "task_id": "two",
                                "email_document": json.dumps(
                                    {"email": "  SECOND@EXAMPLE.ORG  "}),
                            },
                        ]
                    },
                )
                text = returned_text(parallel)
                if "first@example.org" not in text \
                        or "second@example.org" not in text:
                    raise AssertionError("parallel MCP tool outputs missing")
                return {
                    "status": "pass",
                    "transport": "real SDK stdio",
                    "required_tools_discovered": len(required),
                    "fixture_training": "passed",
                    "single_pipeline": "passed",
                    "parallel_pipelines": "passed",
                    "safety_scope": "local deterministic demo only",
                }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(smoke()), indent=2, sort_keys=True))
