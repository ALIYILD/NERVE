"""Tests of v1.6 independent, credential-free paired scoring."""
import math
import unittest

from nerve_awim.study_statistics_v16 import (
    mcnemar_exact_p, seed_cluster_interval, summarize_pairs,
)


def record(seed, fmt, case_id, without, with_mem, *,
           error_without=False, error_with=False):
    return {
        "seed": seed, "format": fmt, "task_id": str(case_id),
        "no_memory": without, "with_memory": with_mem,
        "no_memory_error": error_without,
        "with_memory_error": error_with,
    }


class PairedEvidenceV16Tests(unittest.TestCase):
    def test_exact_discordance(self):
        rows = [
            record(0, "json_email", "a", False, True),
            record(0, "json_email", "b", False, True),
            record(0, "json_email", "c", True, False),
            record(0, "plain_email", "d", True, True),
        ]
        outcome = summarize_pairs(rows)
        self.assertEqual(outcome["overall"]["paired_accuracy_delta"], .25)
        self.assertEqual(outcome["overall"]["memory_only_success"], 2)
        self.assertEqual(outcome["overall"]["no_memory_only_success"], 1)
        self.assertEqual(outcome["overall"]["both_success"], 1)
        self.assertEqual(outcome["per_format"]["json_email"]["task_pairs"], 3)
        self.assertEqual(outcome["descriptive_mcnemar_exact_p"], 1)
        self.assertIsNone(outcome["seed_cluster_delta_interval"])

    def test_exact_mcnemar_no_discordance(self):
        self.assertEqual(mcnemar_exact_p(0, 0), 1)
        self.assertEqual(mcnemar_exact_p(5, 0), .0625)
        self.assertEqual(mcnemar_exact_p(0, 5), .0625)
        self.assertEqual(mcnemar_exact_p(4, 4), 1)

    def test_seed_cluster_bootstrap_reproducible(self):
        rows = []
        for seed in range(8):
            rows.append(record(seed, "json_email", "a", seed % 2 == 0, True))
            rows.append(record(seed, "plain_email", "b", False, seed % 3 == 0))
        first = summarize_pairs(rows, bootstrap_repetitions=300)
        second = summarize_pairs(rows, bootstrap_repetitions=300)
        self.assertEqual(first, second)
        interval = first["seed_cluster_delta_interval"]
        self.assertEqual(interval["distinct_seed_clusters"], 8)
        self.assertGreaterEqual(interval["upper"], interval["lower"])
        self.assertTrue(-1 <= interval["lower"] <= 1)
        self.assertTrue(-1 <= interval["upper"] <= 1)

    def test_fewer_than_five_clusters_no_ci(self):
        rows = [record(seed, "json_email", "a", False, True)
                for seed in range(4)]
        self.assertIsNone(seed_cluster_interval(rows))

    def test_invalid_and_duplicate_pairs_rejected(self):
        row = record(0, "plain_email", "a", True, False)
        with self.assertRaises(ValueError):
            summarize_pairs([row, row])
        with self.assertRaises(ValueError):
            summarize_pairs([])
        with self.assertRaises(ValueError):
            summarize_pairs([dict(row, no_memory=1)])
        with self.assertRaises(ValueError):
            summarize_pairs([dict(row, format="unknown")])
        with self.assertRaises(ValueError):
            summarize_pairs([dict(row, expected="secret")])

    def test_execution_errors_count_separately(self):
        rows = [
            record(1, "json_email", "a", False, True,
                   error_without=True),
            record(1, "plain_email", "b", False, False,
                   error_with=True),
        ]
        summary = summarize_pairs(rows)["overall"]
        self.assertEqual(summary["no_memory_execution_errors"], 1)
        self.assertEqual(summary["with_memory_execution_errors"], 1)

    def test_invalid_hyperparameters_fail_closed(self):
        rows = [record(1, "json_email", "a", False, True)]
        with self.assertRaises(ValueError):
            summarize_pairs(rows, bootstrap_repetitions=2)
        with self.assertRaises(ValueError):
            mcnemar_exact_p(-1, 1)


if __name__ == "__main__":
    unittest.main()
