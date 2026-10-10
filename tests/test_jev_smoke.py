import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from nerve_awim.jev_optional import JevAdvice
from nerve_awim.jev_smoke import main, run_smoke


class FakeReviewer:
    def __init__(self):
        self.calls = 0

    def review_many(self, *, baseline, candidates):
        self.calls += 1
        self.observed_baseline = baseline
        self.observed_candidates = candidates
        return {
            name: JevAdvice(.25 if name == "case_a" else .9,
                            False, "jev-test", .1234,
                            {"input_tokens": 30, "output_tokens": 2})
            for name in candidates
        }


class JevLiveSmokeTests(unittest.TestCase):
    def test_fixed_synthetic_batch_and_safe_output(self):
        reviewer = FakeReviewer()
        report = run_smoke(reviewer)
        self.assertEqual(reviewer.calls, 1)
        self.assertTrue(report["connected"])
        self.assertEqual(report["batched_questions"], 2)
        self.assertEqual(report["regression_risks"]["case_b"], .9)
        self.assertEqual(set(reviewer.observed_baseline),
                         {"completion", "abort", "violations",
                          "goal_penalized", "prediction_penalized"})
        self.assertNotIn("TYPESAFE_API_KEY", str(report))

    def test_no_key_aborts_before_any_network(self):
        output = io.StringIO()
        with patch.dict("os.environ", {}, clear=True), redirect_stdout(output):
            status = main()
        self.assertEqual(status, 2)
        self.assertIn("No TYPESAFE_API_KEY", output.getvalue())
        self.assertNotIn("Bearer", output.getvalue())


if __name__ == "__main__":
    unittest.main()
