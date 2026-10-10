import unittest
from nerve_awim.autoresearch_v05 import eligibility,experiment
from nerve_awim.autoresearch_v04 import Proposal
class EligibilityTests(unittest.TestCase):
    def test_failure_reasons(self):
        x=eligibility({"completion":.55,"abort":1,"violations":0})
        self.assertFalse(x.eligible)
        self.assertIn("episode_abort_detected",x.reasons)
    def test_ideal_metric_eligible(self):
        self.assertTrue(eligibility({"completion":1,"abort":0,"violations":0}).eligible)
    def test_current_worldcore_is_not_review_eligible(self):
        report=experiment([Proposal("long",8,.25)])
        self.assertFalse(report["eligible_for_deployment_review"])
    def test_bounded(self):
        with self.assertRaises(ValueError):
            experiment([Proposal(str(i),8,.25) for i in range(9)])
if __name__=="__main__":unittest.main()
