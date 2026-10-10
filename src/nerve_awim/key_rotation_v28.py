"""Operator-controlled JWKS rotations for the offline OIDC verifier.

No network retrieval. Replacement is atomic at object level; callers must
provision trusted keysets through a separate secure process.
"""
from .oidc_v27 import PinnedOIDCVerifier

class RotatingIdentityVerifier:
    def __init__(self, *, issuer, audience, jwks):
        self.issuer,self.audience=issuer,audience
        self._active=PinnedOIDCVerifier(issuer=issuer,audience=audience,jwks=jwks)
        self.version=1
    def verify(self, token, now):
        return self._active.verify(token,now)
    def rotate(self, *, jwks, authorised=False):
        if authorised is not True:
            raise PermissionError("trusted operator authorisation required")
        candidate=PinnedOIDCVerifier(issuer=self.issuer,
            audience=self.audience,jwks=jwks)
        self._active=candidate
        self.version+=1
        return self.version
