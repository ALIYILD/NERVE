"""v2.1 supervised recovery state machine for simulated sensor outages.

External supervisor approval is an explicit API input, never inferred from an
LLM response. This does not operate or certify any real-world actuators.
"""
from dataclasses import dataclass
from .worldcore_v20 import WorldCoreV2,ControlResult

@dataclass(frozen=True)
class RecoveryStatus:
    phase:str
    fresh_observations:int
    approvals:int

class SupervisedWorldCore(WorldCoreV2):
    def __init__(self,*,recovery_samples=3,**kwargs):
        if not isinstance(recovery_samples,int) or recovery_samples<1:
            raise ValueError("invalid recovery sample threshold")
        super().__init__(**kwargs)
        self.phase="active"
        self.required=recovery_samples
        self.fresh_count=0
        self.approvals=0
        self.last_recovery_timestamp=-1
    def miss(self):
        super().miss()
        if self.last_packet_age>=self.max_missing:
            self.phase="supervision_required"
            self.fresh_count=0
    def ingest(self,timestamp,*,position=None,velocity=None):
        # Require a new, timestamped observation; reject duplicated or stale
        # packets as recovery evidence. The base filter still accepts delayed
        # packets for historical state estimation.
        super().ingest(timestamp,position=position,velocity=velocity)
        if self.phase!="active" and timestamp>self.last_recovery_timestamp:
            self.last_recovery_timestamp=timestamp
            self.fresh_count+=1
            if self.fresh_count>=self.required:
                self.phase="awaiting_approval"
    def approve_recovery(self,approved:bool):
        if self.phase!="awaiting_approval" or approved is not True:
            return False
        self.approvals+=1
        self.phase="active"
        self.last_packet_age=0
        return True
    def decide(self):
        if self.phase!="active":
            return ControlResult(None,self.phase,None)
        return super().decide()
    def recovery_status(self):
        return RecoveryStatus(self.phase,self.fresh_count,self.approvals)
