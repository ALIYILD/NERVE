import unittest
from benchmarks.v13_benchmark import benchmark, experiment, multi_regime_benchmark

class BenchmarkTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(experiment(7,True),experiment(7,True))
    def test_multi_seed_report(self):
        result=benchmark(range(3))
        self.assertEqual(result["config"]["seeds"],3)
        self.assertEqual(set(result["adaptive"]),set(result["frozen"]))
        self.assertGreaterEqual(result["adaptive"]["goal_error"],0)
    def test_multiple_regimes(self):
        report=multi_regime_benchmark(range(2))
        self.assertEqual(len(report["config"]["regimes"]),4)
        self.assertEqual(report["config"]["seeds"],2)
    def test_exactly_frozen_gain(self):
        from nerve_awim.integrated_v13 import SensorOnlyController
        c=SensorOnlyController(learning_rate=0)
        c.act();c.act();c.ingest(0,velocity=.3);c.ingest(1,velocity=.5)
        self.assertEqual(c.gain,.27)
    def test_frozen_and_adaptive_have_same_config(self):
        a=experiment(3,True)
        b=experiment(3,False)
        self.assertEqual(a.keys(),b.keys())

if __name__=="__main__": unittest.main()
