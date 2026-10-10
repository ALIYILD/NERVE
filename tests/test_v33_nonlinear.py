import unittest
from benchmarks.v33_nonlinear import episode,benchmark
class NonlinearTests(unittest.TestCase):
    def test_deterministic(self):self.assertEqual(episode(9),episode(9))
    def test_equal_parameter_models(self):
        r=episode(3)
        self.assertAlmostEqual(r["unified"],r["specialists"],places=12)
    def test_multiseed(self):self.assertEqual(benchmark(range(3))["seeds"],3)
if __name__=="__main__":unittest.main()
