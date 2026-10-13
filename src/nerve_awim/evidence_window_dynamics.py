"""Experimental evidence-window gain learning; no default promotion.

Only usable timestamped sensor pairs update the gain. A fixed prior moderates
small noisy samples; it is not a calibrated Bayesian posterior. Authorized
recovery can forget the sample window without changing gain until new evidence.
"""
from collections import deque
from math import isfinite

from .consistent_dynamics import ConsistentDynamicsRecovery
from .runtime_v28 import NerveResearchRuntime


class EvidenceWindowGain:
    def __init__(self, *, initial=.27, window=16, prior_weight=4.):
        if (type(window) is not int or not 1 <= window <= 64 or
                any(type(v) not in (int, float) or not isfinite(v) for v in (initial, prior_weight)) or
                not .01 <= initial <= 1 or not 0 < prior_weight <= 64):
            raise ValueError('invalid evidence window configuration')
        self.initial = initial
        self.gain = initial
        self.prior_weight = prior_weight
        self.samples = deque(maxlen=window)
        self.processed = set()
        self.variance = .05
        self.drift_count = 0
        self.evidence_resets = 0

    def update(self, timestamp, action, previous_velocity, velocity, retention=.82):
        if type(timestamp) is not int or timestamp < 0:
            return False
        if timestamp in self.processed:
            return False
        if (type(action) is not int or action not in (-1, 1) or
                any(type(v) not in (int, float) or not isfinite(v)
                    for v in (previous_velocity, velocity, retention)) or not 0 <= retention < 1):
            return False
        sample = (velocity-retention*previous_velocity)/action
        if not isfinite(sample) or not -.3 <= sample <= 1.3:
            return False
        if len(self.samples) == self.samples.maxlen and timestamp < self.samples[0][0]:
            return False  # Too old to affect the registered evidence window.
        # Keep the most recent transition timestamps, not merely arrival order.
        entries = sorted((*self.samples, (timestamp, sample)))
        entries = entries[-self.samples.maxlen:]
        mean = (self.prior_weight*self.initial + sum(value for _, value in entries)) / (self.prior_weight+len(entries))
        gain = max(.01, min(1., mean))
        variance = sum((value-mean)**2 for _, value in entries) / len(entries)
        self.samples.clear()
        self.samples.extend(entries)
        self.processed.add(timestamp)
        self.drift_count += int(abs(sample-self.gain) > .12)
        self.gain = gain
        self.variance = variance
        return True

    def forget_window(self):
        """Retain gain and transition dedup; clear only prior fitting evidence."""
        self.samples.clear()
        self.evidence_resets += 1
        self.variance = .05


class EvidenceWindowRecovery(ConsistentDynamicsRecovery):
    def __init__(self, *, evidence_window=16, prior_weight=4., forget_on_recovery=True, **kwargs):
        if type(forget_on_recovery) is not bool:
            raise ValueError('invalid recovery evidence policy')
        # Validate before superclass initialization creates an approval ledger.
        initial = kwargs.get('gain', .27)
        model = EvidenceWindowGain(initial=initial, window=evidence_window, prior_weight=prior_weight)
        rate = kwargs.get('learning_rate', .08)
        if (kwargs.get('estimator', 'standard') != 'drift' or
                type(rate) not in (int, float) or rate != .08):
            raise ValueError('evidence candidate requires drift hook with fixed .08 activation rate')
        # The hook is enabled; this candidate uses window/prior weights, not EMA.
        kwargs['learning_rate'] = .08
        super().__init__(**kwargs)
        self.forget_on_recovery = forget_on_recovery
        self.core.drift_model = model

    def _reseed_observation(self, timestamp, *, observed_now, position, velocity):
        # All existing checks and host approval remain above this transition.
        super()._reseed_observation(timestamp, observed_now=observed_now, position=position, velocity=velocity)
        if self.forget_on_recovery:
            self.core.drift_model.forget_window()
        else:
            # Local transition indexes start again after the epoch boundary.
            # Preserve old evidence order using negative indexes in the new epoch.
            samples = self.core.drift_model.samples
            values = [value for _, value in samples]
            samples.clear()
            samples.extend((index-len(values), value) for index, value in enumerate(values))


class EvidenceWindowRuntime(NerveResearchRuntime):
    def __init__(self, *, verifier, issuer, audience, secret, ledger_path, **kwargs):
        self.controller = EvidenceWindowRecovery(identity_verifier=verifier,
            expected_issuer=issuer, expected_audience=audience,
            secret=secret, ledger_path=ledger_path, **kwargs)
