import unittest
from benchmarks.v32_multimodal import episode,benchmark
class MultimodalTests(unittest.TestCase):
    def test_repeatable(self):self.assertEqual(episode(4),episode(4))
    def test_equivalent_information_no_artificial_advantage(self):
        r=episode(7)
        self.assertAlmostEqual(r["single_fused"],r["specialist_fused"],places=12)
    def test_missing_sensor(self):
        self.assertGreater(episode(7,missing=.5)["missing"],0)
    def test_report(self):self.assertEqual(benchmark(range(2))["seeds"],2)
if __name__=="__main__":unittest.main()
