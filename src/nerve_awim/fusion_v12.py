"""v1.2: timestamp-aware 2D position/velocity Kalman filter (research only).

The state is [position, velocity]. A delayed observation triggers full replay
from the original prior with historical actions, not a present-time correction.
"""
from dataclasses import dataclass
from math import isfinite, sqrt

@dataclass(frozen=True)
class FusedState:
    position: float
    velocity: float
    position_var: float
    velocity_var: float

class LaggedPositionVelocityFilter:
    def __init__(self, *, a=0.82, b=0.27, position_var=0.0025,
                 velocity_var=0.0025, process_var=0.0004, initial_var=0.1,
                 initial_position=0., initial_velocity=0.):
        if not all(isfinite(x) for x in (a,b,position_var,velocity_var,process_var,initial_var,initial_position,initial_velocity)):
            raise ValueError('nonfinite parameters')
        if min(position_var,velocity_var,process_var,initial_var)<=0:
            raise ValueError('variances must be positive')
        self.a,self.b,self.rp,self.rv,self.q,self.p0=a,b,position_var,velocity_var,process_var,initial_var
        self.initial_position=initial_position
        self.initial_velocity=initial_velocity
        self.actions=[]
        self.readings={}
        self.states=[FusedState(initial_position,initial_velocity,initial_var,initial_var)]
        self.innovations=[]
    def step(self, action):
        if action not in (-1,0,1): raise ValueError('invalid action')
        self.actions.append(action)
        self._replay()
    def observe(self,transition, *, position=None, velocity=None):
        if not isinstance(transition,int) or not 0<=transition<len(self.actions):
            raise ValueError('invalid timestamp')
        if position is None and velocity is None:raise ValueError('no observations')
        if not all(v is None or isfinite(v) for v in (position,velocity)):
            raise ValueError('nonfinite observation')
        old=self.readings.get(transition,(None,None))
        self.readings[transition]=(position if position is not None else old[0],
                                  velocity if velocity is not None else old[1])
        self._replay()
    def _replay(self):
        x,v=self.initial_position,self.initial_velocity
        pp=pv=self.p0; cross=0.
        states=[FusedState(x,v,pp,pv)]
        innovations=[]
        a=self.a
        for k,u in enumerate(self.actions):
            x+=a*v+self.b*u
            v=a*v+self.b*u
            pp,pv,cross=(pp+2*a*cross+a*a*pv+self.q,
                         a*a*pv+self.q,
                         a*cross+a*a*pv+self.q)
            if k in self.readings:
                yp,yv=self.readings[k]
                for is_position,y,r in ((True,yp,self.rp),(False,yv,self.rv)):
                    if y is None:continue
                    predicted=x if is_position else v
                    s=(pp if is_position else pv)+r
                    innovations.append((y-predicted)**2/s)
                    if is_position:
                        kx,kv=pp/s,cross/s
                        err=y-x
                        oldpp,oldcross=pp,cross
                        x+=kx*err;v+=kv*err
                        pp=max(pp-kx*oldpp,1e-12)
                        cross=cross-kx*oldcross
                        pv=max(pv-kv*oldcross,1e-12)
                    else:
                        kx,kv=cross/s,pv/s
                        err=y-v
                        oldpv,oldcross=pv,cross
                        x+=kx*err;v+=kv*err
                        pp=max(pp-kx*oldcross,1e-12)
                        cross=cross-kx*oldpv
                        pv=max(pv-kv*oldpv,1e-12)
            states.append(FusedState(x,v,pp,pv))
        self.states=states
        self.innovations=innovations
    @property
    def state(self):return self.states[-1]
    @property
    def velocity_std(self):return sqrt(self.state.velocity_var)
    @property
    def nis_mean(self):return sum(self.innovations)/len(self.innovations) if self.innovations else float('nan')
