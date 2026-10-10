import unittest
from nerve_awim.calibrated_v16 import CalibratedController

class CalibratedControllerTests(unittest.TestCase):
    def test_unobserved_predictions_not_calibrated(self):
        c=CalibratedController(min_samples=2)
        c.act();c.act()
        self.assertIsNone(c.calibration.radius())
    def test_resolved_predictions_calibrate(self):
        c=CalibratedController(min_samples=2)
        c.act();c.act()
        c.ingest(0,velocity=0.5)
        c.ingest(1,velocity=0.4)
        self.assertIsNotNone(c.calibration.radius())
    def test_large_error_uses_safe_zero_action(self):
        c=CalibratedController(min_samples=2,radius_limit=.01)
        c.act();c.act()
        c.ingest(0,velocity=5)
        c.ingest(1,velocity=5)
        self.assertEqual(c.choose(),0)
    def test_invalid_limit(self):
        with self.assertRaises(ValueError):CalibratedController(radius_limit=0)

if __name__=="__main__":unittest.main()
