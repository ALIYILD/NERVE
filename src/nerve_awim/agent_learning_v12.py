"""NERVE v1.2: feedback-trained strategy selection for executable agents.

Framework-independent handlers are registered by trusted Python code. Stored
experience text can ONLY name a registered strategy, never execute commands,
code, or override policy. The judge/reward is external and must be verified
by a trusted caller. No third-party API or LLM is required.
"""
from dataclasses import dataclass
from math import isfinite

from .parallel_agents_v11 import AgentJob, BoundedParallelAgents


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    context: str
    payload: object

    def __post_init__(self):
        if not isinstance(self.task_id, str) or not 0 < len(self.task_id) <= 80:
            raise ValueError("bounded task ID required")
        if not isinstance(self.context, str) or not 0 < len(self.context) <= 80:
            raise ValueError("bounded task context required")


@dataclass(frozen=True)
class RegisteredStrategy:
    strategy_id: str
    context: str
    handler: object

    def __post_init__(self):
        if (not isinstance(self.strategy_id, str)
                or not 0 < len(self.strategy_id) <= 80
                or not isinstance(self.context, str)
                or not 0 < len(self.context) <= 80
                or not callable(self.handler)):
            raise ValueError("trusted registered callable required")


@dataclass(frozen=True)
class TaskOutcome:
    task_id: str
    context: str
    strategy_id: str
    value: object
    used_feedback: bool


class FeedbackAgentCoordinator:
    """Choose from registered handlers using evaluated episodic feedback.

    Utility policy averages rewards from prior evaluated episodes. Recency
    policy chooses the most recently evaluated strategy from SAME history.
    Both execute one strategy per task. No automatic feedback on test tasks.
    """

    def __init__(self, *, memory, agent_id, strategies, max_workers=4):
        if not isinstance(agent_id, str) or not 0 < len(agent_id) <= 80:
            raise ValueError("bounded agent identity required")
        self.memory = memory
        self.agent_id = agent_id
        self.registry = {}
        self.ordered = {}
        for item in strategies:
            if not isinstance(item, RegisteredStrategy):
                raise TypeError("RegisteredStrategy required")
            key = (item.context, item.strategy_id)
            if key in self.registry:
                raise ValueError("duplicate strategy in context")
            self.registry[key] = item.handler
            self.ordered.setdefault(item.context, []).append(item.strategy_id)
        if not self.registry:
            raise ValueError("at least one registered strategy required")
        if any(len(ids) > 20 for ids in self.ordered.values()):
            raise ValueError("more than 20 strategies in context")
        self.workers = BoundedParallelAgents(
            {"execute": self._execute}, max_workers=max_workers, max_jobs=64
        )

    def _execute(self, selected):
        context, strategy_id, payload = selected
        return (strategy_id, self.registry[(context, strategy_id)](payload))

    def feedback(self, *, context, strategy_id, reward):
        """Trusted caller records an independently evaluated bounded reward."""
        if (context, strategy_id) not in self.registry:
            raise ValueError("unregistered strategy cannot be rewarded")
        if (type(reward) not in (float, int)
                or not isfinite(reward) or not 0 <= reward <= 1):
            raise ValueError("reward must be finite between 0 and 1")
        return self.memory.record(
            self.agent_id, context, strategy_id, float(reward)
        )

    def select(self, context, *, policy="utility"):
        if policy not in ("utility", "recency"):
            raise ValueError("unsupported selection policy")
        allowed = self.ordered.get(context)
        if not allowed:
            raise LookupError("no strategy for context")
        history = self.memory.store.rated_history(self.agent_id, context)
        # All memory entries are untrusted strings. Never dispatch an
        # unregistered strategy, even if it has an impressive score.
        entries = [r for r in history
                   if r.outcome in allowed and r.score is not None
                   and isfinite(r.score) and 0 <= r.score <= 1]
        if not entries:
            return allowed[0], False
        if policy == "recency":
            return entries[-1].outcome, True
        totals = {name: [0.0, 0] for name in allowed}
        for r in entries:
            totals[r.outcome][0] += r.score
            totals[r.outcome][1] += 1
        ranked = [(s / count, -allowed.index(name), name)
                  for name, (s, count) in totals.items() if count]
        return max(ranked)[2], True

    def run(self, tasks, *, policy="utility"):
        tasks = tuple(tasks)
        if not 1 <= len(tasks) <= 64 or not all(
                isinstance(task, AgentTask) for task in tasks):
            raise ValueError("one to 64 typed tasks required")
        if len({task.task_id for task in tasks}) != len(tasks):
            raise ValueError("duplicate task IDs")
        # Decide for the entire batch before any worker executes. Observed
        # holdout results are never automatically used as training feedback.
        planned = [
            (task, *self.select(task.context, policy=policy))
            for task in tasks
        ]
        outcomes = self.workers.run([
            AgentJob(task.task_id, "execute",
                     (task.context, strategy_id, task.payload))
            for task, strategy_id, _ in planned
        ])
        return tuple(
            TaskOutcome(task.task_id, task.context, result.output[0],
                        result.output[1], used_history)
            for (task, _, used_history), result in zip(planned, outcomes)
        )
