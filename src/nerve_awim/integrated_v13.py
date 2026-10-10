"""v1.3 sensor-only feedback controller: experimental integration.

No hidden simulator state enters decisions or model fitting. Delayed sensor
measurements are replayed by the v1.2 filter. A conservative online scalar
action-gain estimate is updated from timestamped filtered velocity changes.
This is a simple experiment, not a safety-certified control system.
"""
from dataclasses import dataclass
from itertools import product
from math import isfinite
from .fusion_v12 import LaggedPositionVelocityFilter
from .drift_v14 import DriftAwareGain

ACTIONS=(-1,0,1)

@dataclass(frozen=True)
class Decision:
    action:int
    predicted_position:float
    predicted_velocity:float
    position_std:float
    model_gain:float
    observation_count:int

class SensorOnlyController:
    def __init__(self, *, target=1.0, retention=0.82, gain=0.27,
                 learning_rate=0.02, bound=5.0, horizon=3,
                 risk_weight=1.0, estimator='standard'):
        values=(target,retention,gain,learning_rate,bound,risk_weight)
        if not all(isfinite(v) for v in values):raise ValueError("nonfinite configuration")
        if not 0<=retention<1 or not 0<=learning_rate<=1 or not 0<bound or not 1<=horizon<=5 or risk_weight<0:
            raise ValueError("invalid controller configuration")
        self.target,self.retention,self.gain=target,retention,gain
        self.lr,self.bound,self.horizon,self.risk=learning_rate,bound,horizon,risk_weight
        self.filter=LaggedPositionVelocityFilter(a=retention,b=gain)
        if estimator not in ('standard','drift'): raise ValueError('invalid estimator')
        self.estimator=estimator
        self.drift_model=DriftAwareGain(initial=gain,base_rate=learning_rate) if estimator=='drift' and learning_rate>0 else None
        self.observation_count=0
        self._last_fit_index=-1
    def ingest(self, timestamp, *, position=None, velocity=None):
        """Only sensor readings (never simulator state) enter the controller."""
        if position is None and velocity is None:raise ValueError("empty sensor packet")
        self.filter.observe(timestamp,position=position,velocity=velocity)
        self.observation_count+=1
        # Fit only transitions for which consecutive timestamped velocity
        # observations exist, avoiding unsound timestamp association.
        for k in range(self._last_fit_index+1,len(self.filter.actions)):
            if k==0:continue
            prev=self.filter.readings.get(k-1,(None,None))[1]
            curr=self.filter.readings.get(k,(None,None))[1]
            a=self.filter.actions[k]
            if prev is None or curr is None or a==0:continue
            sample=(curr-self.retention*prev)/a
            if self.drift_model is not None:
                if self.drift_model.update(k,a,prev,curr,self.retention):
                    self.gain=self.drift_model.gain
            elif self.lr>0 and isfinite(sample) and abs(sample)<=2:
                self.gain=max(0.01,min(1.0,(1-self.lr)*self.gain+self.lr*sample))
        # Revisit delayed updates next time: do not advance past missing pairs.
        self._last_fit_index=-1
    def choose(self):
        s=self.filter.state
        best=None
        for sequence in product(ACTIONS,repeat=self.horizon):
            p,v=s.position,s.velocity
            cost=0.0
            valid=True
            for a in sequence:
                v=self.retention*v+self.gain*a
                p+=v
                if abs(p)>self.bound or abs(v)>2:
                    valid=False;break
                cost+=(p-self.target)**2+0.025*a*a
            if not valid:continue
            # Conservative uncertainty penalty; not a calibrated chance constraint.
            cost+=self.risk*(s.position_var+s.velocity_var)*sum(abs(a) for a in sequence)
            if best is None or cost<best[0]:best=(cost,sequence)
        action=best[1][0] if best else 0
        predicted_v=self.retention*s.velocity+self.gain*action
        return Decision(action,s.position+predicted_v,predicted_v,
                        s.position_var**0.5,self.gain,self.observation_count)
    def act(self):
        decision=self.choose()
        self.filter.step(decision.action)
        return decision
