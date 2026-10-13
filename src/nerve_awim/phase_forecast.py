"""Opt-in fixed forecast routing from authenticated factual action source.

Uses the controller's own prediction while controlling, the separate observer
while external supervision acts, and never selects using subsequent outcomes.
No recovery or actuation capability is provided.
"""
from dataclasses import dataclass
from .actual_action_observer import ActualActionObserver


@dataclass(frozen=True)
class RoutedForecast:
    step: int
    velocity: float | None
    source: str
    status: str


class PhaseAwareForecaster:
    def __init__(self, **observer_kwargs):
        self._observer = ActualActionObserver(**observer_kwargs)

    def observe(self, token, *, now, step, position, velocity):
        return self._observer.observe(token,now=now,step=step,position=position,velocity=velocity)

    def record_action(self, token, *, now, step, action, gain, source, controller_velocity=None):
        with self._observer._lock:
            self._observer._authorize(token,now)
            if type(source) is not str or source not in ('controller','external_supervisor'):
                raise ValueError('invalid_action_source')
            if source == 'controller':
                self._observer._number(controller_velocity)
            elif controller_velocity is not None:
                raise ValueError('external_action_has_no_controller_forecast')
            # Continue observer propagation on every actual action, even when its
            # forecast is not selected. Gaps retain the observer's unknown state.
            observed = self._observer.record_action(token,now=now,step=step,action=action,gain=gain)
            if source == 'controller':
                return RoutedForecast(step,controller_velocity,source,'controller_forecast')
            return RoutedForecast(step,observed.velocity,source,observed.status)

    def record_unknown(self, token, *, now, step):
        observed = self._observer.record_unknown(token,now=now,step=step)
        return RoutedForecast(step,None,'unknown',observed.status)

    def snapshot(self):
        return self._observer.snapshot()
