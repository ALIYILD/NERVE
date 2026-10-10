import unittest
from nerve_awim.recovery_v22 import Approval
from nerve_awim.recovery_v24 import EvidenceGatedRecovery
class RecoveryV24Tests(unittest.TestCase):
    def controller(self):
        c=EvidenceGatedRecovery(max_missing=1,recovery_samples=2)
        for _ in range(4):c.act()
        c.miss()
        return c
    def test_valid_evidence_and_approval(self):
        c=self.controller()
        c.ingest(0,position=.1,velocity=.1)
        c.ingest(1,position=.2,velocity=.2)
        self.assertTrue(c.authorize(Approval("supervisor","supervisor",c.incident,"n1")))
    def test_contradiction_blocks_approval(self):
        c=self.controller()
        c.ingest(0,position=.1,velocity=.1)
        c.ingest(1,position=.2,velocity=1.5)
        self.assertFalse(c.authorize(Approval("supervisor","supervisor",c.incident,"n1")))
    def test_incomplete_evidence_blocks(self):
        c=self.controller()
        c.ingest(0,velocity=.1);c.ingest(1,velocity=.2)
        self.assertFalse(c.authorize(Approval("s","supervisor",c.incident,"n1")))
    def test_replayed_nonce_fails(self):
        c=self.controller()
        c.ingest(0,position=.1,velocity=.1);c.ingest(1,position=.2,velocity=.2)
        a=Approval("s","supervisor",c.incident,"n1")
        self.assertTrue(c.authorize(a))
        self.assertFalse(c.authorize(a))
if __name__=="__main__":unittest.main()
