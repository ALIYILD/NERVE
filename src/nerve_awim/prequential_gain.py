"""Experimental fixed-window prequential selection; no confidence guarantee.

Shadow fitting uses single-use standard EMA. Selection compares immutable
forecasts made on the same state/action before observing the scored velocity.
Only future controller commands use the selected gain; historical filter
coefficients and all inherited control/recovery gates remain unchanged.
"""
from collections import deque
from threading import RLock

from .single_use_standard import SingleUseStandardRecovery
from .runtime_v28 import NerveResearchRuntime


class PrequentialGainRecovery(SingleUseStandardRecovery):
    def __init__(self, *, selector_pending_limit=128, selector_max_age=128, **kwargs):
        if (type(selector_pending_limit) is not int or not 1 <= selector_pending_limit <= 128
                or type(selector_max_age) is not int or not 1 <= selector_max_age <= 4096
                or type(kwargs.get('learning_rate', .08)) not in (int,float)
                or kwargs.get('learning_rate', .08) != .08):
            raise ValueError('invalid prequential selector configuration')
        kwargs['learning_rate'] = .08
        super().__init__(**kwargs)
        self.nominal_gain = self.core.gain
        self.selector_pending_limit = selector_pending_limit
        self.selector_max_age = selector_max_age
        self._pending_forecasts = {}
        self._scores = deque(maxlen=4)
        self._selected_mode = 'nominal'
        self._counts = dict(resolved=0, evicted=0, expired=0, recovery_resets=0)
        self._selector_lock = RLock()
        self._identity_recovery_in_progress = False

    def _count(self, name):
        self._counts[name] = min(2**63-1, self._counts[name]+1)

    def _clock(self):
        return max(self._freshness_time, self.epoch_origin+len(self.core.filter.actions)-1)

    def _apply_selection(self):
        learned = (len(self._scores) == 4 and
            all(row['learned_error'] < row['nominal_error'] for row in self._scores))
        self._selected_mode = 'learned' if learned else 'nominal'
        self.core.gain = self.core.drift_model.gain if learned else self.nominal_gain

    def _expire(self):
        now = self._clock()
        for timestamp in list(self._pending_forecasts):
            if now-timestamp > self.selector_max_age:
                del self._pending_forecasts[timestamp]; self._count('expired')
        retained = [row for row in self._scores if now-row['timestamp'] <= self.selector_max_age]
        self._scores.clear(); self._scores.extend(retained)
        self._apply_selection()

    def ingest(self, timestamp, *, position=None, velocity=None):
        with self._selector_lock:
            try:
                accepted = super().ingest(timestamp, position=position, velocity=velocity)
            finally:
                # The learning hook writes core.gain; selection owns the gain
                # exposed to control, including when ingestion raises.
                self._apply_selection()
            if accepted is False: return accepted
            self._expire()
            if velocity is not None and timestamp in self._pending_forecasts:
                forecast = self._pending_forecasts.pop(timestamp)
                score = dict(forecast, observed_velocity=velocity,
                    nominal_error=abs(forecast['nominal_forecast']-velocity),
                    learned_error=abs(forecast['learned_forecast']-velocity))
                self._scores.append(score)
                self._count('resolved')
            self._apply_selection()
            return accepted

    def act(self):
        with self._selector_lock:
            self._expire()
            timestamp = self.epoch_origin+len(self.core.filter.actions)
            velocity, shadow = self.core.filter.state.velocity, self.core.drift_model.gain
            action = super().act()  # Existing freshness, phase and feasibility gates.
            if action != 0:
                record = dict(timestamp=timestamp, velocity=velocity, action=action,
                    nominal_gain=self.nominal_gain, shadow_gain=shadow,
                    nominal_forecast=self.core.retention*velocity+self.nominal_gain*action,
                    learned_forecast=self.core.retention*velocity+shadow*action)
                if len(self._pending_forecasts) >= self.selector_pending_limit:
                    del self._pending_forecasts[next(iter(self._pending_forecasts))]
                    self._count('evicted')
                self._pending_forecasts[timestamp] = record
            return action

    def advance_time(self, now):
        with self._selector_lock:
            result = super().advance_time(now)
            self._expire()
            return result

    def authorize_identity(self, token, approval, now):
        with self._selector_lock:
            if self._identity_recovery_in_progress:
                raise RuntimeError('recursive recovery authorization denied')
            self._identity_recovery_in_progress = True
            try: return super().authorize_identity(token, approval, now)
            finally: self._identity_recovery_in_progress = False

    def _reseed_observation(self, timestamp, *, observed_now, position, velocity):
        with self._selector_lock:
            if not self._identity_recovery_in_progress:
                raise PermissionError('identity authorized recovery required for selector reset')
            super()._reseed_observation(timestamp, observed_now=observed_now, position=position, velocity=velocity)
            self._pending_forecasts.clear(); self._scores.clear()
            self._count('recovery_resets')
            self._apply_selection()

    def selector_snapshot(self):
        with self._selector_lock:
            return dict(mode=self._selected_mode, nominal_gain=self.nominal_gain,
                shadow_gain=self.core.drift_model.gain, selected_gain=self.core.gain,
                pending=[dict(row) for row in self._pending_forecasts.values()],
                scores=[dict(row) for row in self._scores], counts=dict(self._counts))


class PrequentialGainRuntime(NerveResearchRuntime):
    def __init__(self, *, verifier, issuer, audience, secret, ledger_path, **kwargs):
        self.controller = PrequentialGainRecovery(identity_verifier=verifier,
            expected_issuer=issuer, expected_audience=audience,
            secret=secret, ledger_path=ledger_path, **kwargs)
