"""Executable-tool agent memory benchmark with fixed withheld examples.

This is more concrete than random-success lookups: actual trusted Python
handlers perform email normalisation, numeric sorting and JSON extraction.
Neither policy receives held-out answer feedback during evaluation. It is
NOT an LLM-agent benchmark or evidence of autonomous model training.
"""
import json
import random
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

from nerve_awim.agent_learning_v12 import (
    AgentTask, FeedbackAgentCoordinator, RegisteredStrategy,
)
from nerve_awim.evolution_v01 import EvolutionMemory


def strategies():
    return (
        RegisteredStrategy("lower-only", "email",
                           lambda value: value.lower()),
        RegisteredStrategy("strip-lower", "email",
                           lambda value: value.strip().lower()),
        RegisteredStrategy("lexical-sort", "numbers",
                           lambda value: tuple(int(x) for x in sorted(value))),
        RegisteredStrategy("numeric-sort", "numbers",
                           lambda value: tuple(sorted(int(x) for x in value))),
        RegisteredStrategy("return-zero", "json",
                           lambda value: 0),
        RegisteredStrategy("parse-json", "json",
                           lambda value: json.loads(value)["value"]),
    )


def case(context, index):
    """Generate held-out inputs without looking at any agent's predictions."""
    if context == "email":
        name = "user" + str(index)
        value = "  " + name.upper() + "@Example.ORG  "
        return value, name + "@example.org"
    if context == "numbers":
        values = ("10", str(2 + index % 4), "3")
        return values, tuple(sorted(int(x) for x in values))
    if context == "json":
        return json.dumps({"value": index + 9,
                           "metadata": "non-critical"}), index + 9
    raise ValueError("unsupported benchmark capability")


def episode(seed, training_examples=5, heldout_per_context=24):
    if type(training_examples) is not int or not 1 <= training_examples <= 30:
        raise ValueError("bounded training examples required")
    if type(heldout_per_context) is not int or not 1 <= heldout_per_context <= 50:
        raise ValueError("bounded holdout required")
    rng = random.Random(seed)
    capabilities = ("email", "numbers", "json")
    with tempfile.TemporaryDirectory() as folder:
        memory = EvolutionMemory(Path(folder) / "memory.sqlite")
        agent = FeedbackAgentCoordinator(
            memory=memory, agent_id="research-test",
            strategies=strategies(), max_workers=4,
        )
        for context in capabilities:
            # Both strategies are attempted equally often. Randomise which
            # one is most recent; the recency policy gets the same history.
            ids = list(agent.ordered[context])
            rng.shuffle(ids)
            for strategy_id in ids:
                handler = agent.registry[(context, strategy_id)]
                for index in range(training_examples):
                    payload, expected = case(context, seed * 100 + index)
                    actual = handler(payload)
                    reward = float(actual == expected)
                    agent.feedback(context=context, strategy_id=strategy_id,
                                   reward=reward)

        # Entire held-out task set is prepared before either policy executes.
        tasks = []
        expected = {}
        for context in capabilities:
            for index in range(heldout_per_context):
                task_id = context + ":" + str(index)
                payload, target = case(context, 100000 + seed * 100 + index)
                tasks.append(AgentTask(task_id, context, payload))
                expected[task_id] = target
        # Both policies have exactly one registered strategy invocation per
        # task, and use the same input stream and evaluated memory.
        observed = {}
        timing = {}
        for policy in ("utility", "recency"):
            start = perf_counter()
            predictions = []
            for offset in range(0, len(tasks), 48):
                predictions.extend(agent.run(
                    tasks[offset:offset + 48], policy=policy))
            timing[policy] = perf_counter() - start
            if len(predictions) != len(tasks):
                raise RuntimeError("missing executable outcomes")
            observed[policy] = sum(
                result.value == expected[result.task_id]
                for result in predictions
            ) / len(tasks)

        return {
            "utility_success": observed["utility"],
            "recency_success": observed["recency"],
            "task_calls_per_policy": len(tasks),
            "training_feedback_count": (
                len(capabilities) * 2 * training_examples
            ),
            "utility_elapsed_seconds": timing["utility"],
            "recency_elapsed_seconds": timing["recency"],
        }


def benchmark(seeds=range(12)):
    records = [episode(seed) for seed in seeds]
    if not records:
        raise ValueError("at least one seed required")
    return {
        "seeds": len(records),
        "task_calls_per_policy_per_seed": records[0]["task_calls_per_policy"],
        "training_feedback_per_seed": records[0]["training_feedback_count"],
        "utility_success": statistics.mean(
            r["utility_success"] for r in records),
        "recency_success": statistics.mean(
            r["recency_success"] for r in records),
        "utility_win_seeds": sum(
            r["utility_success"] > r["recency_success"] for r in records),
        "utility_mean_elapsed_seconds": statistics.mean(
            r["utility_elapsed_seconds"] for r in records),
        "recency_mean_elapsed_seconds": statistics.mean(
            r["recency_elapsed_seconds"] for r in records),
        "limitations": (
            "Deterministic hand-authored tools and exact-output judge; "
            "does not establish improvement for LLMs, real-world agents, "
            "model-weight learning, or execution speed."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(benchmark(), indent=2, sort_keys=True))
