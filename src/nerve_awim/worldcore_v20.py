"""WorldCore v2.0: adaptive-calibration-aware planning with sensor health.

Experimental simulator controller only. A sensor outage causes an explicit
UNAVAILABLE state rather than treating zero movement as inherently safe.
"""
from dataclasses import dataclass
from math import isfinite
from .risk_v17 import RiskAwareController
from .adaptive_calibration_v19 import AdaptiveCoverageAuditor

@dataclass(frozen=True)
class ControlResult:
    action: int | None
    status: str
    radius: float | None

class WorldCoreV2(RiskAwareController):
    def __init__(self, *, max_missing=5, calibration_target=.9, **kwargs):
        if not isinstance(max_missing,int) or max_missing<1:
            raise ValueError("invalid max_missing")
        super().__init__(**kwargs)
        self.auditor=AdaptiveCoverageAuditor(target=calibration_target,
            minimum=kwargs.get("min_samples",8))
        self.max_missing=max_missing
        self.last_packet_age=0
        self._scored=set()
    def ingest(self,timestamp,*,position=None,velocity=None):
        forecast=self.pending_predictions.get(timestamp)
        super().ingest(timestamp,position=position,velocity=velocity)
        self.last_packet_age=0
        if velocity is not None and forecast is not None and timestamp not in self._scored:
            self.auditor.record(forecast,velocity)
            self._scored.add(timestamp)
    def miss(self):
        self.last_packet_age+=1
        self.auditor.record(0,None)
    def choose(self):
        if self.last_packet_age>=self.max_missing:
            raise RuntimeError("sensor unavailable: external safety supervision required")
        s=self.core.filter.state
        radius=self.auditor.calibrator.radius()
        radius=0 if radius is None else radius*self.auditor.scale
        choices=[]
        for a in (-1,0,1):
            v=self.core.retention*s.velocity+self.core.gain*a
            p=s.position+v
            if abs(p)+radius>self.safe_position or abs(v)+radius>self.safe_velocity:
                continue
            score=(p-self.core.target)**2+.025*a*a+self.risk_aversion*radius*abs(a)
            choices.append((score,a))
        if not choices:
            self.infeasible+=1
            raise RuntimeError("no feasible action")
        return min(choices)[1]
    def decide(self):
        radius=self.auditor.calibrator.radius()
        radius=None if radius is None else radius*self.auditor.scale
        try:
            action=self.act()
            return ControlResult(action,"ok",radius)
        except RuntimeError:
            return ControlResult(None,"unavailable_or_infeasible",radius)
