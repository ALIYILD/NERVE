"""Safe, offline validation of advisory Jev comparison and scoring."""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from nerve_awim.jev_agreement_v12 import (
    BASELINE, CASES, SyntheticFixtureReviewer, compare,
    deterministic_assessment, main,
)
from nerve_awim.jev_optional import JevAdvice


class FakeAllSafe:
    def review_many(self, *, baseline, candidates):
        return {
            name: JevAdvice(0.0, False, "mock-optimistic", .01, {})
            for name in candidates
        }


class FakeMissing:
    def review_many(self, *, baseline, candidates):
        return {"only_one": JevAdvice(.5, False, "mock", 0, {})}


class JevAgreementV12Tests(unittest.TestCase):
    def test_fixture_is_explicit_not_real_jev(self):
        report = compare(SyntheticFixtureReviewer())
        self.assertEqual(report["comparison_cases"], 6)
        self.assertEqual(report["reviewer"], "synthetic-fixture-not-jev")
        self.assertEqual(report["agreement_fraction"], 4/6)
        self.assertEqual(report["confusion"], {
            "true_positive": 3, "false_positive": 1,
            "true_negative": 1, "false_negative": 1,
        })

    def test_deterministic_acceptance_cannot_be_overridden(self):
        report = compare(FakeAllSafe())
        cases = {item["case"]: item for item in report["cases"]}
        self.assertFalse(cases["constraint_violation"]["candidate_for_human_review"])
        self.assertFalse(cases["unexpected_abort"]["candidate_for_human_review"])
        self.assertFalse(cases["lower_completion"]["candidate_for_human_review"])
        self.assertTrue(cases["safer_goal"]["candidate_for_human_review"])

    def test_recovery_policy_not_inferred_from_jev(self):
        blocked = deterministic_assessment(CASES["constraint_violation"])
        self.assertFalse(blocked["candidate_for_review"])
        self.assertIn("constraint_violation_detected", blocked["reasons"])

    def test_unanswered_questions_rejected(self):
        with self.assertRaises(ValueError):
            compare(FakeMissing())

    def test_default_cli_no_api_key_or_network(self):
        stream = io.StringIO()
        with patch.dict("os.environ", {}, clear=True), redirect_stdout(stream):
            self.assertEqual(main([]), 0)
        self.assertIn("synthetic-fixture-not-jev", stream.getvalue())
        self.assertIn("independent acceptance", stream.getvalue())

    def test_live_without_key_fails_before_network(self):
        stream = io.StringIO()
        with patch.dict("os.environ", {}, clear=True), redirect_stdout(stream):
            self.assertEqual(main(["--live"]), 2)
        self.assertIn("comparison unavailable", stream.getvalue())
        self.assertNotIn("Authorization", stream.getvalue())

    def test_reference_invariant(self):
        self.assertEqual(BASELINE["violations"], 0)
        self.assertEqual(len(CASES), 6)


if __name__ == "__main__":
    unittest.main()
