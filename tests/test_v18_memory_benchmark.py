"""Validate that v1.8 benchmark reports simulated results honestly."""
import unittest
from benchmarks.v18_memory_retrieval import benchmark, FAMILIES


class MemoryRetrievalBenchmarkTests(unittest.TestCase):
    def test_five_families_and_query_budget(self):
        result = benchmark()
        self.assertEqual(result["families"], 5)
        self.assertEqual(result["queries"], 10)

    def test_constructed_paraphrase_limitations(self):
        result = benchmark()
        self.assertEqual(result["results"]["lexical"]["exact_recall_at_1"], 1.)
        self.assertEqual(result["results"]["lexical"]["paraphrase_recall_at_1"], 0.)
        self.assertEqual(result["results"]["semantic"]["recall_at_1"], 1.)
        self.assertIn("NOT Mem0 OSS", result["disclaimer"])

    def test_cross_tenant_provider_invocations_blocked(self):
        result = benchmark()
        self.assertEqual(result["cross_tenant_results"], 0)
        self.assertEqual(result["cross_tenant_provider_calls"], 0)

    def test_local_latency_is_reported_not_real_latency(self):
        result = benchmark()
        for mode in ("semantic", "lexical"):
            scores = result["results"][mode]
            self.assertGreaterEqual(scores["p50_local_ms"], 0)
            self.assertGreaterEqual(scores["p95_local_ms"], 0)
        self.assertIn("local test overhead", result["disclaimer"])


if __name__ == "__main__":
    unittest.main()
