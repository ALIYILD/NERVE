import unittest
from nerve_awim.drift_v14 import DriftAwareGain
from nerve_awim.integrated_v13 import SensorOnlyController
from benchmarks.v13_benchmark import multi_regime_benchmark

class DriftTests(unittest.TestCase):
    def test_no_duplicate_learning(self):
        m=DriftAwareGain()
        self.assertTrue(m.update(1,1,0,.5))
        old=m.gain
        self.assertFalse(m.update(1,1,0,.5))
        self.assertEqual(m.gain,old)
    def test_drift_trigger(self):
        m=DriftAwareGain(initial=.25)
        m.update(1,1,0,.65)
        self.assertEqual(m.drift_count,1)
    def test_no_learning_from_zero_action(self):
        m=DriftAwareGain()
        self.assertFalse(m.update(1,0,0,.4))
    def test_integrated_delayed_packets(self):
        c=SensorOnlyController(estimator='drift')
        for _ in range(4):c.act()
        c.ingest(0,velocity=0.1);c.ingest(1,velocity=0.3)
        self.assertTrue(0.01<=c.gain<=1.0)
    def test_drift_benchmark_report(self):
        r=multi_regime_benchmark(range(2))
        self.assertIn("drift",r)
        self.assertGreaterEqual(r["drift"]["goal_error"],0)
    def test_invalid_estimator(self):
        with self.assertRaises(ValueError):SensorOnlyController(estimator='unknown')
if __name__=="__main__":unittest.main()
