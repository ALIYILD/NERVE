"""v1.3 held-out two-step MCP-ready agent strategy benchmark.

Executes the same fixed allowlisted tools via DemoAgentBridge for utility,
recency and fixed-correct reference. It does not use an MCP wire client,
external LLM, real API, patient data, or private credentials.
"""
import json
import random
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

from nerve_awim.agent_bridge_v13 import DemoAgentBridge


def episode(seed, *, tasks_per_seed=18):
    if type(tasks_per_seed) is not int or not 1 <= tasks_per_seed <= 36:
        raise ValueError("bounded evaluation tasks required")
    rng = random.Random(seed + 100000)
    with tempfile.TemporaryDirectory() as folder:
        bridge = DemoAgentBridge(Path(folder) / "memory.sqlite", max_workers=4)
        # Both methods use exactly the same trusted, fixed training data.
        trained = bridge.train_fixed_fixtures()
        tasks = []
        expected = {}
        for index in range(tasks_per_seed):
            name = "user" + str(seed) + "_" + str(index)
            extra = " " * (1 + rng.randrange(1, 4))
            address = name.upper() + "@EXAMPLE.ORG"
            raw = extra + address + extra
            item = {"task_id": "t" + str(index),
                    "email_document": json.dumps({"email": raw})}
            tasks.append(item)
            expected[item["task_id"]] = name + "@example.org"
        rates = {}
        costs = {}
        for policy in ("utility", "recency"):
            before = perf_counter()
            outputs = bridge.run_pipelines(tasks[:16], policy=policy)
            if len(tasks) > 16:
                outputs += bridge.run_pipelines(tasks[16:], policy=policy)
            costs[policy] = perf_counter() - before
            rates[policy] = sum(
                output["result"] == expected[output["task_id"]]
                for output in outputs
            ) / len(tasks)
        # A correctly configured deterministic baseline is also perfect:
        # memory should NOT be described as inherently superior to this.
        fixed_optimal = sum(
            raw["email_document"] is not None and
            json.loads(raw["email_document"])["email"].strip().lower() ==
                expected[raw["task_id"]]
            for raw in tasks
        ) / len(tasks)
        return {
            "utility_accuracy": rates["utility"],
            "recency_accuracy": rates["recency"],
            "fixed_optimal_accuracy": fixed_optimal,
            "tasks_per_policy": len(tasks),
            "strategy_invocations_per_policy": len(tasks) * 2,
            "training_observations": trained["verified_training_observations"],
            "utility_wall_seconds": costs["utility"],
            "recency_wall_seconds": costs["recency"],
        }


def benchmark(seeds=range(12)):
    records = [episode(seed) for seed in seeds]
    if not records:
        raise ValueError("nonempty seed collection required")
    report = {
        "seeds": len(records),
        "tasks_per_seed_per_policy": records[0]["tasks_per_policy"],
        "registered_tool_invocations_per_policy": records[0][
            "strategy_invocations_per_policy"],
        "training_observations": records[0]["training_observations"],
        "accuracy": {
            policy: statistics.mean(r[policy + "_accuracy"] for r in records)
            for policy in ("utility", "recency", "fixed_optimal")
        },
        "utility_win_seeds": sum(
            r["utility_accuracy"] > r["recency_accuracy"] for r in records),
        "utility_mean_wall_seconds": statistics.mean(
            r["utility_wall_seconds"] for r in records),
        "recency_mean_wall_seconds": statistics.mean(
            r["recency_wall_seconds"] for r in records),
        "interpretation": (
            "Toy two-step allowlisted tools; learning picks the verified "
            "configuration, but a fixed-correct non-learning pipeline is "
            "equally accurate. Not a real LLM or MCP protocol benchmark."
        ),
    }
    return report


if __name__ == "__main__":
    print(json.dumps(benchmark(), indent=2, sort_keys=True))
