"""WorldCore v2.0: adaptive-calibration-aware planning with sensor health.

Experimental simulator controller only. A sensor outage causes an explicit
UNAVAILABLE state rather than treating zero movement as inherently safe.
"""
from dataclasses import dataclass
from math import isfinite
from .risk_v17 import RiskAwareController
from .adaptive_calibration_v19 import AdaptiveCoverageAuditor
from .calibration_v15 import RollingErrorInterval
from .fusion_v12 import LaggedPositionVelocityFilter

@dataclass(frozen=True)
class ControlResult:
    action: int | None
    status: str
    radius: float | None

class WorldCoreV2(RiskAwareController):
    def __init__(self, *, max_missing=5, calibration_target=.9, **kwargs):
        if type(max_missing) is not int or max_missing<1:
            raise ValueError("invalid max_missing")
        super().__init__(**kwargs)
        self.auditor=AdaptiveCoverageAuditor(target=calibration_target,
            minimum=kwargs.get("min_samples",8))
        self.max_missing=max_missing
        self.last_packet_age=0
        self.latest_observation_timestamp=-1
        self._freshness_time=-1
        self.epoch_origin=0
        self._scored=set()
    def ingest(self,timestamp,*,position=None,velocity=None):
        if type(timestamp) is not int or timestamp<self.epoch_origin:
            raise ValueError("invalid timestamp")
        local=timestamp-self.epoch_origin
        forecast=self.pending_predictions.get(local)
        super().ingest(local,position=position,velocity=velocity)
        # Historical corrections still update the lagged estimator, but only
        # a newer observation can refresh liveness. Account for its step lag.
        self._freshness_time=max(self._freshness_time,self.epoch_origin+len(self.core.filter.actions)-1)
        if timestamp>self.latest_observation_timestamp:
            self.latest_observation_timestamp=timestamp
            self.last_packet_age=max(0,self._freshness_time-timestamp)
        if velocity is not None and forecast is not None and timestamp not in self._scored:
            self.auditor.record(forecast,velocity)
            self._scored.add(timestamp)
    def miss(self):
        self._freshness_time=max(self._freshness_time,self.epoch_origin+len(self.core.filter.actions)-2)+1
        self.last_packet_age+=1
        self.auditor.record(0,None)
    def _sync_freshness(self):
        self._freshness_time=max(self._freshness_time,self.epoch_origin+len(self.core.filter.actions)-1)
        if self.latest_observation_timestamp>=0:
            self.last_packet_age=max(self.last_packet_age,
                self._freshness_time-self.latest_observation_timestamp)
        elif self._freshness_time>=0:
            self.last_packet_age=max(self.last_packet_age,self._freshness_time+1)
    def advance_time(self,now):
        if type(now) is not int or now<max(self._freshness_time,
                self.epoch_origin+len(self.core.filter.actions)-1):
            raise ValueError("invalid monotonic observation time")
        self._freshness_time=now
        self._sync_freshness()

    def _reseed_observation(self,timestamp,*,observed_now,position,velocity):
        # Trusted recovery transition only; public authorization lives above.
        if (type(timestamp) is not int or type(observed_now) is not int
                or timestamp<=self.latest_observation_timestamp
                or timestamp!=observed_now
                or observed_now<max(timestamp,self._freshness_time,
                    self.epoch_origin+len(self.core.filter.actions)-1)
                or observed_now-timestamp>=self.max_missing
                or any(type(v) not in (int,float) or not isfinite(v)
                       for v in (position,velocity))):
            raise ValueError("invalid recovery observation")
        old=self.core.filter
        replacement=LaggedPositionVelocityFilter(a=old.a,b=old.b,
            position_var=old.rp,velocity_var=old.rv,process_var=old.q,
            initial_var=old.p0,initial_position=position,initial_velocity=velocity)
        calibration=RollingErrorInterval(coverage=self.calibration.coverage,
            window=self.calibration.errors.maxlen,minimum=self.calibration.minimum)
        auditor=AdaptiveCoverageAuditor(target=self.auditor.calibrator.coverage,
            window=self.auditor.calibrator.errors.maxlen,
            minimum=self.auditor.calibrator.minimum,adapt_rate=self.auditor.adapt_rate,
            min_scale=self.auditor.min_scale,max_scale=self.auditor.max_scale)
        self.core.filter=replacement
        self.core._last_fit_index=-1
        if self.core.drift_model is not None:
            self.core.drift_model.processed.clear()
        self.calibration=calibration
        self.auditor=auditor
        self.pending_predictions.clear()
        self._scored.clear()
        self.epoch_origin=timestamp+1
        self.latest_observation_timestamp=timestamp
        self._freshness_time=observed_now
        self.last_packet_age=observed_now-timestamp

    def choose(self):
        self._sync_freshness()
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
