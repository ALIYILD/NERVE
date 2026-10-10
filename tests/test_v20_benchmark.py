import unittest
from benchmarks.v20_benchmark import episode,benchmark
class V20BenchmarkTests(unittest.TestCase):
    def test_determinism(self):
        self.assertEqual(episode(4),episode(4))
    def test_comparison(self):
        self.assertEqual(set(benchmark(range(2))["results"]),{"v17","v20"})
if __name__=="__main__":unittest.main()
