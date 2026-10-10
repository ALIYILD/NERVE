import unittest
from nerve_awim.key_rotation_v28 import RotatingIdentityVerifier
try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    jwt=None

@unittest.skipIf(jwt is None,"PyJWT crypto dependency missing")
class RotationTests(unittest.TestCase):
    def keyset(self,kid):
        import json
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        jwk.update({"kid":kid,"alg":"RS256"})
        return {"keys":[jwk]}
    def test_rotation_requires_operator(self):
        v=RotatingIdentityVerifier(issuer="https://idp.test",
            audience="nerve",jwks=self.keyset("one"))
        with self.assertRaises(PermissionError):
            v.rotate(jwks=self.keyset("two"))
        self.assertEqual(v.version,1)
    def test_successful_rotation(self):
        v=RotatingIdentityVerifier(issuer="https://idp.test",
            audience="nerve",jwks=self.keyset("one"))
        self.assertEqual(v.rotate(jwks=self.keyset("two"),authorised=True),2)
    def test_invalid_rotation_preserves_old(self):
        v=RotatingIdentityVerifier(issuer="https://idp.test",
            audience="nerve",jwks=self.keyset("one"))
        with self.assertRaises(ValueError):
            v.rotate(jwks={"keys":[]},authorised=True)
        self.assertEqual(v.version,1)
if __name__=="__main__":unittest.main()
