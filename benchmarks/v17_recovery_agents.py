"""NERVE v1.7 held-out multi-context strategy recovery benchmark.

Three executable registered capabilities: normalise text, numeric sorting,
and JSON value extraction. Same withheld tasks, allowed handlers, independent
judge and *max two attempts* for every policy. Strong preconfigured
non-learning baseline included. All experience training is separate from
test execution; this is not an LLM or general learning-speed benchmark.
"""
import json
import random
import statistics
import tempfile
from pathlib import Path

from nerve_awim.agent_learning_v12 import AgentTask, RegisteredStrategy
from nerve_awim.evolution_v01 import EvolutionMemory
from nerve_awim.recovery_learning_v17 import BoundedStrategyRecovery

CONTEXTS = ("email", "numbers", "json")


def trusted_judge(task, outcome):
    try:
        if task.context == "email":
            expected = task.payload.strip().lower()
            return expected.endswith("@example.org") and outcome == expected
        if task.context == "numbers":
            expected = tuple(sorted(int(x) for x in task.payload))
            return outcome == expected
        if task.context == "json":
            data = json.loads(task.payload)
            return type(data) is dict and type(data.get("value")) is int \
                and outcome == data["value"]
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return False
    return False


def strategies(seed, *, preconfigured=False):
    rng = random.Random(seed)
    groups = {
        "email": [
            RegisteredStrategy("lower-only", "email", lambda x: x.lower()),
            RegisteredStrategy("strip-lower", "email", lambda x: x.strip().lower()),
        ],
        "numbers": [
            RegisteredStrategy("lexical-sort", "numbers",
                               lambda x: tuple(int(v) for v in sorted(x))),
            RegisteredStrategy("numeric-sort", "numbers",
                               lambda x: tuple(sorted(int(v) for v in x))),
        ],
        "json": [
            RegisteredStrategy("zero", "json", lambda x: 0),
            RegisteredStrategy("parse-json", "json",
                               lambda x: json.loads(x)["value"]),
        ],
    }
    expected = {
        "email": "strip-lower", "numbers": "numeric-sort",
        "json": "parse-json",
    }
    for context in CONTEXTS:
        if preconfigured:
            groups[context].sort(
                key=lambda x: (x.strategy_id != expected[context],
                               x.strategy_id))
        else:
            rng.shuffle(groups[context])
    return tuple(x for context in CONTEXTS for x in groups[context])


def task(context, seed, i, *, heldout):
    identifier = ("heldout" if heldout else "training") + str(seed) + str(i)
    if context == "email":
        return AgentTask(
            context + ":" + str(i), context,
            "  " + identifier.upper() + "@EXAMPLE.ORG  ",
        )
    if context == "numbers":
        return AgentTask(
            context + ":" + str(i), context,
            ("10", str(2 + i % 3), "3"),
        )
    if context == "json":
        return AgentTask(
            context + ":" + str(i), context,
            json.dumps({"value": seed * 5 + i + 7}),
        )
    raise ValueError("unknown capability")


def withheld(seed, *, per_context=8, include_ood=True):
    tasks = [
        task(context, seed + 100000, i, heldout=True)
        for context in CONTEXTS for i in range(per_context)
    ]
    if include_ood:
        # Strict verifier rejects these even after the retry. They test that
        # persistent failure remains visible instead of being hidden as
        # "successfully retried".
        tasks.extend((
            AgentTask("ood-email", "email", "not-an-email"),
            AgentTask("ood-numbers", "numbers", ("bad", "10")),
            AgentTask("ood-json", "json", "not-json"),
        ))
    return tuple(tasks)


def train(agent, seed, train_examples=3):
    for context in CONTEXTS:
        for registered in agent.coordinator.ordered[context]:
            for i in range(train_examples):
                agent.record_training(
                    task(context, seed, i, heldout=False), registered
                )
    return len(CONTEXTS) * 2 * train_examples


def measurements(outcomes):
    attempts = [attempt for row in outcomes for attempt in row.attempts]
    return {
        "success_rate": sum(x.succeeded for x in outcomes) / len(outcomes),
        "first_attempt_success_rate": sum(
            bool(x.attempts and x.attempts[0].accepted) for x in outcomes
        ) / len(outcomes),
        "recovered_after_failure_rate": sum(
            x.recovered_after_failure for x in outcomes
        ) / len(outcomes),
        "mean_invocations": len(attempts) / len(outcomes),
        "failed_handler_calls": sum(x.handler_error for x in attempts),
        "unresolved_tasks": sum(not x.succeeded for x in outcomes),
        "tasks": len(outcomes),
    }


def episode(seed, *, per_context=8):
    all_tasks = withheld(seed, per_context=per_context)
    with tempfile.TemporaryDirectory() as directory:
        memory = EvolutionMemory(Path(directory) / "experiences.sqlite")
        selected = strategies(seed)
        agent = BoundedStrategyRecovery(
            memory=memory, agent_id="learner", strategies=selected,
            judge=trusted_judge, max_attempts=2, max_workers=4
        )
        trained = train(agent, seed)
        before = {
            context: len(memory.store.rated_history("learner", context))
            for context in CONTEXTS
        }
        observed = {}
        for policy in ("no_memory", "memory"):
            outputs = []
            for offset in range(0, len(all_tasks), 24):
                outputs += list(agent.run(
                    all_tasks[offset:offset + 24], policy=policy
                ))
            observed[policy] = measurements(outputs)
        after = {
            context: len(memory.store.rated_history("learner", context))
            for context in CONTEXTS
        }
        if before != after:
            raise AssertionError("held-out attempt leaked into training")

        # Optimally configured, non-learning baseline has the exact same
        # strategies, trusted judge, tasks and retry limit. Its first choice
        # is correctly configured instead of learned.
        fixed = BoundedStrategyRecovery(
            memory=memory, agent_id="fixed-control",
            strategies=strategies(seed, preconfigured=True),
            judge=trusted_judge, max_attempts=2, max_workers=4
        )
        outputs = []
        for offset in range(0, len(all_tasks), 24):
            outputs += list(fixed.run(
                all_tasks[offset:offset + 24], policy="no_memory"
            ))
        observed["fixed_correct"] = measurements(outputs)
        return {"policies": observed, "training_observations": trained}


def benchmark(seeds=range(12)):
    runs = [episode(seed) for seed in seeds]
    if not runs:
        raise ValueError("nonempty seed set required")
    policies = {}
    for policy in ("no_memory", "memory", "fixed_correct"):
        keys = runs[0]["policies"][policy]
        policies[policy] = {
            k: statistics.mean(run["policies"][policy][k] for run in runs)
            for k in keys
        }
    return {
        "seeds": len(runs),
        "training_observations_per_seed": runs[0]["training_observations"],
        "benchmark": "three executable contexts with bounded retry",
        "max_attempts_per_task": 2,
        "policies": policies,
        "limitations": (
            "Synthetic deterministic registered strategies and trusted exact "
            "judges only. Memory may reduce redundant attempts, but the "
            "preconfigured non-learning control is equally capable; "
            "no claim of faster LLM learning or production safety."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(benchmark(), indent=2, sort_keys=True))
