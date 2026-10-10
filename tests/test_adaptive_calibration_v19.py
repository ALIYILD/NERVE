import unittest
from nerve_awim.adaptive_calibration_v19 import AdaptiveCoverageAuditor
class AdaptiveCalibrationTests(unittest.TestCase):
    def test_failure_alert_after_five_missing(self):
        a=AdaptiveCoverageAuditor(minimum=2)
        for _ in range(5):a.record(0,None)
        self.assertEqual(a.failure_alerts,1)
    def test_misses_expand_radius_scale(self):
        a=AdaptiveCoverageAuditor(minimum=2)
        a.record(0,1);a.record(0,1)
        a.record(0,10)
        self.assertGreater(a.scale,1)
    def test_no_outcome_leakage(self):
        a=AdaptiveCoverageAuditor(minimum=2)
        a.record(0,0);a.record(0,0)
        a.record(0,10)
        self.assertEqual(a.report().covered,0)
    def test_scale_bounded(self):
        a=AdaptiveCoverageAuditor(minimum=2)
        a.record(0,1);a.record(0,1)
        for _ in range(100):a.record(0,100)
        self.assertLessEqual(a.scale,4)
if __name__=="__main__":unittest.main()
