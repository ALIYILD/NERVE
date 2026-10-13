"""Opt-in synthetic controller candidates; no automatic baseline promotion.

The multi-step radius is a fixed empirical heuristic, not a calibrated
future-state bound. The drift estimator consumes each sensor pair once.
Store the gain actually used at each filter transition so later learning cannot
rewrite historical propagation. Planning depth is independently selectable.
"""
from itertools import product
from math import isfinite

from .fusion_v12 import FusedState, LaggedPositionVelocityFilter
from .identity_v26 import IdentityBoundRecovery
from .runtime_v28 import NerveResearchRuntime


class ProspectiveGainFilter(LaggedPositionVelocityFilter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._transition_gains = ()

    @property
    def transition_gains(self):
        return self._transition_gains

    def set_next_gain(self, gain):
        if type(gain) not in (int, float) or not isfinite(gain) or not .01 <= gain <= 1.:
            raise ValueError('invalid prospective gain')
        self.b = gain

    def step(self, action):
        if type(action) is not int or action not in (-1, 0, 1):
            raise ValueError('invalid action')
        if len(self.transition_gains) != len(self.actions):
            raise ValueError('gain history mismatch')
        self.set_next_gain(self.b)
        self._transition_gains += (self.b,)
        super().step(action)

    def _replay(self):
        if len(self.transition_gains) != len(self.actions):
            raise ValueError('gain history mismatch')
        x, v = self.initial_position, self.initial_velocity
        pp = pv = self.p0
        cross = 0.
        states = [FusedState(x, v, pp, pv)]
        innovations = []
        a = self.a
        for k, (u, gain) in enumerate(zip(self.actions, self.transition_gains)):
            x += a * v + gain * u
            v = a * v + gain * u
            pp, pv, cross = (pp + 2*a*cross + a*a*pv + self.q,
                             a*a*pv + self.q, a*cross + a*a*pv + self.q)
            if k in self.readings:
                yp, yv = self.readings[k]
                for is_position, y, r in ((True, yp, self.rp), (False, yv, self.rv)):
                    if y is None:
                        continue
                    predicted = x if is_position else v
                    s = (pp if is_position else pv) + r
                    innovations.append((y - predicted)**2 / s)
                    if is_position:
                        kx, kv = pp/s, cross/s
                        err = y-x
                        oldpp, oldcross = pp, cross
                        x += kx*err
                        v += kv*err
                        pp = max(pp-kx*oldpp, 1e-12)
                        cross -= kx*oldcross
                        pv = max(pv-kv*oldcross, 1e-12)
                    else:
                        kx, kv = cross/s, pv/s
                        err = y-v
                        oldpv, oldcross = pv, cross
                        x += kx*err
                        v += kv*err
                        pp = max(pp-kx*oldcross, 1e-12)
                        cross -= kx*oldpv
                        pv = max(pv-kv*oldpv, 1e-12)
            states.append(FusedState(x, v, pp, pv))
        self.states, self.innovations = states, innovations


class ConsistentDynamicsRecovery(IdentityBoundRecovery):
    def __init__(self, *, consistent_filter=True, planning_horizon=1, **kwargs):
        if type(consistent_filter) is not bool:
            raise ValueError('invalid consistent_filter')
        if type(planning_horizon) is not int or not 1 <= planning_horizon <= 5:
            raise ValueError('invalid planning_horizon')
        super().__init__(**kwargs)
        self.consistent_filter = consistent_filter
        self.planning_horizon = planning_horizon
        if consistent_filter:
            self._install_filter()

    def _install_filter(self):
        old = self.core.filter
        if old.actions or old.readings:
            raise ValueError('cannot replace nonempty filter history')
        replacement = ProspectiveGainFilter(a=old.a, b=self.core.gain,
            position_var=old.rp, velocity_var=old.rv, process_var=old.q,
            initial_var=old.p0, initial_position=old.initial_position,
            initial_velocity=old.initial_velocity)
        replacement.set_next_gain(self.core.gain)
        self.core.filter = replacement

    def ingest(self, timestamp, *, position=None, velocity=None):
        result = super().ingest(timestamp, position=position, velocity=velocity)
        if self.consistent_filter:
            self.core.filter.set_next_gain(self.core.gain)
        return result

    def _reseed_observation(self, timestamp, *, observed_now, position, velocity):
        super()._reseed_observation(timestamp, observed_now=observed_now,
                                    position=position, velocity=velocity)
        if self.consistent_filter:
            self._install_filter()

    def choose(self):
        # Invoke the entire existing phase/freshness/feasibility guard chain.
        baseline = super().choose()
        if self.planning_horizon == 1:
            return baseline
        state = self.core.filter.state
        radius = self.auditor.calibrator.radius()
        radius = 0. if radius is None else radius*self.auditor.scale
        choices = []
        for sequence in product((-1, 0, 1), repeat=self.planning_horizon):
            position, velocity, cost = state.position, state.velocity, 0.
            for action in sequence:
                velocity = self.core.retention*velocity + self.core.gain*action
                position += velocity
                if abs(position)+radius > self.safe_position or abs(velocity)+radius > self.safe_velocity:
                    break
                cost += (position-self.core.target)**2 + .025*action*action + self.risk_aversion*radius*abs(action)
            else:
                choices.append((cost, sequence))
        if not choices:
            self.infeasible += 1
            raise RuntimeError('no feasible planning sequence')
        return min(choices)[1][0]


class ConsistentDynamicsRuntime(NerveResearchRuntime):
    def __init__(self, *, verifier, issuer, audience, secret, ledger_path, **kwargs):
        self.controller = ConsistentDynamicsRecovery(identity_verifier=verifier,
            expected_issuer=issuer, expected_audience=audience,
            secret=secret, ledger_path=ledger_path, **kwargs)
