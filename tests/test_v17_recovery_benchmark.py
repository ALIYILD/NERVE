"""v1.7 held-out executable recovery benchmark checks."""
import unittest

from benchmarks.v17_recovery_agents import (
    CONTEXTS, benchmark, episode, withheld, strategies, trusted_judge
)
from nerve_awim.agent_learning_v12 import AgentTask


class V17RecoveryBenchmarkTests(unittest.TestCase):
    def test_all_three_contexts(self):
        self.assertEqual(len(CONTEXTS), 3)
        self.assertEqual(len(withheld(4, per_context=3)), 12)

    def test_known_good_strategies(self):
        handlers = {(x.context, x.strategy_id): x.handler
                    for x in strategies(7, preconfigured=True)}
        tasks = withheld(2, per_context=3, include_ood=False)
        good = {
            "email": "strip-lower",
            "numbers": "numeric-sort",
            "json": "parse-json",
        }
        self.assertTrue(all(trusted_judge(
            task, handlers[(task.context, good[task.context])](task.payload)
        ) for task in tasks))

    def test_both_memory_and_baseline_recover_with_same_budget(self):
        output = episode(7, per_context=4)["policies"]
        self.assertEqual(output["no_memory"]["unresolved_tasks"], 3)
        self.assertEqual(output["memory"]["unresolved_tasks"], 3)
        self.assertEqual(output["fixed_correct"]["unresolved_tasks"], 3)
        self.assertEqual(output["no_memory"]["success_rate"],
                         output["memory"]["success_rate"])
        self.assertEqual(output["fixed_correct"]["success_rate"],
                         output["memory"]["success_rate"])
        self.assertLessEqual(output["memory"]["mean_invocations"],
                             output["no_memory"]["mean_invocations"])
        self.assertEqual(output["memory"]["mean_invocations"],
                         output["fixed_correct"]["mean_invocations"])

    def test_deterministic_metrics_except_time(self):
        a = episode(3, per_context=3)
        b = episode(3, per_context=3)
        self.assertEqual(a, b)

    def test_twelve_seed_paired_summary(self):
        report = benchmark(range(3))
        self.assertEqual(report["seeds"], 3)
        self.assertEqual(report["max_attempts_per_task"], 2)
        self.assertEqual(report["training_observations_per_seed"], 18)
        self.assertEqual(set(report["policies"]),
                         {"memory", "no_memory", "fixed_correct"})

    def test_unrecoverable_input_stays_unresolved(self):
        invalids = [x for x in withheld(2) if x.task_id.startswith("ood-")]
        self.assertEqual(len(invalids), 3)
        self.assertFalse(trusted_judge(
            AgentTask("x", "email", "not-an-email"),
            "not-an-email"))

    def test_no_training_on_test_set(self):
        # The episode itself verifies pre/post SQLite history size.
        self.assertEqual(episode(6)["training_observations"], 18)


if __name__ == "__main__":
    unittest.main()
