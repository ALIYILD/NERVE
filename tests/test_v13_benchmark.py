import unittest
from benchmarks.v13_benchmark import benchmark, experiment

class BenchmarkTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(experiment(7,True),experiment(7,True))
    def test_multi_seed_report(self):
        result=benchmark(range(3))
        self.assertEqual(result["config"]["seeds"],3)
        self.assertEqual(set(result["adaptive"]),set(result["frozen"]))
        self.assertGreaterEqual(result["adaptive"]["goal_error"],0)
    def test_frozen_and_adaptive_have_same_config(self):
        a=experiment(3,True)
        b=experiment(3,False)
        self.assertEqual(a.keys(),b.keys())

if __name__=="__main__": unittest.main()
