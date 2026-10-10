import tempfile
import unittest
from pathlib import Path

from nerve_awim.agent_learning_v12 import (
    AgentTask, FeedbackAgentCoordinator, RegisteredStrategy
)
from nerve_awim.evolution_v01 import EvolutionMemory


class FeedbackAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "evolution.sqlite"
        self.memory = EvolutionMemory(self.db)
        self.strategies = (
            RegisteredStrategy("bad", "email", lambda x: x.lower()),
            RegisteredStrategy("good", "email", lambda x: x.strip().lower()),
            RegisteredStrategy("identity", "numbers", lambda x: tuple(x)),
        )
        self.agent = FeedbackAgentCoordinator(
            memory=self.memory, agent_id="agent-alpha",
            strategies=self.strategies, max_workers=3
        )

    def test_learns_from_persisted_feedback(self):
        self.assertEqual(self.agent.select("email"), ("bad", False))
        self.agent.feedback(context="email", strategy_id="bad", reward=0)
        self.agent.feedback(context="email", strategy_id="good", reward=1)
        self.assertEqual(self.agent.select("email"), ("good", True))
        outcome = self.agent.run([
            AgentTask("one", "email", "  ADMIN@EXAMPLE.COM  ")
        ])[0]
        self.assertEqual(outcome.value, "admin@example.com")
        self.assertTrue(outcome.used_feedback)
        # Create a new process-independent coordinator over the same SQLite DB.
        restarted = FeedbackAgentCoordinator(
            memory=EvolutionMemory(self.db), agent_id="agent-alpha",
            strategies=self.strategies
        )
        self.assertEqual(restarted.select("email"), ("good", True))

    def test_recency_and_utility_differ_on_same_evidence(self):
        self.agent.feedback(context="email", strategy_id="good", reward=1)
        self.agent.feedback(context="email", strategy_id="bad", reward=0)
        self.assertEqual(self.agent.select("email", policy="recency")[0], "bad")
        self.assertEqual(self.agent.select("email", policy="utility")[0], "good")

    def test_untrusted_memory_cannot_trigger_unknown_handler(self):
        self.memory.record("agent-alpha", "email", "arbitrary_code", 1)
        self.assertEqual(self.agent.select("email"), ("bad", False))
        with self.assertRaises(ValueError):
            self.agent.feedback(
                context="email", strategy_id="arbitrary_code", reward=1
            )

    def test_agent_and_context_isolation(self):
        self.agent.feedback(context="email", strategy_id="good", reward=1)
        other = FeedbackAgentCoordinator(
            memory=self.memory, agent_id="agent-beta",
            strategies=self.strategies
        )
        self.assertEqual(other.select("email"), ("bad", False))
        self.assertEqual(self.agent.select("numbers"), ("identity", False))

    def test_invalid_rewards_rejected(self):
        for value in (float("nan"), float("inf"), -1, 1.1, True):
            with self.assertRaises(ValueError):
                self.agent.feedback(context="email", strategy_id="good",
                                    reward=value)

    def test_parallel_task_results_are_ordered(self):
        self.agent.feedback(context="email", strategy_id="good", reward=1)
        outcomes = self.agent.run([
            AgentTask("second", "numbers", (3, 1)),
            AgentTask("first", "email", "  HI@TEST.ORG  "),
        ])
        self.assertEqual([r.task_id for r in outcomes], ["second", "first"])
        self.assertEqual([r.value for r in outcomes],
                         [(3, 1), "hi@test.org"])

    def test_batch_failure_never_returns_partial_results(self):
        bad = FeedbackAgentCoordinator(
            memory=self.memory, agent_id="agent-alpha",
            strategies=[
                RegisteredStrategy(
                    "raise", "bad", lambda _: (_ for _ in ()).throw(
                        ValueError("expected simulated failure")
                    )
                )
            ],
        )
        with self.assertRaises(RuntimeError):
            bad.run([AgentTask("one", "bad", "data")])

    def test_duplicate_task_ids_rejected(self):
        with self.assertRaises(ValueError):
            self.agent.run([
                AgentTask("same", "email", "a"),
                AgentTask("same", "email", "b"),
            ])

    def test_unregistered_context_rejected(self):
        with self.assertRaises(LookupError):
            self.agent.run([AgentTask("a", "clinical", "data")])

    def test_exact_history_ignores_adjacent_context(self):
        self.memory.record("agent-alpha", "email-extra", "good", 1)
        self.assertEqual(self.agent.select("email"), ("bad", False))

    def test_holdout_run_does_not_record_feedback(self):
        self.agent.feedback(context="email", strategy_id="good", reward=1)
        before = len(self.memory.store.rated_history("agent-alpha", "email"))
        self.agent.run([AgentTask("a", "email", " A@B.COM ")])
        after = len(self.memory.store.rated_history("agent-alpha", "email"))
        self.assertEqual(before, after)

    def test_bad_policy_and_registry(self):
        with self.assertRaises(ValueError):
            self.agent.select("email", policy="unknown")
        with self.assertRaises(ValueError):
            FeedbackAgentCoordinator(
                memory=self.memory, agent_id="agent-alpha",
                strategies=self.strategies + (self.strategies[0],)
            )


if __name__ == "__main__":
    unittest.main()
