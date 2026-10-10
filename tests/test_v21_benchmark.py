import unittest
from benchmarks.v21_benchmark import episode,benchmark
class Benchmark21Tests(unittest.TestCase):
    def test_repeatability(self):
        self.assertEqual(episode(5),episode(5))
    def test_report(self):
        result=benchmark(range(2))
        self.assertEqual(result["seeds"],2)
        self.assertGreaterEqual(result["results"]["withheld"],0)
if __name__=="__main__":unittest.main()
