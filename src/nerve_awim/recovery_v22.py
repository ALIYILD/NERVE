"""v2.2 auditable simulated recovery authorization.

An identity assertion is passed by a trusted caller; it is NOT authentication.
In production, identity, role, token integrity and replay protection must be
enforced independently of this model. No physical actuation allowed.
"""
from dataclasses import dataclass
from .recovery_v21 import SupervisedWorldCore

@dataclass(frozen=True)
class Approval:
    principal:str
    role:str
    incident:int
    nonce:str

class AuditedRecovery(SupervisedWorldCore):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.incident=0
        self.used_nonces=set()
        self.audit=[]
        self.last_packet=-1
    def miss(self):
        previous=self.phase
        super().miss()
        if previous=="active" and self.phase!="active":
            self.incident+=1
            self.last_recovery_timestamp=-1
            self.fresh_count=0
            self.audit.append(("outage",self.incident))
    def ingest(self,timestamp,*,position=None,velocity=None):
        if self.phase!="active" and timestamp<=self.last_packet:
            self.audit.append(("stale_rejected",self.incident))
            return False
        super().ingest(timestamp,position=position,velocity=velocity)
        self.last_packet=max(self.last_packet,timestamp)
        return True
    def authorize(self,approval:Approval):
        if not isinstance(approval,Approval):
            raise TypeError("approval required")
        valid=(self.phase=="awaiting_approval"
               and approval.incident==self.incident
               and approval.principal.strip()!=""
               and approval.role=="supervisor"
               and approval.nonce.strip()!=""
               and approval.nonce not in self.used_nonces)
        if not valid:
            self.audit.append(("approval_rejected",self.incident))
            return False
        self.used_nonces.add(approval.nonce)
        result=super().approve_recovery(True)
        self.audit.append(("approval_accepted",self.incident))
        return result
    def approve_recovery(self,approved):
        """Block legacy boolean approval; use authorize(Approval) instead."""
        return False
