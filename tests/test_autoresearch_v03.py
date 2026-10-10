import json
import tempfile
import unittest
from pathlib import Path
from nerve_awim.autoresearch_v03 import ResearchProposal, evaluate, experiment, demo

class AutoResearchV03Tests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(demo(), demo())
    def test_three_existing_benchmarks(self):
        self.assertEqual(set(evaluate(ResearchProposal("a", "unified"), (1, 2))),
                         {"memory", "sensory", "nonlinear"})
    def test_invalid_proposal(self):
        with self.assertRaises(ValueError):
            ResearchProposal("untrusted", "execute-python")
    def test_no_regression_gate_rejects_specialist(self):
        result = experiment([ResearchProposal("specialist", "specialist")])
        self.assertEqual(result["trials"][0]["decision"], "reject")
        self.assertEqual(result["selected"], "unified")
    def test_budget_and_duplicate_rejection(self):
        with self.assertRaises(ValueError):
            experiment([ResearchProposal("a", "unified"), ResearchProposal("a", "specialist")])
        with self.assertRaises(ValueError):
            experiment([ResearchProposal("a", "unified")], max_trials=0)
    def test_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "research.jsonl"
            experiment([ResearchProposal("a", "specialist")], ledger_path=path)
            self.assertEqual(len(path.read_text().splitlines()), 1)
            self.assertEqual(json.loads(path.read_text())["selected"], "unified")
    def test_holdout_not_in_trial(self):
        result = demo()
        self.assertNotIn("report_only_holdout", result["trials"][0])

if __name__ == "__main__":
    unittest.main()
