import unittest
from nerve_awim.recovery_v22 import AuditedRecovery,Approval

class RecoveryV22Tests(unittest.TestCase):
    def prepare(self):
        c=AuditedRecovery(max_missing=1,recovery_samples=2)
        c.miss()
        c.observe_recovery(1,observed_now=1,position=.1,velocity=.1);c.observe_recovery(2,observed_now=2,position=.2,velocity=.2)
        return c
    def test_requires_role_and_incident(self):
        c=self.prepare()
        self.assertFalse(c.authorize(Approval("x","viewer",c.incident,"n1")))
        self.assertFalse(c.authorize(Approval("x","supervisor",c.incident+1,"n1")))
    def test_simulated_approval(self):
        c=self.prepare()
        self.assertTrue(c.authorize(Approval("operator","supervisor",c.incident,"n1")))
        self.assertEqual(c.phase,"active")
    def test_replay_rejected(self):
        c=self.prepare()
        a=Approval("operator","supervisor",c.incident,"n1")
        self.assertTrue(c.authorize(a))
        c.miss()
        c.observe_recovery(4,observed_now=4,position=.3,velocity=.3);c.observe_recovery(5,observed_now=5,position=.4,velocity=.4)
        self.assertFalse(c.authorize(a))
    def test_boolean_approval_disabled(self):
        c=self.prepare()
        self.assertFalse(c.approve_recovery(True))
    def test_stale_packet_rejected(self):
        c=self.prepare()
        self.assertFalse(c.observe_recovery(1,observed_now=2,position=.1,velocity=.1))
        self.assertEqual(c.fresh_count,2)
if __name__=="__main__":unittest.main()
