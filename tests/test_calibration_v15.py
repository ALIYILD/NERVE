import unittest
from nerve_awim.calibration_v15 import RollingErrorInterval, evaluate_intervals

class CalibrationTests(unittest.TestCase):
    def test_warmup_no_interval(self):
        c=RollingErrorInterval(minimum=3)
        self.assertIsNone(c.interval(1))
        c.update(0,1);c.update(0,2)
        self.assertIsNone(c.radius())
        c.update(0,3)
        self.assertEqual(c.radius(),3)
    def test_test_before_update(self):
        stream=[(0,0)]*8+[(0,10)]
        report=evaluate_intervals(stream,minimum=4)
        self.assertEqual(report["issued"],5)
        self.assertLess(report["empirical_coverage"],1)
    def test_bounded_history(self):
        c=RollingErrorInterval(window=4,minimum=2)
        for i in range(20):c.update(0,i)
        self.assertEqual(c.summary()["count"],4)
    def test_invalid_values(self):
        c=RollingErrorInterval()
        with self.assertRaises(ValueError):c.update(float("nan"),1)
        with self.assertRaises(ValueError):RollingErrorInterval(coverage=1)
    def test_interval_contains_center(self):
        c=RollingErrorInterval(minimum=2)
        c.update(0,1);c.update(0,2)
        lo,hi=c.interval(5)
        self.assertLessEqual(lo,5)
        self.assertGreaterEqual(hi,5)

if __name__=="__main__":unittest.main()
