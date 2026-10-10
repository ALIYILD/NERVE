import unittest
from nerve_awim.recovery_v21 import SupervisedWorldCore
class RecoveryTests(unittest.TestCase):
    def test_lockout_and_approval(self):
        c=SupervisedWorldCore(max_missing=2,recovery_samples=2)
        c.act();c.act();c.act()
        c.miss();c.miss()
        self.assertIsNone(c.decide().action)
        c.ingest(0,velocity=.1);c.ingest(1,velocity=.2)
        self.assertEqual(c.recovery_status().phase,"awaiting_approval")
        self.assertIsNone(c.decide().action)
        self.assertTrue(c.approve_recovery(True))
        self.assertEqual(c.recovery_status().phase,"active")
    def test_duplicate_timestamp_not_recovery(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=2)
        c.act();c.act();c.miss()
        c.ingest(0,velocity=.2)
        c.ingest(0,velocity=.2)
        self.assertEqual(c.recovery_status().fresh_observations,1)
    def test_no_auto_approval(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=1)
        c.act();c.miss();c.ingest(0,velocity=.2)
        self.assertFalse(c.approve_recovery(False))
        self.assertIsNone(c.decide().action)
    def test_bad_threshold(self):
        with self.assertRaises(ValueError):SupervisedWorldCore(recovery_samples=0)
if __name__=="__main__":unittest.main()
