"""NERVE v1.4: real MCP transport + optional live LLM strategy benchmark.

Default fixture exercises *exactly the same* orchestration but is not a
real model. --live makes a bounded number of operator-authorised chat API
calls using a private environment key. Never sends raw tasks to the LLM.
"""
import argparse
import io
import os
from unittest.mock import patch
import asyncio
import json
from pathlib import Path
import statistics
import sys
import tempfile
from time import perf_counter

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from nerve_awim.llm_agent_v14 import (
    ChatCompletionsPlanner, FixturePlanner,
)


def unpack(result):
    if getattr(result, "is_error", getattr(result, "isError", False)):
        raise RuntimeError("MCP tool failed")
    structured = getattr(result, "structured_content",
                         getattr(result, "structuredContent", None))
    if structured is not None:
        if isinstance(structured, dict) and set(structured) == {"result"}:
            return structured["result"]
        return structured
    items = [getattr(item, "text", "") for item in result.content]
    if len(items) != 1:
        raise RuntimeError("MCP response shape not recognized")
    return json.loads(items[0])


def samples(count):
    if type(count) is not int or not 1 <= count <= 12:
        raise ValueError("the public benchmark supports 1..12 fixed inputs")
    return [
        {"task_id": "case-" + str(i),
         "email_document": json.dumps(
             {"email": "  USER" + str(i) + "@EXAMPLE.ORG  "}),
         "expected": "user" + str(i) + "@example.org"}
        for i in range(count)
    ]


async def run_study(*, planner, count=4):
    test_cases = samples(count)
    # Explicitly provision a minimal process environment: no secret or
    # unrelated local variables can reach the MCP child process.
    with tempfile.TemporaryDirectory() as directory:
        environment = {
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
            "NERVE_LEARN_DB": str(Path(directory) / "data.sqlite"),
            "NERVE_DEMO_AGENT_ID": "v14-synthetic-study",
            "PYTHONUNBUFFERED": "1",
        }
        settings = StdioServerParameters(
            command=sys.executable,
            args=["-m", "nerve_awim.learn_mcp"],
            env=environment,
        )
        async with stdio_client(settings) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = {tool.name for tool in (await client.list_tools()).tools}
                required = {
                    "train_demo_agent_on_fixtures",
                    "choose_demo_agent_strategy",
                    "run_demo_agent_plan",
                }
                if not required <= tools:
                    raise RuntimeError("NERVE v1.4 MCP tool contract incomplete")
                trained = unpack(await client.call_tool(
                    "train_demo_agent_on_fixtures", arguments={}
                ))
                if trained.get("verified_training_observations") != 8:
                    raise RuntimeError("fixture calibration failed")
                guidance = {}
                for context in ("extract", "normalise"):
                    selected = unpack(await client.call_tool(
                        "choose_demo_agent_strategy",
                        arguments={"context": context, "policy": "utility"},
                    ))
                    guidance[context] = selected["strategy_id"]

                outcomes = {}
                for setting, advice in (
                        ("no_memory", None),
                        ("with_memory", guidance)):
                    successes = 0
                    timings = []
                    tokens = {"input": 0, "output": 0}
                    for i, task in enumerate(test_cases):
                        started = perf_counter()
                        # One model decision and one registered two-stage tool
                        # execution for both arms. No test feedback is written.
                        decision = planner.plan(advice=advice)
                        plan = decision.plan
                        result = unpack(await client.call_tool(
                            "run_demo_agent_plan",
                            arguments={
                                "task_id": setting + "-" + str(i),
                                "email_document": task["email_document"],
                                "extract_strategy": plan.extract_strategy,
                                "normalise_strategy": plan.normalise_strategy,
                            },
                        ))
                        successes += result["result"] == task["expected"]
                        timings.append(perf_counter() - started)
                        for field, value in (
                                ("input", decision.input_tokens),
                                ("output", decision.output_tokens)):
                            if value is not None:
                                tokens[field] += value
                    outcomes[setting] = {
                        "accuracy": successes / len(test_cases),
                        "tasks": len(test_cases),
                        "model_decisions": len(test_cases),
                        "registered_tool_stages": 2 * len(test_cases),
                        "mean_wall_seconds": round(statistics.mean(timings), 6),
                        "tokens": tokens,
                    }
                return {
                    "planner": planner.__class__.__name__,
                    "transport": "official MCP Python SDK 2 stdio",
                    "tasks_per_arm": len(test_cases),
                    "training_observations": 8,
                    "arms": outcomes,
                    "no_automatic_feedback": True,
                    "limitations": (
                        "Synthetic fixed tools and task family. Offline "
                        "fixture is not a real model; live comparison needs "
                        "separate private API configuration and cannot by "
                        "itself prove general agent learning."
                    ),
                }


class MockChatResponse:
    def __init__(self, result):
        self._reader = io.BytesIO(json.dumps(result).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self._reader.read(size)


def mocked_chat_completions(request, timeout):
    """Protocol-shaped, intentionally naive test double, NOT a real LLM."""
    body = json.loads(request.data)
    if len(body.get("messages", [])) != 2:
        raise AssertionError("unexpected chat input shape")
    prompt = body["messages"][1]["content"]
    guided = '"extract": "json-field"' in prompt and \
             '"normalise": "trim-lower"' in prompt
    selected = {
        "extract_strategy": "json-field" if guided else "raw",
        "normalise_strategy": "trim-lower" if guided else "lower-only",
    }
    return MockChatResponse({
        "choices": [{"message": {"content": json.dumps(selected)}}],
        "usage": {"prompt_tokens": 75, "completion_tokens": 14},
    })


def main(argv=None):
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--mock-api", action="store_true")
    parser.add_argument("--cases", type=int, default=4)
    args = parser.parse_args(argv)
    if args.mock_api:
        with patch.dict(os.environ, {"NERVE_LLM_API_KEY": "local-test-only-not-a-credential"}):
            planner = ChatCompletionsPlanner(
                url="https://mock.invalid/v1/chat/completions",
                model="protocol-fixture", transport=mocked_chat_completions)
            report = asyncio.run(run_study(planner=planner, count=args.cases))
        report["model_backend"] = "mock HTTP response; no external LLM"
    else:
        planner = ChatCompletionsPlanner() if args.live else FixturePlanner()
        report = asyncio.run(run_study(planner=planner, count=args.cases))
        report["model_backend"] = ("live external provider" if args.live
                                   else "offline deterministic fixture")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
