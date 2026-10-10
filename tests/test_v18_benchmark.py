import unittest
from benchmarks.v18_benchmark import episode, benchmark
class StressTests(unittest.TestCase):
    def test_repeatable(self):
        self.assertEqual(episode(5,True),episode(5,True))
    def test_outage_increases_missing(self):
        self.assertGreater(episode(7,True)["outages"],episode(7,False)["outages"])
    def test_benchmark_two_conditions(self):
        b=benchmark(range(2))
        self.assertEqual(set(b["results"]),{"normal","abrupt_outage"})
if __name__=="__main__":unittest.main()
