import unittest
from benchmarks.v17_benchmark import episode,benchmark

class V17BenchTests(unittest.TestCase):
    def test_repeatable(self):
        self.assertEqual(episode(5,"risk"),episode(5,"risk"))
    def test_three_policies(self):
        r=benchmark(range(2))
        self.assertEqual(set(r["results"]),{"ungated","gate","risk"})
    def test_completed_steps_bounded(self):
        self.assertLessEqual(episode(1,"risk")["completed_steps"],80)
if __name__=="__main__":unittest.main()
