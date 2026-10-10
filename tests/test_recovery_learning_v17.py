import tempfile
import unittest
from pathlib import Path
from nerve_awim.agent_learning_v12 import AgentTask, RegisteredStrategy
from nerve_awim.evolution_v01 import EvolutionMemory
from nerve_awim.recovery_learning_v17 import BoundedStrategyRecovery


def strict_judge(task, output):
    return output == {
        "email": "test@example.org",
        "numbers": (2, 3, 10),
        "json": 17,
    }[task.context]


class RecoveryLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.memory = EvolutionMemory(Path(self.temp.name) / "memory.sqlite")
        self.strategies = (
            RegisteredStrategy("bad", "email", lambda x: x.lower()),
            RegisteredStrategy("good", "email", lambda x: x.strip().lower()),
            RegisteredStrategy("wrong", "numbers", lambda x: tuple(int(v) for v in sorted(x))),
            RegisteredStrategy("correct", "numbers", lambda x: tuple(sorted(int(v) for v in x))),
            RegisteredStrategy("zero", "json", lambda x: 0),
            RegisteredStrategy("parse", "json", lambda x: __import__("json").loads(x)["value"]),
        )
        self.agent = BoundedStrategyRecovery(
            memory=self.memory, agent_id="research",
            strategies=self.strategies, judge=strict_judge, max_workers=3
        )
        self.tasks = (
            AgentTask("a", "email", "  TEST@EXAMPLE.ORG  "),
            AgentTask("b", "numbers", ("10", "2", "3")),
            AgentTask("c", "json", '{"value":17}'),
        )

    def test_untrained_baseline_recovers_on_second_attempt(self):
        out = self.agent.run(self.tasks, policy="no_memory")
        self.assertTrue(all(x.succeeded and x.recovered_after_failure for x in out))
        self.assertEqual([len(x.attempts) for x in out], [2, 2, 2])
        self.assertEqual([x.task_id for x in out], ["a", "b", "c"])

    def test_evaluated_history_prioritises_successful_strategy(self):
        for task in self.tasks:
            ids = self.agent.coordinator.ordered[task.context]
            for name in ids:
                self.agent.record_training(task, name)
        out = self.agent.run(self.tasks, policy="memory")
        self.assertTrue(all(x.succeeded for x in out))
        self.assertTrue(all(len(x.attempts) == 1 for x in out))
        self.assertTrue(all(x.used_memory for x in out))

    def test_memory_never_changes_during_holdout(self):
        self.agent.record_training(self.tasks[0], "good")
        n = len(self.memory.store.rated_history("research", "email"))
        self.agent.run(self.tasks)
        self.assertEqual(len(self.memory.store.rated_history("research", "email")), n)

    def test_unregistered_memory_is_never_executable(self):
        self.memory.record("research", "email", "arbitrary-python-script", 1.)
        out = self.agent.run([self.tasks[0]])
        self.assertTrue(out[0].succeeded)
        self.assertTrue(all(attempt.strategy_id in ("bad", "good") for attempt in out[0].attempts))

    def test_one_attempt_budget_does_not_recover(self):
        agent = BoundedStrategyRecovery(
            memory=self.memory, agent_id="research",
            strategies=self.strategies, judge=strict_judge, max_attempts=1
        )
        out = agent.run([self.tasks[0]], policy="no_memory")
        self.assertFalse(out[0].succeeded)
        self.assertEqual(len(out[0].attempts), 1)

    def test_failing_strategy_can_trigger_fallback(self):
        strategies = (
            RegisteredStrategy("raise", "email", lambda x: 1/0),
            RegisteredStrategy("good", "email", lambda x: x.strip().lower()),
        )
        agent = BoundedStrategyRecovery(
            memory=self.memory, agent_id="research",
            strategies=strategies, judge=strict_judge
        )
        r, = agent.run([self.tasks[0]], policy="no_memory")
        self.assertTrue(r.succeeded)
        self.assertTrue(r.attempts[0].handler_error)

    def test_judge_failure_fails_entire_batch(self):
        def judge(task, output):
            raise RuntimeError("research evaluator unavailable")
        agent = BoundedStrategyRecovery(
            memory=self.memory, agent_id="research",
            strategies=self.strategies, judge=judge
        )
        with self.assertRaisesRegex(RuntimeError, "batch rejected"):
            agent.run(self.tasks)

    def test_invalid_judge_output_denied(self):
        agent = BoundedStrategyRecovery(
            memory=self.memory, agent_id="research",
            strategies=self.strategies, judge=lambda task, output: "approved"
        )
        with self.assertRaises(RuntimeError):
            agent.run([self.tasks[0]])
        with self.assertRaises(ValueError):
            agent.record_training(self.tasks[0], "good")

    def test_cross_agent_history_not_reused(self):
        other = BoundedStrategyRecovery(
            memory=self.memory, agent_id="other",
            strategies=self.strategies, judge=strict_judge
        )
        self.agent.record_training(self.tasks[0], "good")
        out, = other.run([self.tasks[0]], policy="memory")
        self.assertFalse(out.used_memory)
        self.assertEqual(len(out.attempts), 2)

    def test_unknown_strategy_feedback_rejected(self):
        with self.assertRaises(ValueError):
            self.agent.record_training(self.tasks[0], "from-memory-python")

    def test_duplicate_and_invalid_budget_rejected(self):
        with self.assertRaises(ValueError):
            self.agent.run([self.tasks[0], self.tasks[0]])
        with self.assertRaises(ValueError):
            BoundedStrategyRecovery(
                memory=self.memory, agent_id="research",
                strategies=self.strategies, judge=strict_judge, max_attempts=0
            )

    def test_genuinely_unsolvable_task_stays_unsolved(self):
        task = AgentTask("out-of-distribution", "email", "unknown-format")
        result, = self.agent.run([task])
        self.assertFalse(result.succeeded)
        self.assertEqual(len(result.attempts), 2)
        self.assertFalse(result.recovered_after_failure)


if __name__ == "__main__":
    unittest.main()
