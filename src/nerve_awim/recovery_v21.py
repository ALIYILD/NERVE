"""Supervised recovery from fresh host-timestamped simulated observations.

Historical action-index packets remain estimator corrections, never recovery
permission. No physical actuation or model-generated approval is provided.
"""
from dataclasses import dataclass
from math import isfinite
from .worldcore_v20 import WorldCoreV2,ControlResult

@dataclass(frozen=True)
class RecoveryStatus:
    phase:str
    fresh_observations:int
    approvals:int

class SupervisedWorldCore(WorldCoreV2):
    def __init__(self,*,recovery_samples=3,**kwargs):
        if type(recovery_samples) is not int or recovery_samples<1:
            raise ValueError("invalid recovery sample threshold")
        super().__init__(**kwargs)
        self.phase="active"
        self.required=recovery_samples
        self.fresh_count=0
        self.approvals=0
        self.last_recovery_timestamp=-1
        self.recovery_after=-1
        self._recovery_observation=None
    def _on_incident(self):
        pass
    def _on_recovery_reset(self):
        pass
    def _on_recovery_observation(self,observation):
        pass
    def _reset_recovery(self):
        self.phase="supervision_required"
        self.fresh_count=0
        self.recovery_after=self._freshness_time
        self._recovery_observation=None
        self._on_recovery_reset()
    def _enter_supervision(self):
        if self.phase=="active":
            self._reset_recovery()
            self._on_incident()
    def miss(self):
        super().miss()
        if self.phase!="active":
            self._reset_recovery()
        elif self.last_packet_age>=self.max_missing:
            self._enter_supervision()
    def advance_time(self,now):
        super().advance_time(now)
        if self.last_packet_age>=self.max_missing:
            self._enter_supervision()
    def observe_recovery(self,timestamp,*,observed_now,position,velocity):
        """Accept a complete sensor sample on the trusted episode clock.

        This clock keeps advancing while action generation is suspended. No
        estimator action or prediction is fabricated to admit the observation.
        """
        if (type(timestamp) is not int or type(observed_now) is not int
                or timestamp<0 or observed_now<timestamp
                or observed_now<max(self._freshness_time,
                    self.epoch_origin+len(self.core.filter.actions)-1)):
            raise ValueError("invalid recovery observation time")
        if any(type(v) not in (int,float) or not isfinite(v)
               for v in (position,velocity)):
            raise ValueError("complete finite recovery observation required")
        was_active=self.phase=="active"
        self.advance_time(observed_now)
        if (was_active or timestamp<=self.recovery_after
                or timestamp<=self.last_recovery_timestamp
                or timestamp<=self.latest_observation_timestamp
                or observed_now-timestamp>=self.max_missing):
            return False
        if (self._recovery_observation is not None
                and observed_now-self.last_recovery_timestamp>self.max_missing):
            self.fresh_count=0
            self.phase="supervision_required"
            self._recovery_observation=None
            self._on_recovery_reset()
        observation=dict(timestamp=timestamp,position=position,velocity=velocity)
        self._recovery_observation=observation
        self.last_recovery_timestamp=timestamp
        self.fresh_count+=1
        if self.fresh_count>=self.required:
            self.phase="awaiting_approval"
        self._on_recovery_observation(observation)
        return True
    def recovery_ready(self):
        self._sync_freshness()
        observation=self._recovery_observation
        return (self.phase=="awaiting_approval" and self.fresh_count>=self.required
                and observation is not None
                and abs(observation["position"])<=self.safe_position
                and abs(observation["velocity"])<=self.safe_velocity
                and observation["timestamp"]==self._freshness_time)
    def approve_recovery(self,approved:bool):
        if approved is not True or not self.recovery_ready():
            return False
        observation=self._recovery_observation
        self._reseed_observation(observation["timestamp"],observed_now=self._freshness_time,
            position=observation["position"],velocity=observation["velocity"])
        self.approvals+=1
        self.phase="active"
        return True
    def choose(self):
        if self.phase!="active":
            raise RuntimeError("sensor recovery requires external approval")
        try:
            return super().choose()
        except RuntimeError:
            if self.last_packet_age>=self.max_missing:
                self._enter_supervision()
            raise
    def decide(self):
        if self.phase!="active":
            return ControlResult(None,self.phase,None)
        return super().decide()
    def recovery_status(self):
        return RecoveryStatus(self.phase,self.fresh_count,self.approvals)
