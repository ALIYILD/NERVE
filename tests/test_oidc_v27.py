import time,unittest
from nerve_awim.oidc_v27 import PinnedOIDCVerifier
try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    jwt=None

@unittest.skipIf(jwt is None,"PyJWT[crypto] required")
class OIDCV27Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        import json
        cls.jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.private.public_key()))
        cls.jwk.update({"kid":"test-rsa","alg":"RS256"})
        cls.verifier=PinnedOIDCVerifier(issuer="https://idp.test",audience="nerve",
            jwks={"keys":[cls.jwk]})
    def token(self,**changes):
        now=int(time.time())
        claims=dict(sub="alice",iss="https://idp.test",aud="nerve",
            exp=now+300,iat=now-5,roles=["recovery-supervisor"])
        claims.update(changes)
        return jwt.encode(claims,self.private,algorithm="RS256",headers={"kid":"test-rsa"})
    def test_valid(self):
        self.assertIn("recovery-supervisor",
            self.verifier.verify(self.token(),int(time.time())).roles)
    def test_wrong_audience(self):
        self.assertIsNone(self.verifier.verify(self.token(aud="elsewhere"),int(time.time())))
    def test_wrong_issuer(self):
        self.assertIsNone(self.verifier.verify(self.token(iss="https://evil.test"),int(time.time())))
    def test_unknown_key(self):
        forged=jwt.encode(dict(sub="alice",iss="https://idp.test",aud="nerve",
            exp=int(time.time())+300,iat=int(time.time())-5),
            rsa.generate_private_key(public_exponent=65537,key_size=2048),
            algorithm="RS256",headers={"kid":"test-rsa"})
        self.assertIsNone(self.verifier.verify(forged,int(time.time())))
    def test_expired(self):
        self.assertIsNone(self.verifier.verify(self.token(exp=int(time.time())-100),int(time.time())))
    def test_invalid_role_shape(self):
        self.assertIsNone(self.verifier.verify(self.token(roles="supervisor"),int(time.time())))
if __name__=="__main__":unittest.main()
