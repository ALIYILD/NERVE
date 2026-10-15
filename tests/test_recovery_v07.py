"""v0.7 incident-bound recovery regression tests (simulation only)."""
import tempfile
import unittest
from pathlib import Path
from nerve_awim.runtime_v28 import NerveResearchRuntime
from nerve_awim.recovery_v25 import sign_approval
from nerve_awim.identity_v26 import VerifiedIdentity

SECRET=b"synthetic-test-secret-not-for-live-use"
class Verifier:
    def verify(self,token,now):
        if token!="valid":return None
        return VerifiedIdentity("operator","https://idp.test","nerve",
            frozenset({"recovery-supervisor"}),now+100)

class RecoveryV07(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime=NerveResearchRuntime(verifier=Verifier(),
            issuer="https://idp.test",audience="nerve",secret=SECRET,
            ledger_path=str(Path(self.tmp.name)/"approvals.db"),
            max_missing=1,recovery_samples=2)
        self.runtime.sensor_missing()
    def approval(self,incident=None,nonce="unique"):
        return sign_approval(SECRET,"operator","supervisor",
            self.runtime.controller.incident if incident is None else incident,
            nonce,200)
    def evidence(self,inconsistent=False):
        self.runtime.observe_recovery(1,observed_now=1,position=.1,velocity=.1)
        self.runtime.observe_recovery(2,observed_now=2,position=3. if inconsistent else .2,
                             velocity=2. if inconsistent else .2)
    def test_no_identity(self):
        self.evidence()
        self.assertFalse(self.runtime.authorise_recovery("bad",self.approval(),100))
        self.assertIsNone(self.runtime.tick().action)
    def test_wrong_incident(self):
        self.evidence()
        self.assertFalse(self.runtime.authorise_recovery("valid",self.approval(999),100))
    def test_inconsistent_evidence(self):
        self.evidence(inconsistent=True)
        self.assertFalse(self.runtime.authorise_recovery("valid",self.approval(),100))
    def test_replay(self):
        self.evidence()
        a=self.approval()
        self.assertTrue(self.runtime.authorise_recovery("valid",a,100))
        self.runtime.sensor_missing()
        self.runtime.observe_recovery(3,observed_now=3,position=.3,velocity=.2)
        self.runtime.observe_recovery(4,observed_now=4,position=.4,velocity=.2)
        self.assertFalse(self.runtime.authorise_recovery("valid",a,100))
    def test_valid_path(self):
        self.evidence()
        self.assertTrue(self.runtime.authorise_recovery("valid",self.approval(),100))
        result=self.runtime.tick()
        self.assertEqual(result.phase,"active")
        self.assertIsNotNone(result.action)
if __name__=="__main__":unittest.main()
