"""Opt-in nominal-prior fallback at an authorized research recovery epoch.

The prior is the configured initial gain, not an observation or plant truth.
Only successful inherited identity/signed recovery replaces fitting evidence.
This experimental policy has no demonstrated performance advantage.
"""
from threading import RLock

from .evidence_gated_dynamics import EvidenceGatedGain, EvidenceGatedRecovery
from .runtime_v28 import NerveResearchRuntime


class RecoveryEpochRecovery(EvidenceGatedRecovery):
    def __init__(self, **kwargs):
        if kwargs.get('forget_on_recovery', True) is not True:
            raise ValueError('recovery epoch requires forgetting old evidence')
        if kwargs.get('consistent_filter', True) is not True:
            raise ValueError('recovery epoch requires prospective filter')
        super().__init__(**kwargs)
        model = self.core.drift_model
        self._gate_configuration = dict(initial=model.initial, window=model.samples.maxlen,
            minimum=model.minimum, error_multiplier=model.error_multiplier,
            minimum_shift=model.minimum_shift)
        self.nominal_gain = model.initial
        self.recovery_epoch_resets = 0
        self.previous_fitted_gain = None
        self._recovery_lock = RLock()
        self._identity_recovery_in_progress = False

    def authorize_identity(self, token, approval, now):
        # The original verifier, signed nonce ledger, evidence and freshness
        # checks remain the sole authority to reach a successful reseed.
        with self._recovery_lock:
            if self._identity_recovery_in_progress:
                raise RuntimeError('recursive recovery authorization denied')
            self._identity_recovery_in_progress = True
            try:
                return super().authorize_identity(token, approval, now)
            finally:
                self._identity_recovery_in_progress = False

    def _reseed_observation(self, timestamp, *, observed_now, position, velocity):
        with self._recovery_lock:
            if not self._identity_recovery_in_progress:
                raise PermissionError('identity authorized recovery required for epoch fallback')
            # Prepare before any inherited mutation. Invalid recovery evidence
            # still fails in the superclass, leaving this candidate untouched.
            replacement = EvidenceGatedGain(**self._gate_configuration)
            previous = self.core.drift_model.gain
            super()._reseed_observation(timestamp, observed_now=observed_now,
                                        position=position, velocity=velocity)
            self.core.drift_model = replacement
            self.core.gain = replacement.gain
            self.core.filter.set_next_gain(replacement.gain)
            self.previous_fitted_gain = previous
            # A fixed-width diagnostic counter; no unbounded per-epoch history.
            self.recovery_epoch_resets = min(2**63-1, self.recovery_epoch_resets+1)


class RecoveryEpochRuntime(NerveResearchRuntime):
    def __init__(self, *, verifier, issuer, audience, secret, ledger_path, **kwargs):
        self.controller = RecoveryEpochRecovery(identity_verifier=verifier,
            expected_issuer=issuer, expected_audience=audience,
            secret=secret, ledger_path=ledger_path, **kwargs)
