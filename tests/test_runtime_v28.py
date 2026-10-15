import tempfile,unittest
from pathlib import Path
from nerve_awim.runtime_v28 import NerveResearchRuntime
from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.recovery_v25 import sign_approval

SECRET=b"simulation-secret-32bytes-minimum"
class FakeVerifier:
    def verify(self,token,now):
        if token!="valid":return None
        return VerifiedIdentity("operator","https://idp.test","nerve",
            frozenset({"recovery-supervisor"}),now+100)
class RuntimeTests(unittest.TestCase):
    def test_supervised_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            r=NerveResearchRuntime(verifier=FakeVerifier(),issuer="https://idp.test",
                audience="nerve",secret=SECRET,ledger_path=str(Path(d)/"db"),
                max_missing=1,recovery_samples=2)
            r.sensor_missing()
            self.assertIsNone(r.tick().action)
            r.observe_recovery(1,observed_now=1,position=.1,velocity=.1)
            r.observe_recovery(2,observed_now=2,position=.2,velocity=.2)
            r.advance_time(2)
            a=sign_approval(SECRET,"operator","supervisor",
                r.controller.incident,"nonce",200)
            self.assertFalse(r.authorise_recovery("bad",a,100))
            self.assertTrue(r.authorise_recovery("valid",a,100))
            result=r.tick()
            self.assertEqual(result.phase,"active")
            self.assertIsNotNone(result.action)
            r.advance_time(3)
            self.assertIsNone(r.tick().action)
    def test_no_automatic_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            r=NerveResearchRuntime(verifier=FakeVerifier(),issuer="https://idp.test",
                audience="nerve",secret=SECRET,ledger_path=str(Path(d)/"db"),
                max_missing=1,recovery_samples=2)
            r.sensor_missing()
            self.assertIsNone(r.tick().action)
if __name__=="__main__":unittest.main()
