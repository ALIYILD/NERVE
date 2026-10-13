"""Authenticated factual action observation, separate from control authority.

Synthetic research only. Reports describe actions already executed; they never
instruct a device or authorize recovery. Unknown actions invalidate the estimate.
The injected verifier and scope-bound audience must be supplied by a trusted host.
"""
from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from functools import wraps
from threading import RLock

from .consistent_dynamics import ProspectiveGainFilter
from .identity_v26 import VerifiedIdentity


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


@dataclass(frozen=True)
class ActionForecast:
    step: int
    position: float | None
    velocity: float | None
    status: str


class ActualActionObserver:
    def __init__(self, *, verifier, issuer, audience, subjects, retention=.82,
                 initial_gain=.27, max_history=4096):
        if (type(issuer) is not str or not issuer or type(audience) is not str or not audience
                or type(subjects) is not frozenset or not subjects
                or any(type(s) is not str or not s for s in subjects)
                or type(max_history) is not int or not 1 <= max_history <= 10000):
            raise ValueError('invalid observer authority or history budget')
        self._number(retention, 0., .999999)
        self._number(initial_gain, .01, 1.)
        self._lock = RLock()
        self.verifier, self.issuer, self.audience = verifier, issuer, audience
        self.subjects, self.max_history = subjects, max_history
        self._filter = ProspectiveGainFilter(a=retention, b=initial_gain)
        self._next_step = 0
        self._origin = 0
        self._known = True
        self._last_now = -1

    @staticmethod
    def _number(value, lower=-1e6, upper=1e6):
        if type(value) not in (int, float) or not isfinite(value) or not lower <= value <= upper:
            raise ValueError('invalid observer numeric value')

    def _authorize(self, token, now):
        if type(now) is not int or now < 0 or now < self._last_now:
            raise ValueError('invalid monotonic host time')
        identity = self.verifier.verify(token, now)
        if (type(identity) is not VerifiedIdentity or identity.issuer != self.issuer
                or identity.audience != self.audience or identity.subject not in self.subjects
                or type(identity.roles) is not frozenset or 'actual-action-observer' not in identity.roles
                or type(identity.expires_at) is not int or identity.expires_at < now):
            raise PermissionError('actual_action_observation_denied')

    @property
    @_serialized
    def next_step(self):
        return self._next_step

    @_serialized
    def snapshot(self):
        state = self._filter.state if self._known else None
        return {'next_step':self._next_step, 'known':self._known,
                'position':None if state is None else state.position,
                'velocity':None if state is None else state.velocity,
                'history_steps':len(self._filter.actions), 'epoch_origin':self._origin}

    def _validate_filter(self, candidate):
        for state in candidate.states:
            for value in (state.position,state.velocity,state.position_var,state.velocity_var):
                self._number(value)
        if any(not isfinite(value) for value in candidate.innovations):
            raise ValueError('nonfinite observer innovation')

    @_serialized
    def record_action(self, token, *, now, step, action, gain):
        self._authorize(token, now)
        if type(step) is not int or step < self._next_step:
            raise ValueError('replayed_or_invalid_action_step')
        if type(action) is not int or action not in (-1,0,1):
            raise ValueError('invalid actual action')
        self._number(gain,.01,1.)
        if step != self._next_step or not self._known:
            # A missing report is unknown, never an inferred zero action.
            self._known = False
            self._next_step, self._last_now = step+1, now
            return ActionForecast(step,None,None,'unknown_action_history')
        if len(self._filter.actions) >= self.max_history:
            self._known = False
            self._next_step, self._last_now = step+1, now
            return ActionForecast(step,None,None,'history_budget_exhausted')
        candidate = deepcopy(self._filter)
        candidate.set_next_gain(gain)
        candidate.step(action)
        self._validate_filter(candidate)
        state = candidate.state
        self._filter = candidate
        self._next_step, self._last_now = step+1, now
        return ActionForecast(step,state.position,state.velocity,'observed_action_forecast')

    @_serialized
    def record_unknown(self, token, *, now, step):
        self._authorize(token, now)
        if type(step) is not int or step < self._next_step:
            raise ValueError('replayed_or_invalid_action_step')
        self._known = False
        self._next_step, self._last_now = step+1, now
        return ActionForecast(step,None,None,'unknown_action_history')

    @_serialized
    def observe(self, token, *, now, step, position, velocity):
        self._authorize(token, now)
        if type(step) is not int or not 0 <= step < self._next_step:
            raise ValueError('invalid sensor step')
        self._number(position); self._number(velocity)
        if not self._known:
            if step != self._next_step-1:
                raise ValueError('current_checkpoint_required')
            old = self._filter
            candidate = ProspectiveGainFilter(a=old.a,b=old.b,position_var=old.rp,
                velocity_var=old.rv,process_var=old.q,initial_var=old.p0,
                initial_position=position,initial_velocity=velocity)
            origin = self._next_step
        else:
            if step < self._origin:
                raise ValueError('sensor_before_observer_epoch')
            candidate = deepcopy(self._filter)
            candidate.observe(step-self._origin,position=position,velocity=velocity)
            origin = self._origin
        self._validate_filter(candidate)
        self._filter, self._origin = candidate, origin
        self._known, self._last_now = True, now
        return self.snapshot()
