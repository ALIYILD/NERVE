import unittest
from nerve_awim.recovery_v21 import SupervisedWorldCore
class RecoveryTests(unittest.TestCase):
    def test_lockout_and_approval(self):
        c=SupervisedWorldCore(max_missing=2,recovery_samples=2)
        c.miss();c.miss()
        self.assertIsNone(c.decide().action)
        c.observe_recovery(2,observed_now=2,position=.1,velocity=.1)
        c.observe_recovery(3,observed_now=3,position=.2,velocity=.2)
        self.assertEqual(c.recovery_status().phase,"awaiting_approval")
        self.assertIsNone(c.decide().action)
        self.assertTrue(c.approve_recovery(True))
        self.assertEqual(c.recovery_status().phase,"active")
        self.assertEqual(len(c.core.filter.actions),0)
        self.assertAlmostEqual(c.core.filter.state.position,.2)
        self.assertIsNotNone(c.decide().action)
    def test_duplicate_timestamp_not_recovery(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=2)
        c.miss()
        self.assertTrue(c.observe_recovery(1,observed_now=1,position=.1,velocity=.2))
        self.assertFalse(c.observe_recovery(1,observed_now=1,position=.1,velocity=.2))
        self.assertEqual(c.recovery_status().fresh_observations,1)
    def test_no_auto_approval_or_direct_action_bypass(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=1)
        c.miss();c.observe_recovery(1,observed_now=1,position=.1,velocity=.2)
        self.assertFalse(c.approve_recovery(False))
        self.assertIsNone(c.decide().action)
        with self.assertRaises(RuntimeError):c.act()
        with self.assertRaises(RuntimeError):c.choose()
    def test_historical_packet_is_not_recovery_evidence(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=1)
        c.act();c.ingest(0,position=.1,velocity=.1);c.miss()
        c.ingest(0,position=.2,velocity=.2)
        self.assertEqual(c.fresh_count,0)
        self.assertFalse(c.approve_recovery(True))
    def test_expired_evidence_cannot_be_refreshed_by_approval(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=1)
        c.miss();c.observe_recovery(1,observed_now=1,position=.1,velocity=.1)
        c.advance_time(2)
        self.assertFalse(c.approve_recovery(True))
        self.assertIsNone(c.decide().action)
    def test_missing_sample_discards_prior_recovery_progress(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=2)
        c.miss();c.observe_recovery(1,observed_now=1,position=.1,velocity=.1)
        c.miss()
        c.observe_recovery(3,observed_now=3,position=.2,velocity=.2)
        self.assertEqual(c.fresh_count,1)
        self.assertFalse(c.approve_recovery(True))
    def test_invalid_recovery_packet_does_not_advance_clock(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=1)
        c.miss()
        before=c._freshness_time
        for value in (None,float('nan'),True):
            with self.assertRaises(ValueError):
                c.observe_recovery(3,observed_now=3,position=value,velocity=.2)
        self.assertEqual(c._freshness_time,before)
        self.assertEqual(c.fresh_count,0)
    def test_long_gap_cannot_pool_recovery_samples(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=2)
        c.miss();c.observe_recovery(1,observed_now=1,position=.1,velocity=.1)
        c.observe_recovery(10,observed_now=10,position=.2,velocity=.2)
        self.assertEqual(c.fresh_count,1)
        self.assertFalse(c.approve_recovery(True))
    def test_out_of_envelope_evidence_cannot_resume(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=1)
        c.miss();c.observe_recovery(1,observed_now=1,position=7.,velocity=.1)
        self.assertFalse(c.approve_recovery(True))
        self.assertIsNone(c.decide().action)
    def test_stale_packet_advances_known_clock_without_recovery_credit(self):
        c=SupervisedWorldCore(max_missing=1,recovery_samples=1)
        c.miss();c.observe_recovery(1,observed_now=1,position=.1,velocity=.1)
        self.assertFalse(c.observe_recovery(1,observed_now=10,position=.1,velocity=.1))
        self.assertEqual(c._freshness_time,10)
        self.assertFalse(c.approve_recovery(True))
    def test_retrograde_action_time_packet_is_atomic(self):
        c=SupervisedWorldCore(max_missing=3,recovery_samples=1)
        c.act();c.act()
        before=(c._freshness_time,c.phase,c.fresh_count,c._recovery_observation)
        with self.assertRaises(ValueError):
            c.observe_recovery(0,observed_now=0,position=.1,velocity=.1)
        self.assertEqual((c._freshness_time,c.phase,c.fresh_count,c._recovery_observation),before)
    def test_latest_reseed_observation_must_be_current(self):
        c=SupervisedWorldCore(max_missing=3,recovery_samples=1)
        c.miss();c.miss();c.miss()
        self.assertTrue(c.observe_recovery(3,observed_now=4,position=.1,velocity=.1))
        self.assertFalse(c.approve_recovery(True))
        self.assertIsNone(c.decide().action)
        self.assertTrue(c.observe_recovery(4,observed_now=4,position=.2,velocity=.2))
        self.assertTrue(c.approve_recovery(True))
        self.assertEqual(c.epoch_origin,5)
        self.assertIsNotNone(c.decide().action)
    def test_bad_threshold(self):
        for value in (0,True):
            with self.assertRaises(ValueError):SupervisedWorldCore(recovery_samples=value)
if __name__=="__main__":unittest.main()
