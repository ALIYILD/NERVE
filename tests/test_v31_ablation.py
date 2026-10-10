import unittest
from benchmarks.v31_ablation import benchmark,episode
class AblationTests(unittest.TestCase):
    def test_deterministic(self):self.assertEqual(episode(5),episode(5))
    def test_three_methods(self):
        r=benchmark(range(2))
        self.assertEqual(set(r["results"]),{"single_memory","specialist_memory","specialist_fixed"})
    def test_all_positive(self):
        self.assertTrue(all(x>=0 for x in episode(2).values()))
if __name__=="__main__":unittest.main()
