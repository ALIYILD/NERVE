import unittest
from nerve_awim.recovery_v22 import AuditedRecovery,Approval

class RecoveryV22Tests(unittest.TestCase):
    def prepare(self):
        c=AuditedRecovery(max_missing=1,recovery_samples=2)
        c.act();c.act();c.act()
        c.miss()
        c.ingest(0,velocity=.1);c.ingest(1,velocity=.2)
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
        c.miss();c.ingest(2,velocity=.3);c.ingest(3,velocity=.4)
        self.assertFalse(c.authorize(a))
    def test_boolean_approval_disabled(self):
        c=self.prepare()
        self.assertFalse(c.approve_recovery(True))
    def test_stale_packet_rejected(self):
        c=self.prepare()
        self.assertFalse(c.ingest(0,velocity=.1))
        self.assertEqual(c.fresh_count,2)
if __name__=="__main__":unittest.main()
