"""v2.6 identity-provider verification boundary (simulation adapter).

The identity verifier is injected and must independently validate signed
identity assertions from a trusted IdP. This module intentionally does NOT
accept free-form role claims or trust an AI agent to grant approval.
No production IdP or device safety integration is provided.
"""
from dataclasses import dataclass
from typing import Protocol
from .recovery_v25 import SignedRecovery,SignedApproval

@dataclass(frozen=True)
class VerifiedIdentity:
    subject:str
    issuer:str
    audience:str
    roles:frozenset[str]
    expires_at:int

class IdentityVerifier(Protocol):
    def verify(self,token:str,now:int)->VerifiedIdentity|None: ...

class IdentityBoundRecovery(SignedRecovery):
    def __init__(self,*,identity_verifier:IdentityVerifier,expected_issuer:str,
                 expected_audience:str,**kwargs):
        if not expected_issuer or not expected_audience:raise ValueError("issuer/audience required")
        super().__init__(**kwargs)
        self.verifier=identity_verifier
        self.issuer=expected_issuer
        self.audience=expected_audience
    def authorize_signed(self,approval:SignedApproval,now:int)->bool:
        """Block inherited signing-only bypass: identity is also mandatory."""
        return False
    def authorize_identity(self,token:str,approval:SignedApproval,now:int)->bool:
        identity=self.verifier.verify(token,now)
        if (identity is None or identity.issuer!=self.issuer
            or identity.audience!=self.audience or identity.expires_at<now
            or "recovery-supervisor" not in identity.roles
            or identity.subject!=approval.principal):
            self.ledger.event(self.incident,"identity_denied",now)
            return False
        return SignedRecovery.authorize_signed(self,approval,now)
