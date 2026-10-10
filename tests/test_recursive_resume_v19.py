"""Cross-run data-only evolutionary checkpoint is resumable and fail-closed."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.recursive_research_v19 import previous_checkpoint, run


class ContinuousResearchV19Tests(unittest.TestCase):
    def setUp(self):
        self.working = tempfile.TemporaryDirectory()
        self.addCleanup(self.working.cleanup)
        self.path = Path(self.working.name) / "prior.json"

    def test_resumes_typed_population_without_trusting_old_scores(self):
        before = run(seed=19, generations=4)
        self.path.write_text(json.dumps(before), encoding="utf-8")
        after = run(checkpoint=self.path, seed=20, generations=3)
        self.assertTrue(after["resumed_from_checkpoint"])
        self.assertEqual(after["baseline"], before["selected"])
        self.assertGreaterEqual(after["known_population_size"],
                                before["known_population_size"])
        self.assertLessEqual(after["candidates_evaluated"], 18)
        self.assertEqual(after["report_only_holdout"]["cross_tenant_leaks"], 0)

    def test_no_history_starts_from_default_safe_recipe(self):
        current = run(checkpoint=self.path, seed=19, generations=2)
        self.assertFalse(current["resumed_from_checkpoint"])
        self.assertEqual(current["baseline"],
                         {"token_weight": 3, "trigram_weight": 0})

    def test_checkpoint_import_refuses_arbitrary_code_and_invalid_fields(self):
        record = run(seed=19, generations=1)
        payloads = [
            dict(record, selected={"token_weight": "__import__('os')",
                                   "trigram_weight": 0}),
            dict(record, selected={"token_weight": 2, "trigram_weight": 1,
                                   "execute": "shell"}),
            dict(record, study_protocol="unrecognised"),
            dict(record, population_archive=[{
                "token_weight": 4, "trigram_weight": 99}]),
            dict(record, population_archive=[]),
        ]
        for payload in payloads:
            self.path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises((TypeError, ValueError)):
                previous_checkpoint(self.path)

    def test_forged_historical_metrics_not_used_for_selection(self):
        report = run(seed=4, generations=2)
        report["selected_validation"] = {
            "accuracy": 1, "cross_tenant_leaks": 0, "hits": 100,
            "queries": 100}
        report["status"] = "deployment_authorised"
        self.path.write_text(json.dumps(report), encoding="utf-8")
        follow = run(checkpoint=self.path, seed=5, generations=2)
        self.assertNotEqual(follow["status"], "deployment_authorised")
        self.assertEqual(follow["baseline_validation"]["queries"], 6)

    def test_archive_is_bounded(self):
        first = run(seed=19, generations=5)
        self.assertLessEqual(len(first["population_archive"]), 36)
        self.assertLessEqual(first["known_population_size"], 36)


if __name__ == "__main__":
    unittest.main()
