"""Opt-in factual forecast sidecar for a fresh, local research runtime.

A command is never treated as evidence of execution. The trusted simulator host
must report the executed action separately, using observation-only authority.
This wrapper provides neither actuation nor additional recovery authority.
"""
from dataclasses import dataclass
from functools import wraps
from threading import RLock

from .phase_forecast import PhaseAwareForecaster
from .runtime_v28 import NerveResearchRuntime


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


@dataclass(frozen=True)
class _PendingAction:
    step: int
    action: int | None
    gain: float
    velocity: float
    retention: float


class ForecastResearchRuntime:
    def __init__(self, runtime, forecaster, *, max_report_delay=1,
                 max_pending_observations=128):
        if not isinstance(runtime, NerveResearchRuntime) or type(forecaster) is not PhaseAwareForecaster:
            raise TypeError('research runtime and fixed forecaster required')
        if (type(max_report_delay) is not int or not 0 <= max_report_delay <= 10000
                or type(max_pending_observations) is not int
                or not 1 <= max_pending_observations <= 10000):
            raise ValueError('invalid forecast report budget')
        controller, observer = runtime.controller, forecaster._observer
        model = controller.core.filter
        snapshot = forecaster.snapshot()
        if (model.actions or model.readings or controller.epoch_origin != 0
                or controller.phase != 'active' or controller.incident != 0
                or controller._freshness_time != -1
                or snapshot['next_step'] != 0 or snapshot['history_steps'] != 0
                or snapshot['known'] is not True or snapshot['epoch_origin'] != 0
                or observer._last_now != -1):
            raise ValueError('fresh_runtime_and_forecaster_required')
        if (observer._filter.a != controller.core.retention
                or observer._filter.b != controller.core.gain
                or snapshot['position'] != model.state.position
                or snapshot['velocity'] != model.state.velocity):
            raise ValueError('forecast_initial_state_mismatch')
        self.runtime, self.forecaster = runtime, forecaster
        self.max_report_delay = max_report_delay
        self.max_pending_observations = max_pending_observations
        self._lock = RLock()
        self._pending = None
        self._next_step = 0
        self._tick_failed = False
        self._observations = {}
        self._evicted_observations = 0

    @property
    def controller(self):
        return self.runtime.controller

    @_serialized
    def tick(self):
        if self._tick_failed:
            raise RuntimeError('runtime_tick_failed_requires_new_session')
        if self._pending is not None:
            raise RuntimeError('executed_action_report_required')
        core = self.controller.core
        gain, velocity, retention = core.gain, core.filter.state.velocity, core.retention
        try:
            result = self.runtime.tick()
        except Exception:
            # A failing controller may already have mutated. Never retry it as
            # if the original step had not happened.
            self._tick_failed = True
            raise
        self._pending = _PendingAction(self._next_step, result.action, gain, velocity, retention)
        return result

    def _require_report(self, token, now, step, *, allow_late=False):
        self.forecaster._observer._authorize(token, now)
        pending = self._pending
        if type(step) is not int or pending is None or step != pending.step:
            raise ValueError('no_matching_pending_action')
        if now < step or (not allow_late and now-step > self.max_report_delay):
            raise ValueError('executed_report_outside_deadline')
        return pending

    @_serialized
    def report_executed(self, token, *, now, step, action, source):
        with self.forecaster._observer._lock:
            pending = self._require_report(token, now, step)
            if type(action) is not int or action not in (-1, 0, 1):
                raise ValueError('invalid_executed_action')
            if type(source) is not str or source not in ('controller', 'external_supervisor'):
                raise ValueError('invalid_executed_action_source')
            if ((source == 'controller' and (pending.action is None or action != pending.action))
                    or (source == 'external_supervisor' and pending.action is not None)):
                raise ValueError('executed_action_does_not_match_issued_command')
            prediction = (pending.retention*pending.velocity + pending.gain*action
                          if source == 'controller' else None)
            forecast = self.forecaster.record_action(token, now=now, step=step,
                action=action, gain=pending.gain, source=source, controller_velocity=prediction)
            self._pending = None
            self._next_step += 1
            return forecast

    @_serialized
    def report_unknown(self, token, *, now, step):
        with self.forecaster._observer._lock:
            self._require_report(token, now, step, allow_late=True)
            forecast = self.forecaster.record_unknown(token, now=now, step=step)
            self._pending = None
            self._next_step += 1
            return forecast

    def _remember_observation(self, timestamp, position, velocity, accepted):
        # Partial observations remain valid for the original controller, but
        # cannot initialize the separate position/velocity observer.
        if accepted is False or position is None or velocity is None:
            return
        self._observations[timestamp] = (position, velocity)
        if len(self._observations) > self.max_pending_observations:
            self._observations.pop(next(iter(self._observations)))
            self._evicted_observations += 1

    @_serialized
    def observe(self, timestamp, *, position=None, velocity=None):
        result = self.runtime.observe(timestamp, position=position, velocity=velocity)
        self._remember_observation(timestamp, position, velocity, result)
        return result

    @_serialized
    def observe_recovery(self, timestamp, *, observed_now, position, velocity):
        result = self.runtime.observe_recovery(timestamp, observed_now=observed_now,
                                               position=position, velocity=velocity)
        self._remember_observation(timestamp, position, velocity, result)
        return result

    @_serialized
    def report_observation(self, token, *, now, step):
        with self.forecaster._observer._lock:
            self.forecaster._observer._authorize(token, now)
            if type(step) is not int or step not in self._observations:
                raise ValueError('accepted_observation_required')
            position, velocity = self._observations[step]
            result = self.forecaster.observe(token, now=now, step=step,
                                             position=position, velocity=velocity)
            del self._observations[step]
            return result

    @_serialized
    def sensor_missing(self):
        return self.runtime.sensor_missing()

    @_serialized
    def advance_time(self, now):
        return self.runtime.advance_time(now)

    @_serialized
    def authorise_recovery(self, token, approval, now):
        return self.runtime.authorise_recovery(token, approval, now)

    @_serialized
    def snapshot(self):
        return {'next_step': self._next_step,
                'pending_step': None if self._pending is None else self._pending.step,
                'tick_failed': self._tick_failed,
                'pending_observations': len(self._observations),
                'evicted_observations': self._evicted_observations,
                'observer': self.forecaster.snapshot()}
