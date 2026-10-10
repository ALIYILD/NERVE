import unittest
from nerve_awim.worldcore_v20 import WorldCoreV2

class WorldCoreV20Tests(unittest.TestCase):
    def test_initial_decision(self):
        c=WorldCoreV2()
        self.assertIn(c.decide().action,(-1,0,1))
    def test_outage_refuses_action(self):
        c=WorldCoreV2(max_missing=2)
        c.miss();c.miss()
        r=c.decide()
        self.assertIsNone(r.action)
        self.assertEqual(r.status,"unavailable_or_infeasible")
    def test_new_sensor_restores_status(self):
        c=WorldCoreV2(max_missing=2)
        c.act();c.miss();c.miss()
        c.ingest(0,velocity=.2)
        self.assertEqual(c.last_packet_age,0)
    def test_observation_not_scored_twice(self):
        c=WorldCoreV2(min_samples=2)
        c.act();c.act()
        c.ingest(0,velocity=.2)
        before=c.auditor.observed
        c.ingest(0,velocity=.2)
        self.assertEqual(c.auditor.observed,before)
    def test_invalid_outage_setting(self):
        with self.assertRaises(ValueError):WorldCoreV2(max_missing=0)
if __name__=="__main__":unittest.main()
