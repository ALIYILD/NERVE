"""NERVE Evolution v1.3: framework-neutral, allowlisted executable agent demo.

Only two inert string transformations are exposed. Stored experience
never executes arbitrary code or changes permissions. Caller-supplied
agent_id is a local namespace, NOT authenticated identity.
"""
from dataclasses import asdict
import json

from .agent_learning_v12 import (
    AgentTask, FeedbackAgentCoordinator, RegisteredStrategy
)
from .evolution_v01 import EvolutionMemory
from .parallel_agents_v11 import AgentJob, BoundedParallelAgents


def _validate_email(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 180:
        raise ValueError("demo email must be nonempty and <=180 characters")
    return value


def _extract_raw(value):
    return value  # Deliberately ineffective candidate for measured evaluation.


def _extract_json(value):
    document = json.loads(value)
    if not isinstance(document, dict) or set(document) != {"email"}:
        raise ValueError("expected exactly one email field")
    return _validate_email(document["email"])


def _normalise_basic(value):
    return _validate_email(value).lower()


def _normalise_trim(value):
    return _validate_email(value).strip().lower()


STRATEGIES = (
    RegisteredStrategy("raw", "extract", _extract_raw),
    RegisteredStrategy("json-field", "extract", _extract_json),
    RegisteredStrategy("lower-only", "normalise", _normalise_basic),
    RegisteredStrategy("trim-lower", "normalise", _normalise_trim),
)

# Fixed training-only examples, not arbitrary caller-supplied reward labels.
FIXTURES = (
    ("  TRAIN.ONE@EXAMPLE.COM  ", "train.one@example.com"),
    ("  TWO@EXAMPLE.ORG  ", "two@example.org"),
)


class DemoAgentBridge:
    def __init__(self, path, *, agent_id="external-demo", max_workers=4):
        self.agent = FeedbackAgentCoordinator(
            memory=EvolutionMemory(path), agent_id=agent_id,
            strategies=STRATEGIES, max_workers=max_workers
        )
        self.pool = BoundedParallelAgents(
            {"pipeline": self._run_one}, max_workers=max_workers,
            max_jobs=16
        )

    @staticmethod
    def capabilities():
        return (
            {"context": "extract", "strategies": ["raw", "json-field"]},
            {"context": "normalise", "strategies": ["lower-only", "trim-lower"]},
        )

    def train_fixed_fixtures(self):
        """Trusted program scores known tools on fixed examples.

        No feedback, scores or expected labels are accepted from MCP callers.
        Deliberately record the poor strategy last so recency is a meaningful
        baseline in paired tests, using exactly the same prior experiences.
        """
        count = 0
        for raw_email, canonical in FIXTURES:
            source = json.dumps({"email": raw_email}, sort_keys=True)
            for context, candidates, payload, expected in (
                ("extract", ("json-field", "raw"), source, raw_email),
                ("normalise", ("trim-lower", "lower-only"), raw_email, canonical),
            ):
                for strategy_id in candidates:
                    handler = self.agent.registry[(context, strategy_id)]
                    try:
                        outcome = handler(payload)
                    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                        outcome = None
                    self.agent.feedback(
                        context=context, strategy_id=strategy_id,
                        reward=float(outcome == expected)
                    )
                    count += 1
        return {"verified_training_observations": count,
                "source": "fixed synthetic fixtures; no user labels"}

    def choose(self, context, *, policy="utility"):
        if context not in ("extract", "normalise"):
            raise ValueError("only built-in safe contexts are supported")
        strategy_id, used_feedback = self.agent.select(context, policy=policy)
        return {"context": context, "strategy_id": strategy_id,
                "used_feedback": used_feedback,
                "warning": "Selection is research guidance, not authorisation"}

    def _run_one(self, payload):
        task_id, email_document, policy = payload
        if not isinstance(email_document, str) or not 1 <= len(email_document) <= 512:
            raise ValueError("demo JSON input must be <=512 characters")
        if policy not in ("utility", "recency"):
            raise ValueError("only utility and recency research policies supported")
        first = self.agent.run([
            AgentTask(task_id + ":extract", "extract", email_document)
        ], policy=policy)[0]
        if not isinstance(first.value, str):
            raise ValueError("string extraction result required")
        second = self.agent.run([
            AgentTask(task_id + ":normalise", "normalise", first.value)
        ], policy=policy)[0]
        return {
            "task_id": task_id,
            "result": second.value,
            "strategies": {
                "extract": first.strategy_id,
                "normalise": second.strategy_id,
            },
            "used_feedback": first.used_feedback or second.used_feedback,
            "policy": policy,
        }

    def run_pipeline(self, *, task_id, email_document, policy="utility"):
        if not isinstance(task_id, str) or not 0 < len(task_id) <= 48:
            raise ValueError("bounded task ID required")
        return self._run_one((task_id, email_document, policy))

    def run_pipelines(self, tasks, *, policy="utility"):
        """Concurrent independent two-stage tasks, all-or-nothing results."""
        tasks = tuple(tasks)
        if not 1 <= len(tasks) <= 16:
            raise ValueError("between 1 and 16 pipeline tasks required")
        validated = []
        for task in tasks:
            if not isinstance(task, dict) or set(task) != {"task_id", "email_document"}:
                raise ValueError("expected task_id and email_document")
            task_id = task["task_id"]
            if not isinstance(task_id, str) or not 0 < len(task_id) <= 48:
                raise ValueError("invalid pipeline task ID")
            validated.append(task)
        if len({task["task_id"] for task in validated}) != len(validated):
            raise ValueError("duplicate pipeline task IDs")
        outcomes = self.pool.run([
            AgentJob(task["task_id"], "pipeline",
                     (task["task_id"], task["email_document"], policy))
            for task in validated
        ])
        return [item.output for item in outcomes]
