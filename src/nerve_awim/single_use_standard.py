"""Opt-in single-consumption correction for the standard gain-learning hook.

Uses the original standard EMA and sample eligibility, once per accepted local
transition. Later sensor corrections still reach the lagged state filter but do
not train the same transition again. Missing/rejected pairs can qualify later.
EMA remains dependent on the order transitions first become usable; this is not
chronological re-fitting or an order-invariant estimator. Exhaustion retains the
gain until an inherited authorized recovery clears the local transition epoch.
Existing defaults, filter propagation and recovery authority are unchanged.
"""
from math import isfinite

from .identity_v26 import IdentityBoundRecovery
from .integrated_v13 import SensorOnlyController
from .runtime_v28 import NerveResearchRuntime


class SingleUseStandardGain:
    def __init__(self, *, initial=.27, learning_rate=.02, max_processed=4096):
        if (type(initial) not in (int, float) or not isfinite(initial) or not .01 <= initial <= 1.
                or type(learning_rate) not in (int, float) or not isfinite(learning_rate)
                or not 0 <= learning_rate <= 1.
                or type(max_processed) is not int or not 1 <= max_processed <= 10000):
            raise ValueError('invalid single-use standard gain configuration')
        self.gain = initial
        self.learning_rate = learning_rate
        self.max_processed = max_processed
        self.processed = set()

    @property
    def budget_exhausted(self):
        return len(self.processed) >= self.max_processed

    def update(self, timestamp, action, previous_velocity, velocity, retention=.82):
        if (self.learning_rate == 0 or type(timestamp) is not int or timestamp < 0
                or timestamp in self.processed or self.budget_exhausted
                or type(action) is not int or action not in (-1, 1)
                or any(type(value) not in (int, float) or not isfinite(value)
                       for value in (previous_velocity, velocity, retention))
                or not 0 <= retention < 1):
            return False
        sample = (velocity-retention*previous_velocity)/action
        if not isfinite(sample) or abs(sample) > 2:
            return False
        gain = max(.01, min(1., (1-self.learning_rate)*self.gain+self.learning_rate*sample))
        self.processed.add(timestamp)
        self.gain = gain
        return True


def _model(kwargs, max_processed):
    if kwargs.get('estimator', 'standard') != 'standard':
        raise ValueError('single-use correction requires standard estimator')
    model = SingleUseStandardGain(initial=kwargs.get('gain', .27),
        learning_rate=kwargs.get('learning_rate', .02), max_processed=max_processed)
    return model if model.learning_rate > 0 else None


class SingleUseStandardController(SensorOnlyController):
    def __init__(self, *, max_processed=4096, **kwargs):
        model = _model(kwargs, max_processed)
        super().__init__(**kwargs)
        # Reuse the existing optional update hook; no duplicated fitting loop.
        self.drift_model = model


class SingleUseStandardRecovery(IdentityBoundRecovery):
    def __init__(self, *, max_processed=4096, **kwargs):
        model = _model(kwargs, max_processed)
        super().__init__(**kwargs)
        self.core.drift_model = model


class SingleUseStandardRuntime(NerveResearchRuntime):
    def __init__(self, *, verifier, issuer, audience, secret, ledger_path, **kwargs):
        self.controller = SingleUseStandardRecovery(identity_verifier=verifier,
            expected_issuer=issuer, expected_audience=audience,
            secret=secret, ledger_path=ledger_path, **kwargs)
