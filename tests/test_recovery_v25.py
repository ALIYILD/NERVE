import tempfile,unittest
from pathlib import Path
from nerve_awim.recovery_v25 import SignedRecovery,sign_approval

SECRET=b"simulation-secret-32bytes-minimum"
class SignedRecoveryTests(unittest.TestCase):
    def build(self,path):
        c=SignedRecovery(secret=SECRET,ledger_path=path,max_missing=1,recovery_samples=2)
        c.miss()
        c.observe_recovery(1,observed_now=1,position=.1,velocity=.1)
        c.observe_recovery(2,observed_now=2,position=.2,velocity=.2)
        return c
    def test_valid_signature(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.build(str(Path(d)/"events.db"))
            a=sign_approval(SECRET,"reviewer","supervisor",c.incident,"nonce-a",200)
            self.assertTrue(c.authorize_signed(a,100))
            self.assertEqual(c.phase,"active")
            self.assertIn("approval_accepted",[r[1] for r in c.ledger.records()])
    def test_forgery_and_expiry(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.build(str(Path(d)/"events.db"))
            forged=sign_approval(b"wrong-simulation-secret-long","reviewer","supervisor",c.incident,"n1",200)
            expired=sign_approval(SECRET,"reviewer","supervisor",c.incident,"n2",99)
            self.assertFalse(c.authorize_signed(forged,100))
            self.assertFalse(c.authorize_signed(expired,100))
    def test_legacy_bypass_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.build(str(Path(d)/"events.db"))
            self.assertFalse(c.authorize(True))
            self.assertFalse(c.approve_recovery(True))
    def test_durable_replay_denied(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"events.db")
            c=self.build(path)
            a=sign_approval(SECRET,"reviewer","supervisor",c.incident,"once",200)
            self.assertTrue(c.authorize_signed(a,100))
            c2=self.build(path)
            self.assertFalse(c2.authorize_signed(a,101))
            self.assertIn("replay_denied",[r[1] for r in c2.ledger.records()])
    def test_expired_sensor_evidence_does_not_consume_signed_nonce(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.build(str(Path(d)/"events.db"))
            a=sign_approval(SECRET,"reviewer","supervisor",c.incident,"fresh-only",200)
            c.advance_time(3)
            self.assertFalse(c.authorize_signed(a,100))
            self.assertNotIn("approval_accepted",[r[1] for r in c.ledger.records()])
            c.observe_recovery(4,observed_now=4,position=.3,velocity=.2)
            c.observe_recovery(5,observed_now=5,position=.4,velocity=.2)
            self.assertTrue(c.authorize_signed(a,101))
    def test_short_secret_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                SignedRecovery(secret=b"short",ledger_path=str(Path(d)/"db"))
if __name__=="__main__":unittest.main()
