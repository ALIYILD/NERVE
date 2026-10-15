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
    def test_delayed_sensor_retains_elapsed_age(self):
        c=WorldCoreV2(max_missing=2)
        c.act();c.miss();c.miss()
        c.ingest(0,velocity=.2)
        self.assertEqual(c.last_packet_age,1)
    def test_observation_not_scored_twice(self):
        c=WorldCoreV2(min_samples=2)
        c.act();c.act()
        c.ingest(0,velocity=.2)
        before=c.auditor.observed
        c.ingest(0,velocity=.2)
        self.assertEqual(c.auditor.observed,before)
    def test_duplicate_packet_cannot_restore_outage(self):
        c=WorldCoreV2(max_missing=2)
        c.act();c.ingest(0,velocity=.2)
        c.miss();c.miss()
        for _ in range(3):
            c.ingest(0,velocity=.2)
            self.assertEqual(c.last_packet_age,2)
            self.assertIsNone(c.decide().action)

    def test_older_correction_updates_estimator_not_liveness(self):
        c=WorldCoreV2(max_missing=2)
        c.act();c.act();c.ingest(1,velocity=.2)
        c.miss();c.miss()
        c.ingest(0,position=.1)
        self.assertEqual(c.core.filter.readings[0][0],.1)
        self.assertEqual(c.latest_observation_timestamp,1)
        self.assertEqual(c.last_packet_age,2)
        self.assertIsNone(c.decide().action)

    def test_delayed_first_observation_retains_step_age(self):
        c=WorldCoreV2(max_missing=3)
        c.act();c.act();c.act()
        c.ingest(0,velocity=.2)
        self.assertEqual(c.last_packet_age,2)
        c.ingest(2,velocity=.2)
        self.assertEqual(c.last_packet_age,0)

    def test_invalid_packet_does_not_advance_freshness(self):
        c=WorldCoreV2(max_missing=2)
        c.act();c.ingest(0,velocity=.2);c.miss()
        for timestamp,value in ((True,.2),(1,.2),(0,float('nan'))):
            with self.assertRaises(ValueError):c.ingest(timestamp,velocity=value)
            self.assertEqual(c.latest_observation_timestamp,0)
            self.assertEqual(c.last_packet_age,1)
        with self.assertRaises(ValueError):WorldCoreV2(max_missing=True)

    def test_duplicate_arrivals_cannot_hide_action_time(self):
        c=WorldCoreV2(max_missing=3)
        c.act();c.ingest(0,velocity=.2)
        for _ in range(3):
            c.ingest(0,velocity=.2);c.act()
        c.ingest(0,velocity=.2)
        self.assertIsNone(c.decide().action)

    def test_newer_historical_packet_cannot_erase_missed_time(self):
        c=WorldCoreV2(max_missing=3)
        c.act();c.act();c.act();c.ingest(0,velocity=.2)
        c.miss();c.miss();c.miss()
        c.ingest(1,velocity=.2)
        self.assertGreaterEqual(c.last_packet_age,3)
        self.assertIsNone(c.decide().action)

    def test_fresh_observations_allow_continued_actions(self):
        c=WorldCoreV2(max_missing=2)
        for timestamp in range(10):
            c.act()
            c.ingest(timestamp,position=0.,velocity=0.)
            self.assertEqual(c.last_packet_age,0)

    def test_action_time_without_packets_expires(self):
        c=WorldCoreV2(max_missing=2)
        c.act();c.act()
        self.assertIsNone(c.decide().action)

    def test_reseed_uses_measured_prior_without_fabricated_action(self):
        c=WorldCoreV2(max_missing=2,estimator="drift")
        c.act();c.ingest(0,position=.1,velocity=.1)
        gain=c.core.gain
        c.advance_time(3)
        c._reseed_observation(3,observed_now=3,position=.4,velocity=.2)
        self.assertEqual(c.core.filter.actions,[])
        self.assertEqual(c.pending_predictions,{})
        self.assertEqual(c.core.filter.state.position,.4)
        self.assertEqual(c.core.filter.state.velocity,.2)
        self.assertEqual(c.core.gain,gain)
        self.assertEqual(c.epoch_origin,4)
        with self.assertRaises(ValueError):c.ingest(0,velocity=.1)
        c.act()
        c.ingest(4,position=.5,velocity=.1)
        self.assertEqual(c.latest_observation_timestamp,4)
        self.assertIn(0,c.core.filter.readings)
        self.assertEqual(c.last_packet_age,0)

    def test_reseed_rejects_expired_or_invalid_without_mutation(self):
        c=WorldCoreV2(max_missing=2)
        c.act();c.ingest(0,velocity=.1);c.advance_time(4)
        old=c.core.filter
        for timestamp,now,position in ((1,4,.1),(3,4,.1),(5,4,.1),(4,4,float("nan"))):
            with self.assertRaises(ValueError):
                c._reseed_observation(timestamp,observed_now=now,position=position,velocity=.1)
            self.assertIs(c.core.filter,old)
            self.assertEqual(c.latest_observation_timestamp,0)
        with self.assertRaises(ValueError):c.advance_time(True)
        with self.assertRaises(ValueError):c.advance_time(3)

    def test_invalid_outage_setting(self):
        with self.assertRaises(ValueError):WorldCoreV2(max_missing=0)
if __name__=="__main__":unittest.main()
