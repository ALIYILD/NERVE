"""Experimental uncertainty-aware MPC wrapper. Research only.

Keeps a rolling interval calibrator using resolved prediction/observation pairs.
Applies a conservative action gate when uncertainty exceeds a configured bound.
No formal chance-constraint, hardware safety guarantee or clinical validation.
"""
from .integrated_v13 import SensorOnlyController
from .calibration_v15 import RollingErrorInterval

class CalibratedController:
    def __init__(self, *, radius_limit=0.3, min_samples=8, **kwargs):
        if radius_limit <= 0: raise ValueError("radius_limit must be positive")
        self.core=SensorOnlyController(**kwargs)
        self.calibration=RollingErrorInterval(minimum=min_samples)
        self.radius_limit=radius_limit
        self.pending_predictions={}
        self.blocked=0
    def ingest(self,timestamp,*,position=None,velocity=None):
        if velocity is not None and timestamp in self.pending_predictions:
            self.calibration.update(self.pending_predictions.pop(timestamp),velocity)
        self.core.ingest(timestamp,position=position,velocity=velocity)
    def choose(self):
        candidate=self.core.choose()
        radius=self.calibration.radius()
        if radius is not None and radius>self.radius_limit and candidate.action!=0:
            self.blocked+=1
            return 0
        return candidate.action
    def act(self):
        # Record forecast only for the action actually applied, then advance filter.
        candidate=self.core.choose()
        action=self.choose()
        state=self.core.filter.state
        prediction=self.core.retention*state.velocity+self.core.gain*action
        timestamp=len(self.core.filter.actions)
        self.pending_predictions[timestamp]=prediction
        self.core.filter.step(action)
        return action
