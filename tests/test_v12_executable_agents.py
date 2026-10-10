import unittest

from benchmarks.v12_executable_agents import benchmark, case, episode


class ExecutableAgentsV12Tests(unittest.TestCase):
    def test_heldout_equal_task_budget(self):
        outcome = episode(0, heldout_per_context=4)
        self.assertEqual(outcome["task_calls_per_policy"], 12)
        self.assertEqual(outcome["training_feedback_count"], 30)

    def test_utility_retrieval_not_worse_on_constructed_tasks(self):
        result = episode(3, heldout_per_context=6)
        self.assertGreaterEqual(result["utility_success"],
                                result["recency_success"])
        self.assertEqual(result["utility_success"], 1)

    def test_multiple_seeds_aggregate(self):
        result = benchmark(range(3))
        self.assertEqual(result["seeds"], 3)
        self.assertEqual(result["task_calls_per_policy_per_seed"], 72)
        self.assertGreaterEqual(result["utility_success"],
                                result["recency_success"])

    def test_task_generators_are_not_constant(self):
        self.assertNotEqual(case("json", 3), case("json", 8))
        self.assertNotEqual(case("email", 1), case("email", 2))

    def test_training_bounds(self):
        with self.assertRaises(ValueError):
            episode(1, training_examples=0)
        with self.assertRaises(ValueError):
            episode(1, heldout_per_context=0)

    def test_no_external_model_required(self):
        outcome = episode(5, heldout_per_context=3)
        self.assertGreaterEqual(outcome["recency_success"], 0)
        self.assertLessEqual(outcome["recency_success"], 1)


if __name__ == "__main__":
    unittest.main()
