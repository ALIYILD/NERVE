"""NERVE research recovery runtime: controller plus externally injected verifier.

No model-generated approvals; only an externally authenticated identity
assertion and separately signed approval can resume the simulated controller.
"""
from dataclasses import dataclass
from .identity_v26 import IdentityBoundRecovery

@dataclass(frozen=True)
class RuntimeResult:
    action:int|None
    phase:str
    incident:int

class NerveResearchRuntime:
    def __init__(self, *, verifier, issuer, audience, secret, ledger_path, **kwargs):
        self.controller=IdentityBoundRecovery(identity_verifier=verifier,
            expected_issuer=issuer,expected_audience=audience,
            secret=secret,ledger_path=ledger_path,**kwargs)
    def tick(self):
        result=self.controller.decide()
        return RuntimeResult(result.action,self.controller.phase,
                             self.controller.incident)
    def sensor_missing(self):
        self.controller.miss()
    def observe(self,timestamp,*,position=None,velocity=None):
        return self.controller.ingest(timestamp,position=position,velocity=velocity)
    def authorise_recovery(self,token,approval,now):
        return self.controller.authorize_identity(token,approval,now)
