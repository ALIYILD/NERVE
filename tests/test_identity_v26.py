import tempfile,unittest
from pathlib import Path
from nerve_awim.identity_v26 import IdentityBoundRecovery,VerifiedIdentity
from nerve_awim.recovery_v25 import sign_approval
SECRET=b"simulation-secret-32bytes-minimum"
class FakeVerifier:
    def __init__(self,identity):self.identity=identity
    def verify(self,token,now):return self.identity if token=="test-assertion" else None
class IdentityTests(unittest.TestCase):
    def setup_controller(self,identity):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        c=IdentityBoundRecovery(secret=SECRET,ledger_path=str(Path(self.temp.name)/"ledger.db"),
            identity_verifier=FakeVerifier(identity),expected_issuer="test-idp",
            expected_audience="nerve",max_missing=1,recovery_samples=2)
        for _ in range(4):c.act()
        c.miss();c.ingest(0,position=.1,velocity=.1);c.ingest(1,position=.2,velocity=.2)
        return c
    def test_valid_verified_identity(self):
        identity=VerifiedIdentity("alice","test-idp","nerve",frozenset({"recovery-supervisor"}),200)
        c=self.setup_controller(identity)
        a=sign_approval(SECRET,"alice","supervisor",c.incident,"n1",200)
        self.assertTrue(c.authorize_identity("test-assertion",a,100))
    def test_signed_only_bypass_blocked(self):
        identity=VerifiedIdentity("alice","test-idp","nerve",frozenset({"recovery-supervisor"}),200)
        c=self.setup_controller(identity)
        a=sign_approval(SECRET,"alice","supervisor",c.incident,"n1",200)
        self.assertFalse(c.authorize_signed(a,100))
        self.assertEqual(c.phase,"awaiting_approval")
    def test_missing_identity(self):
        c=self.setup_controller(None)
        a=sign_approval(SECRET,"alice","supervisor",c.incident,"n1",200)
        self.assertFalse(c.authorize_identity("test-assertion",a,100))
    def test_role_denied(self):
        identity=VerifiedIdentity("alice","test-idp","nerve",frozenset({"viewer"}),200)
        c=self.setup_controller(identity)
        a=sign_approval(SECRET,"alice","supervisor",c.incident,"n1",200)
        self.assertFalse(c.authorize_identity("test-assertion",a,100))
    def test_expired_identity(self):
        identity=VerifiedIdentity("alice","test-idp","nerve",frozenset({"recovery-supervisor"}),99)
        c=self.setup_controller(identity)
        a=sign_approval(SECRET,"alice","supervisor",c.incident,"n1",200)
        self.assertFalse(c.authorize_identity("test-assertion",a,100))
    def test_wrong_issuer(self):
        identity=VerifiedIdentity("alice","unknown","nerve",frozenset({"recovery-supervisor"}),200)
        c=self.setup_controller(identity)
        a=sign_approval(SECRET,"alice","supervisor",c.incident,"n1",200)
        self.assertFalse(c.authorize_identity("test-assertion",a,100))
    def test_subject_mismatch(self):
        identity=VerifiedIdentity("bob","test-idp","nerve",frozenset({"recovery-supervisor"}),200)
        c=self.setup_controller(identity)
        a=sign_approval(SECRET,"alice","supervisor",c.incident,"n1",200)
        self.assertFalse(c.authorize_identity("test-assertion",a,100))
if __name__=="__main__":unittest.main()
