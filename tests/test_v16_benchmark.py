import unittest
from benchmarks.v16_benchmark import episode, benchmark

class V16BenchmarkTests(unittest.TestCase):
    def test_reproducible(self):
        self.assertEqual(episode(3,.15),episode(3,.15))
    def test_control_comparison(self):
        x=benchmark(range(2))
        self.assertEqual(x["seeds"],2)
        self.assertIn("uncertainty_gated",x["results"])
        self.assertGreaterEqual(x["results"]["uncertainty_gated"]["blocked_actions"],0)

if __name__=="__main__":unittest.main()
