"""v1.5 same-planner, two-format, held-out MCP tool-use evaluation.

The optional live model sees only a task format label and registered
strategy IDs. Synthetic task inputs and answer keys stay local in the
official MCP subprocess/client and independent deterministic evaluator.
"""
import argparse
import asyncio
import io
import json
import os
import random
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from nerve_awim.agent_study_v15 import (
    FORMATS, PLANS, CapableFixturePlanner, LimitedFixturePlanner,
    FormatChatPlanner, FormatExperience,
)
from nerve_awim.evolution_v01 import EvolutionMemory
from nerve_awim.llm_agent_v14 import Plan

ALL_PLANS = (
    Plan("raw", "lower-only"),
    Plan("raw", "trim-lower"),
    Plan("json-field", "lower-only"),
    Plan("json-field", "trim-lower"),
)


def mcp_value(result):
    if getattr(result, "is_error", getattr(result, "isError", False)):
        raise ValueError("registered MCP tool rejected task")
    structured = getattr(result, "structured_content",
                         getattr(result, "structuredContent", None))
    if structured is not None:
        if type(structured) is dict and set(structured) == {"result"}:
            return structured["result"]
        return structured
    content = [getattr(item, "text", "") for item in result.content]
    if len(content) != 1:
        raise ValueError("unexpected MCP response")
    return json.loads(content[0])


def make_task(task_format, seed, index, *, training=False):
    if task_format not in FORMATS:
        raise ValueError("unregistered task format")
    prefix = "training" if training else "heldout"
    base = prefix + str(seed) + "n" + str(index)
    target = base + "@example.org"
    raw = (" " * (index % 3 + 1)) + target.upper() + (" " * (index % 2 + 1))
    document = json.dumps({"email": raw}) if task_format == "json_email" else raw
    return document, target


async def execute(client, *, task_id, text, plan):
    result = await client.call_tool(
        "run_demo_agent_plan",
        arguments={
            "task_id": task_id,
            "email_document": text,
            "extract_strategy": plan.extract_strategy,
            "normalise_strategy": plan.normalise_strategy,
        },
    )
    return mcp_value(result)["result"]


async def study(*, planner, seeds=2, cases_per_format=3):
    if type(seeds) is not int or not 1 <= seeds <= 4:
        raise ValueError("study seeds must be 1..4")
    if type(cases_per_format) is not int or not 1 <= cases_per_format <= 8:
        raise ValueError("per-format cases must be 1..8")
    rows = []
    for seed in range(seeds):
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "history.sqlite")
            memory = FormatExperience(EvolutionMemory(db), agent_id="v15-study")
            environment = {
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                "NERVE_LEARN_DB": db,
                "NERVE_DEMO_AGENT_ID": "v15-mcp-demo",
                "PYTHONUNBUFFERED": "1",
            }
            server = StdioServerParameters(
                command=sys.executable,
                args=["-m", "nerve_awim.learn_mcp"],
                env=environment,
            )
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    registered = {t.name for t in
                                  (await client.list_tools()).tools}
                    if "run_demo_agent_plan" not in registered:
                        raise RuntimeError("safe MCP tool unavailable")
                    # Training split: try each registered combination on two
                    # fixed training examples. Both evaluation arms later see
                    # identical experience history; only use of it differs.
                    count = 0
                    for fmt in FORMATS:
                        for plan_idx, candidate in enumerate(ALL_PLANS):
                            for training_index in range(2):
                                text, expected = make_task(
                                    fmt, seed, training_index, training=True)
                                try:
                                    actual = await execute(
                                        client, task_id="tr-" + fmt +
                                        str(plan_idx) + str(training_index),
                                        text=text, plan=candidate)
                                except (ValueError, RuntimeError):
                                    actual = None
                                memory.record(
                                    fmt, candidate, float(actual == expected))
                                count += 1
                    if count != 16:
                        raise RuntimeError("incomplete training observations")

                    # Lock fixed withheld cases before selecting any plans.
                    tasks = [
                        (fmt, index, *make_task(fmt, seed, index, training=False))
                        for fmt in FORMATS
                        for index in range(cases_per_format)
                    ]
                    rng = random.Random(seed + 990)
                    rng.shuffle(tasks)
                    outcomes = {}
                    for mode in (("no_memory", "with_memory") if seed % 2 == 0
                                 else ("with_memory", "no_memory")):
                        results = []
                        failures = 0
                        elapsed = []
                        model_seconds = []
                        tokens = {"input": 0, "output": 0}
                        for index, (fmt, case_id, text, expected) in enumerate(tasks):
                            start = perf_counter()
                            advice = (memory.recommendation(fmt)
                                      if mode == "with_memory" else None)
                            decision = planner.plan_for(fmt, advice=advice)
                            model_seconds.append(decision.elapsed_seconds)
                            for name, value in (
                                ("input", decision.input_tokens),
                                ("output", decision.output_tokens),
                            ):
                                if value is not None:
                                    tokens[name] += value
                            try:
                                answer = await execute(
                                    client, task_id="ev-" + mode +
                                    str(index), text=text, plan=decision.plan)
                                success = answer == expected
                            except (ValueError, RuntimeError):
                                success = False
                                failures += 1
                            results.append(success)
                            elapsed.append(perf_counter() - start)
                        outcomes[mode] = {
                            "successes": sum(results),
                            "tasks": len(results),
                            "execution_errors": failures,
                            "mean_wall_seconds": statistics.mean(elapsed),
                            "mean_model_seconds": statistics.mean(model_seconds),
                            "tokens": tokens,
                        }
                    rows.append(outcomes)
    arms = {}
    for mode in ("no_memory", "with_memory"):
        subset = [row[mode] for row in rows]
        arms[mode] = {
            "accuracy": sum(x["successes"] for x in subset) /
                        sum(x["tasks"] for x in subset),
            "errors": sum(x["execution_errors"] for x in subset),
            "tasks": sum(x["tasks"] for x in subset),
            "model_decisions": sum(x["tasks"] for x in subset),
            "registered_tool_stages": 2 * sum(x["tasks"] for x in subset),
            "mean_wall_seconds": round(statistics.mean(
                x["mean_wall_seconds"] for x in subset), 6),
            "mean_model_seconds": round(statistics.mean(
                x["mean_model_seconds"] for x in subset), 6),
            "token_usage": {
                name: sum(x["tokens"][name] for x in subset)
                for name in ("input", "output")
            },
        }
    return {
        "planner": planner.__class__.__name__,
        "seeds": seeds,
        "task_formats": list(FORMATS),
        "training_outcomes_per_seed": 16,
        "heldout_cases_per_format_per_seed": cases_per_format,
        "arms": arms,
        "paired_arms": True,
        "arm_order_counterbalanced": seeds >= 2,
        "heldout_feedback_leakage": False,
        "disclaimer": ("Synthetic registered tools. Offline fixtures are not "
                       "LLMs; no real model performance or learning-speed "
                       "claim without live, independent validation."),
    }


class MockResponse:
    def __init__(self, response):
        self._buffer = io.BytesIO(json.dumps(response).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self._buffer.read(limit)


def mock_provider(request, timeout):
    """Capable mock: derives correct tool pair from allowed format metadata."""
    payload = json.loads(request.data)
    metadata = payload["messages"][1]["content"]
    fmt = "json_email" if "format: json_email." in metadata else "plain_email"
    plan = PLANS[fmt]
    return MockResponse({
        "choices": [{"message": {"content": json.dumps({
            "extract_strategy": plan.extract_strategy,
            "normalise_strategy": plan.normalise_strategy,
        })}}],
        "usage": {"prompt_tokens": 85, "completion_tokens": 16}
    })


def main(argv=None):
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--mock-api", action="store_true")
    modes.add_argument("--limited-fixture", action="store_true")
    modes.add_argument("--live", action="store_true")
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--cases", type=int, default=3)
    args = parser.parse_args(argv)
    if args.mock_api:
        with patch.dict(os.environ, {"NERVE_LLM_API_KEY": "fake-local-only"}):
            planner = FormatChatPlanner(
                url="https://mock.invalid/v1/chat/completions",
                model="mock-capable", transport=mock_provider)
            report = asyncio.run(study(
                planner=planner, seeds=args.seeds,
                cases_per_format=args.cases))
        report["mode"] = "offline-chat-protocol-mock-not-llm"
    else:
        planner = (FormatChatPlanner() if args.live else
                   LimitedFixturePlanner() if args.limited_fixture else
                   CapableFixturePlanner())
        report = asyncio.run(study(
            planner=planner, seeds=args.seeds,
            cases_per_format=args.cases))
        report["mode"] = ("live-opt-in" if args.live else
                          "limited-fixture" if args.limited_fixture else
                          "capable-fixture-not-llm")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
