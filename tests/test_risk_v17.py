import unittest
from nerve_awim.risk_v17 import RiskAwareController

class RiskControllerTests(unittest.TestCase):
    def test_choices(self):
        c=RiskAwareController()
        self.assertIn(c.act(),(-1,0,1))
    def test_uses_feedback(self):
        c=RiskAwareController(min_samples=2)
        c.act();c.act()
        c.ingest(0,velocity=.5);c.ingest(1,velocity=.6)
        self.assertIsNotNone(c.calibration.radius())
    def test_infeasible_is_explicit(self):
        c=RiskAwareController(safe_position=.001,safe_velocity=.001)
        c.core.filter.step(1)
        with self.assertRaises(RuntimeError):c.act()
    def test_invalid_risk(self):
        with self.assertRaises(ValueError):RiskAwareController(risk_aversion=-1)
    def test_positive_limits(self):
        with self.assertRaises(ValueError):RiskAwareController(safe_position=0)
if __name__=="__main__":unittest.main()
