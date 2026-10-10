import unittest
from nerve_awim.fusion_v12 import LaggedPositionVelocityFilter

class FusionTests(unittest.TestCase):
    def test_replay_delayed_observation(self):
        f = LaggedPositionVelocityFilter()
        f.step(1)
        f.step(0)
        before = f.state
        f.observe(0, velocity=0.5, position=0.3)
        self.assertNotEqual(before.velocity, f.state.velocity)
    def test_invalid_timestamp(self):
        f = LaggedPositionVelocityFilter()
        with self.assertRaises(ValueError):
            f.observe(0, velocity=1)

if __name__ == "__main__":
    unittest.main()
