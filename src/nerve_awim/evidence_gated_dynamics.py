"""Opt-in evidence-gated gain adaptation for synthetic research.

A finite observation window must support a material shift before gain changes.
The standard-error multiplier is a heuristic under noisy/dependent observations,
not a calibrated confidence interval or a repeated-testing guarantee.
"""
from math import isfinite, sqrt

from .evidence_window_dynamics import EvidenceWindowGain, EvidenceWindowRecovery
from .runtime_v28 import NerveResearchRuntime


class EvidenceGatedGain(EvidenceWindowGain):
    def __init__(self, *, initial=.27, window=4, minimum=4,
                 error_multiplier=3., minimum_shift=.03):
        if (type(minimum) is not int or type(window) is not int or
                not 2 <= minimum <= window <= 64 or
                any(type(value) not in (int, float) or not isfinite(value)
                    for value in (error_multiplier, minimum_shift)) or
                not 0 < error_multiplier <= 10 or not 0 < minimum_shift <= .5):
            raise ValueError('invalid evidence gate configuration')
        super().__init__(initial=initial, window=window, prior_weight=4.)
        self.minimum = minimum
        self.error_multiplier = error_multiplier
        self.minimum_shift = minimum_shift
        self.gain_changes = 0
        self.last_threshold = None

    def update(self, timestamp, action, previous_velocity, velocity, retention=.82):
        retained = self.gain
        if not super().update(timestamp, action, previous_velocity, velocity, retention):
            return False
        # The parent validates, timestamps and deduplicates observation evidence.
        # Its regularized estimate is replaced; only this fixed gate changes gain.
        self.gain = retained
        values = [value for _, value in self.samples]
        count = len(values)
        mean = sum(values)/count
        self.variance = sum((value-mean)**2 for value in values)/count
        self.last_threshold = None
        if count >= self.minimum:
            standard_error = sqrt(self.variance/(count-1))
            self.last_threshold = self.minimum_shift + self.error_multiplier*standard_error
            if abs(mean-retained) > self.last_threshold:
                self.gain = max(.01, min(1., mean))
                self.gain_changes += int(self.gain != retained)
        return True  # Evidence was consumed even if gain was retained.

    def forget_window(self):
        super().forget_window()
        self.last_threshold = None


class EvidenceGatedRecovery(EvidenceWindowRecovery):
    def __init__(self, *, evidence_window=4, minimum=4, error_multiplier=3.,
                 minimum_shift=.03, **kwargs):
        if 'prior_weight' in kwargs:
            raise ValueError('prior_weight is not a gated estimator parameter')
        model = EvidenceGatedGain(initial=kwargs.get('gain', .27), window=evidence_window,
                                  minimum=minimum, error_multiplier=error_multiplier,
                                  minimum_shift=minimum_shift)
        # Existing guards, signed recovery, consistent filter and planning remain.
        super().__init__(evidence_window=evidence_window, **kwargs)
        self.core.drift_model = model


class EvidenceGatedRuntime(NerveResearchRuntime):
    def __init__(self, *, verifier, issuer, audience, secret, ledger_path, **kwargs):
        self.controller = EvidenceGatedRecovery(identity_verifier=verifier,
            expected_issuer=issuer, expected_audience=audience,
            secret=secret, ledger_path=ledger_path, **kwargs)
