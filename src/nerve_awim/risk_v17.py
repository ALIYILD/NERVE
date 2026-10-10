"""v1.7 experimental risk-aware one-step action selection.

Ranks all discrete actions by expected target error and a rolling empirical
prediction-error radius. A separate hard position/velocity envelope rules out
infeasible candidates. This is NOT a calibrated chance constraint or a safety
certification, and stop/no-op is not presumed physically safe.
"""
from math import isfinite
from .calibrated_v16 import CalibratedController

class RiskAwareController(CalibratedController):
    def __init__(self, *, risk_aversion=0.5, safe_position=6.0, safe_velocity=2.0, **kwargs):
        super().__init__(**kwargs)
        if not all(isfinite(v) for v in (risk_aversion,safe_position,safe_velocity)):
            raise ValueError("nonfinite risk configuration")
        if risk_aversion<0 or safe_position<=0 or safe_velocity<=0:
            raise ValueError("invalid risk configuration")
        self.risk_aversion=risk_aversion
        self.safe_position=safe_position
        self.safe_velocity=safe_velocity
        self.infeasible=0
    def choose(self):
        s=self.core.filter.state
        radius=self.calibration.radius() or 0.0
        candidates=[]
        for action in (-1,0,1):
            velocity=self.core.retention*s.velocity+self.core.gain*action
            position=s.position+velocity
            if abs(position)+radius>self.safe_position or abs(velocity)+radius>self.safe_velocity:
                continue
            error=(position-self.core.target)**2
            # Cost of action and uncertainty exposure. The bias on |a| is a
            # transparent research heuristic, not a physical risk model.
            score=error+0.025*action*action+self.risk_aversion*radius*abs(action)
            candidates.append((score,action))
        if not candidates:
            self.infeasible+=1
            # Caller must handle infeasibility; don't pretend zero is safe.
            raise RuntimeError("No action satisfies the conservative envelope")
        return min(candidates)[1]
    def act(self):
        action=self.choose()
        state=self.core.filter.state
        prediction=self.core.retention*state.velocity+self.core.gain*action
        timestamp=len(self.core.filter.actions)
        self.pending_predictions[timestamp]=prediction
        self.core.filter.step(action)
        return action
