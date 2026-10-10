import unittest
from benchmarks.v30_benchmark import benchmark
class BenchmarkV30Tests(unittest.TestCase):
    def test_both_capabilities(self):
        r=benchmark(20)
        self.assertEqual(r["specialist_completion"],20)
        self.assertEqual(r["single_specialist_supported"],10)
    def test_provenance(self):
        self.assertEqual(benchmark(10)["provenance_retained"],10)
if __name__=="__main__":unittest.main()
