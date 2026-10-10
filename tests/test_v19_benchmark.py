import unittest
from benchmarks.v19_benchmark import episode,benchmark
class V19BenchmarkTests(unittest.TestCase):
    def test_repeatable(self):
        self.assertEqual(episode(3,"adaptive"),episode(3,"adaptive"))
    def test_two_methods(self):
        self.assertEqual(set(benchmark(range(2))["results"]),{"fixed","adaptive"})
if __name__=="__main__":unittest.main()
