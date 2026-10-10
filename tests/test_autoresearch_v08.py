import unittest
from nerve_awim.autoresearch_v08 import evaluate,ReviewThresholds
class AggregateResearchTests(unittest.TestCase):
    def test_controller_not_eligible(self):
        r=evaluate()
        self.assertFalse(r["checks"]["controller_absolute_eligibility"])
        self.assertFalse(r["all_checks_pass"])
    def test_recovery_checks_pass(self):
        self.assertTrue(evaluate()["checks"]["simulated_recovery_transitions"])
    def test_budget_reporting(self):
        self.assertGreaterEqual(evaluate()["elapsed_seconds"],0)
    def test_extremely_small_budget_fails(self):
        self.assertFalse(evaluate(ReviewThresholds(0))["checks"]["runtime_budget"])
if __name__=="__main__":unittest.main()
