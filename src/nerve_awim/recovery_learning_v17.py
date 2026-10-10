"""NERVE v1.7: bounded, feedback-guided recovery for registered agent tools.

No arbitrary generated code, third-party API, clinical actuation, or automatic
retraining. Only a trusted evaluator may judge attempts and explicitly write
training feedback. Held-out run() never updates memory. Failed verification
cannot be overridden by agent text or high-scored recalled experiences.
"""
from dataclasses import dataclass
from time import perf_counter
from .agent_learning_v12 import AgentTask, FeedbackAgentCoordinator
from .parallel_agents_v11 import AgentJob, BoundedParallelAgents


@dataclass(frozen=True)
class RecoveryAttempt:
    strategy_id: str
    accepted: bool
    handler_error: bool


@dataclass(frozen=True)
class RecoveryOutcome:
    task_id: str
    context: str
    succeeded: bool
    recovered_after_failure: bool
    attempts: tuple[RecoveryAttempt, ...]
    used_memory: bool
    elapsed_seconds: float


class BoundedStrategyRecovery:
    """One or two registered attempts, scored by an injected trusted judge.

    A successful value is NEVER accepted on a model's self-report. The judge
    must be provisioned by trusted code. A judge failure is fatal for the
    entire batch; strategy errors are recorded and may trigger one fallback.
    """

    def __init__(self, *, memory, agent_id, strategies, judge,
                 max_attempts=2, max_workers=4):
        if not callable(judge):
            raise ValueError("trusted, callable evaluator required")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self.coordinator = FeedbackAgentCoordinator(
            memory=memory, agent_id=agent_id, strategies=strategies,
            max_workers=max_workers,
        )
        self.judge = judge
        self.max_attempts = max_attempts
        self.workers = BoundedParallelAgents(
            {"recover": self._attempt}, max_workers=max_workers, max_jobs=32,
        )

    def record_training(self, task, strategy_id):
        """Explicit training-only reward with evaluator-backed provenance.

        This function must not be called on the held-out task set. It records
        an outcome only after the independently supplied judge scores it.
        """
        if not isinstance(task, AgentTask):
            raise TypeError("typed AgentTask required")
        handler = self.coordinator.registry.get((task.context, strategy_id))
        if handler is None:
            raise ValueError("only registered strategies can be evaluated")
        try:
            result = handler(task.payload)
        except Exception:
            score = 0.0
        else:
            # Do not treat judge exceptions as a negative rating, because
            # doing so would poison otherwise unknown training experience.
            valid = self.judge(task, result)
            if type(valid) is not bool:
                raise ValueError("independent evaluator must return boolean")
            score = float(valid)
        return self.coordinator.feedback(
            context=task.context, strategy_id=strategy_id, reward=score,
        )

    def _attempt(self, payload):
        task, policy = payload
        if policy not in ("memory", "no_memory"):
            raise ValueError("invalid recovery selection policy")
        known = self.coordinator.ordered.get(task.context)
        if not known:
            raise LookupError("unsupported task context")
        if policy == "memory":
            primary, used_feedback = self.coordinator.select(task.context)
        else:
            primary, used_feedback = known[0], False
        # Exhaustively validate registry membership; recovered outputs are
        # evaluated by the same trusted independent judge as first attempts.
        candidates = (primary, *(item for item in known if item != primary))
        attempts = []
        started = perf_counter()
        for strategy_id in candidates[:self.max_attempts]:
            handler = self.coordinator.registry[(task.context, strategy_id)]
            try:
                output = handler(task.payload)
            except Exception:
                attempts.append(RecoveryAttempt(strategy_id, False, True))
                continue
            correct = self.judge(task, output)
            if type(correct) is not bool:
                raise ValueError("untrusted or invalid evaluator response")
            attempts.append(RecoveryAttempt(strategy_id, correct, False))
            if correct:
                break
        succeeded = bool(attempts and attempts[-1].accepted)
        return RecoveryOutcome(
            task_id=task.task_id,
            context=task.context,
            succeeded=succeeded,
            recovered_after_failure=succeeded and len(attempts) > 1,
            attempts=tuple(attempts),
            used_memory=used_feedback,
            elapsed_seconds=perf_counter() - started,
        )

    def run(self, tasks, *, policy="memory"):
        tasks = tuple(tasks)
        if policy not in ("memory", "no_memory"):
            raise ValueError("unsupported recovery policy")
        if not 1 <= len(tasks) <= 32 or not all(
                isinstance(item, AgentTask) for item in tasks):
            raise ValueError("between one and 32 typed tasks required")
        if len({item.task_id for item in tasks}) != len(tasks):
            raise ValueError("duplicate task ID")
        # Memory is unchanged throughout the held-out run. Parallel handlers
        # cannot generate new, approved code or autonomously change policies.
        outcomes = self.workers.run([
            AgentJob(task.task_id, "recover", (task, policy))
            for task in tasks
        ])
        return tuple(out.output for out in outcomes)
