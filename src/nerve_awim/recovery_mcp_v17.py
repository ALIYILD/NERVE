"""MCP-safe v1.7 recovery demonstration with fixed synthetic scenarios.

The caller cannot supply code, credentials, health data, verifier behaviour,
tool handlers or reward labels. All agent strategies and checks are fixed
locally. This is a public research demo, not a deployment safety supervisor.
"""
import json
from .agent_learning_v12 import AgentTask, RegisteredStrategy
from .evolution_v01 import EvolutionMemory
from .recovery_learning_v17 import BoundedStrategyRecovery


def _judge(task, output):
    if task.context == "email":
        return output == "demo@example.org"
    if task.context == "numbers":
        return output == (2, 3, 10)
    if task.context == "json":
        return type(output) is int and output == 25
    return False


STRATEGIES = (
    RegisteredStrategy("basic", "email", lambda x: x.lower()),
    RegisteredStrategy("trim", "email", lambda x: x.strip().lower()),
    RegisteredStrategy("lexical", "numbers",
                       lambda x: tuple(int(y) for y in sorted(x))),
    RegisteredStrategy("numeric", "numbers",
                       lambda x: tuple(sorted(int(y) for y in x))),
    RegisteredStrategy("zero", "json", lambda x: 0),
    RegisteredStrategy("parse", "json", lambda x: json.loads(x)["value"]),
)
CASES = (
    AgentTask("demo-email", "email", "  DEMO@EXAMPLE.ORG  "),
    AgentTask("demo-numbers", "numbers", ("10", "2", "3")),
    AgentTask("demo-json", "json", '{"value":25}'),
    AgentTask("demo-unsolved", "email", "unsupported-format"),
)


class RecoveryMCPDemo:
    def __init__(self, path):
        self.memory = EvolutionMemory(path)
        self.coordinator = BoundedStrategyRecovery(
            memory=self.memory, agent_id="recovery-fixed-synthetic-demo",
            strategies=STRATEGIES, judge=_judge,
            max_attempts=2, max_workers=4,
        )

    def run(self, *, policy="memory", train_on_fixtures=False):
        if policy not in ("memory", "no_memory"):
            raise ValueError("unsupported demo policy")
        if type(train_on_fixtures) is not bool:
            raise ValueError("training option must be boolean")
        observed = 0
        if train_on_fixtures:
            for task in CASES[:3]:
                for strategy in self.coordinator.coordinator.ordered[task.context]:
                    self.coordinator.record_training(task, strategy)
                    observed += 1
        results = self.coordinator.run(CASES, policy=policy)
        return {
            "policy": policy,
            "new_training_observations": observed,
            "synthetic_cases": len(results),
            "completed": sum(x.succeeded for x in results),
            "recovered_after_failure": sum(
                x.recovered_after_failure for x in results),
            "registered_attempts": sum(len(x.attempts) for x in results),
            "memory_used": sum(x.used_memory for x in results),
            "unresolved": sum(not x.succeeded for x in results),
            "case_results": [
                {
                    "task_id": x.task_id,
                    "success": x.succeeded,
                    "attempts": [attempt.strategy_id for attempt in x.attempts],
                }
                for x in results
            ],
            "scope": "program-owned synthetic scenarios; no arbitrary code or real-world actuation",
        }
