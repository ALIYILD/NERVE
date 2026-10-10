"""v2.7 OIDC JWT verification boundary with operator-pinned JWKS.

Only RS256 accepted. The JWKS must be securely provisioned by an operator;
this module neither discovers arbitrary URLs nor fetches untrusted keys.
Requires PyJWT[crypto]. No deployed IdP, revocation service or real identities.
"""
from dataclasses import dataclass
from .identity_v26 import VerifiedIdentity

class PinnedOIDCVerifier:
    def __init__(self, *, issuer, audience, jwks, role_claim="roles", leeway=0):
        if not issuer.startswith("https://") or not audience or not isinstance(jwks,dict):
            raise ValueError("pinned issuer, audience and JWKS required")
        if not isinstance(jwks.get("keys"),list) or leeway<0:
            raise ValueError("invalid JWKS or leeway")
        import jwt
        self.jwt=jwt
        self.issuer=issuer
        self.audience=audience
        self.role_claim=role_claim
        self.leeway=leeway
        self.keys={}
        for item in jwks["keys"]:
            if item.get("kty")!="RSA" or item.get("alg","RS256")!="RS256":
                continue
            kid=item.get("kid")
            if not isinstance(kid,str) or not kid or kid in self.keys:
                raise ValueError("invalid or duplicate key ID")
            self.keys[kid]=jwt.algorithms.RSAAlgorithm.from_jwk(__import__("json").dumps(item))
        if not self.keys:raise ValueError("no supported signing keys")
    def verify(self,token,now):
        try:
            if not isinstance(token,str) or not isinstance(now,int):
                return None
            header=self.jwt.get_unverified_header(token)
            if header.get("alg")!="RS256":
                return None
            key=self.keys.get(header.get("kid"))
            if key is None:return None
            claims=self.jwt.decode(token,key,algorithms=["RS256"],
                 issuer=self.issuer,audience=self.audience,leeway=self.leeway,
                 options={"require":["exp","iat","sub","iss","aud"]})
            issued=claims["iat"]; expiry=claims["exp"]
            if not isinstance(issued,int) or not isinstance(expiry,int):
                return None
            # Caller time is explicit for replayable tests, but live JWT
            # validation also checks system wall-clock via PyJWT.
            if issued>now+self.leeway or expiry<=now-self.leeway:
                return None
            roles=claims.get(self.role_claim,[])
            if not isinstance(roles,list) or not all(isinstance(r,str) for r in roles):
                return None
            return VerifiedIdentity(str(claims["sub"]),claims["iss"],
                self.audience,frozenset(roles),expiry)
        except (self.jwt.PyJWTError,ValueError,TypeError,KeyError):
            return None
