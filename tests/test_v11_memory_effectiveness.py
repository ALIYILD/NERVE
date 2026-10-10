import unittest
from benchmarks.v11_memory_effectiveness import benchmark, episode


class MemoryEffectivenessTests(unittest.TestCase):
    def test_reproducible_seed(self):
        self.assertEqual(episode(42), episode(42))

    def test_reproducible_benchmark(self):
        self.assertEqual(benchmark(range(3)), benchmark(range(3)))

    def test_bounded_rates(self):
        result = episode(3)
        self.assertTrue(all(0 <= value <= 1 for value in result.values()))

    def test_identical_test_budget(self):
        result = benchmark(range(2))
        self.assertEqual(result["heldout_trials_per_seed"], 180)
        self.assertEqual(set(result["success_rate"]),
                         {"outcome_memory", "recency_memory", "oracle"})

    def test_observation_budget_checked(self):
        with self.assertRaises(ValueError):
            episode(2, training_trials=0)


if __name__ == "__main__":
    unittest.main()
