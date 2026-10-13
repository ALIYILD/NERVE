import tempfile,unittest
from pathlib import Path
from nerve_awim.observed_runtime_v29 import ObservedNerveRuntime
from nerve_awim.telemetry_v29 import EventTrace
from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.recovery_v25 import sign_approval
SECRET=b"simulation-secret-32bytes-minimum"
class Verifier:
    def verify(self,token,now):
        if token!="valid":return None
        return VerifiedIdentity("operator","https://test.example","nerve",
            frozenset({"recovery-supervisor"}),now+100)
class TelemetryTests(unittest.TestCase):
    def make_runtime(self,path):
        return ObservedNerveRuntime(verifier=Verifier(),issuer="https://test.example",
            audience="nerve",secret=SECRET,ledger_path=path,
            max_missing=1,recovery_samples=2)
    def test_bounded_events(self):
        t=EventTrace(capacity=2)
        for _ in range(3):t.record("sensor","ok")
        self.assertEqual(t.summary()["retained"],2)
        self.assertEqual(t.summary()["total"],3)
    def test_invalid_event(self):
        with self.assertRaises(ValueError):EventTrace().record("secret","ok")
    def test_end_to_end_denial_and_approval(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.make_runtime(str(Path(d)/"audit.db"))
            r.sensor_missing()
            self.assertIsNone(r.tick().action)
            r.observe_recovery(1,observed_now=1,position=.1,velocity=.1)
            r.observe_recovery(2,observed_now=2,position=.2,velocity=.2)
            r.advance_time(2)
            approval=sign_approval(SECRET,"operator","supervisor",
                                  r.runtime.controller.incident,"nonce-v29",200)
            self.assertFalse(r.authorise_recovery("invalid",approval,100))
            self.assertTrue(r.authorise_recovery("valid",approval,100))
            self.assertEqual(r.trace.summary()["denied"],1)
            result=r.tick()
            self.assertEqual(result.phase,"active")
            self.assertIsNotNone(result.action)
            r.advance_time(3)
            self.assertIsNone(r.tick().action)
            self.assertTrue(all(event.category in ("sensor","control","identity")
                                for event in r.trace.events))
if __name__=="__main__":unittest.main()
