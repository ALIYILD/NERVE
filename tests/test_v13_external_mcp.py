import unittest
from benchmarks.v13_external_mcp import benchmark, episode


class ExternalMCPV13BenchmarkTests(unittest.TestCase):
    def test_equal_training_and_tool_call_budgets(self):
        output = episode(3, tasks_per_seed=8)
        self.assertEqual(output["training_observations"], 8)
        self.assertEqual(output["strategy_invocations_per_policy"], 16)

    def test_utility_reaches_fixed_correct_pipeline(self):
        result = episode(2, tasks_per_seed=12)
        self.assertEqual(result["utility_accuracy"], 1.0)
        self.assertEqual(result["fixed_optimal_accuracy"], 1.0)

    def test_recency_is_deliberately_weak_control(self):
        report = benchmark(range(3))
        self.assertEqual(report["accuracy"]["recency"], 0.0)
        self.assertEqual(report["accuracy"]["utility"], 1.0)
        self.assertEqual(report["accuracy"]["fixed_optimal"], 1.0)

    def test_multiple_seeds(self):
        report = benchmark(range(4))
        self.assertEqual(report["seeds"], 4)
        self.assertEqual(report["tasks_per_seed_per_policy"], 18)
        self.assertEqual(report["utility_win_seeds"], 4)

    def test_invalid_test_budget(self):
        with self.assertRaises(ValueError):
            episode(1, tasks_per_seed=0)
        with self.assertRaises(ValueError):
            episode(1, tasks_per_seed=37)


if __name__ == "__main__":
    unittest.main()
