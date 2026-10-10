import unittest
from nerve_awim.integrated_v13 import SensorOnlyController

class IntegrationTests(unittest.TestCase):
    def test_initial_state(self):
        c=SensorOnlyController()
        self.assertIn(c.choose().action,(-1,0,1))
    def test_observation_replay(self):
        c=SensorOnlyController()
        c.act();c.act()
        before=c.filter.state.velocity
        c.ingest(0,position=0.3,velocity=0.2)
        self.assertNotEqual(before,c.filter.state.velocity)
    def test_no_future_leakage(self):
        c=SensorOnlyController()
        with self.assertRaises(ValueError):c.ingest(0,velocity=0.2)
    def test_rejects_nan(self):
        c=SensorOnlyController()
        c.act()
        with self.assertRaises(ValueError):c.ingest(0,position=float("nan"))
    def test_actions_constrained(self):
        c=SensorOnlyController(bound=0.2)
        for _ in range(5):self.assertIn(c.act().action,(-1,0,1))
    def test_conservative_gain_bounds(self):
        c=SensorOnlyController(learning_rate=.5)
        c.act();c.act();c.act()
        c.ingest(0,velocity=.1);c.ingest(1,velocity=.2)
        self.assertTrue(0.01<=c.gain<=1)
    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):SensorOnlyController(horizon=6)

if __name__=="__main__":unittest.main()
