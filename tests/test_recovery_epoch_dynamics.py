"""Development fixtures only; no registered episode streams or hidden truth."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.recovery_v25 import sign_approval
from nerve_awim.recovery_epoch_dynamics import RecoveryEpochRuntime

SECRET = b'synthetic-recovery-epoch-test-secret'


class Verifier:
    def verify(self, token, now):
        if token in ('operator', 'reporter'):
            roles = {'recovery-supervisor'} if token == 'operator' else {'actual-action-observer'}
            return VerifiedIdentity(token, 'test', 'nerve', frozenset(roles), now+10)


class RecoveryEpochTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.counter = 0

    def runtime(self, **kwargs):
        self.counter += 1
        return RecoveryEpochRuntime(verifier=Verifier(), issuer='test', audience='nerve',
            secret=SECRET, ledger_path=str(self.directory/f'{self.counter}.sqlite'),
            estimator='drift', max_missing=1, recovery_samples=2, **kwargs)

    def fit(self, runtime, value=.6):
        model = runtime.controller.core.drift_model
        for timestamp in range(model.minimum):
            model.update(timestamp, 1, 0., value)
        runtime.controller.core.gain = model.gain
        runtime.controller.core.filter.set_next_gain(model.gain)
        return model

    def ready(self, runtime):
        runtime.sensor_missing()
        self.assertTrue(runtime.observe_recovery(4, observed_now=4, position=.1, velocity=.1))
        self.assertTrue(runtime.observe_recovery(5, observed_now=5, position=.2, velocity=.1))
        return sign_approval(SECRET, 'operator', 'supervisor', runtime.controller.incident,
                             'approval', 20)

    def test_only_successful_authorized_recovery_resets_gain_to_configured_prior(self):
        runtime = self.runtime(gain=.41)
        model = self.fit(runtime, .8)
        before = deepcopy(vars(model))
        approval = self.ready(runtime)
        self.assertEqual(vars(model), before)
        self.assertEqual(runtime.controller.core.gain, .8)
        self.assertEqual(runtime.controller.recovery_epoch_resets, 0)
        for token in ('invalid', 'reporter'):
            self.assertFalse(runtime.authorise_recovery(token, approval, 5))
            self.assertEqual(vars(model), before)
            self.assertEqual(runtime.controller.core.gain, .8)
        self.assertTrue(runtime.authorise_recovery('operator', approval, 5))
        controller = runtime.controller
        self.assertEqual(controller.nominal_gain, .41)
        self.assertEqual(controller.core.gain, .41)
        self.assertEqual(controller.core.filter.b, .41)
        self.assertEqual(controller.previous_fitted_gain, .8)
        self.assertEqual(controller.recovery_epoch_resets, 1)
        self.assertIsNot(controller.core.drift_model, model)
        self.assertEqual(controller.core.drift_model.samples.maxlen, 4)
        self.assertEqual(len(controller.core.drift_model.samples), 0)
        self.assertEqual(controller.core.drift_model.processed, set())
        self.assertEqual(controller.core.drift_model.gain_changes, 0)
        self.assertIsNone(controller.core.drift_model.last_threshold)

    def test_recovery_gate_must_relearn_from_fresh_minimum_evidence(self):
        runtime = self.runtime(); self.fit(runtime)
        self.assertTrue(runtime.authorise_recovery('operator', self.ready(runtime), 5))
        model = runtime.controller.core.drift_model
        for timestamp in range(3):
            self.assertTrue(model.update(timestamp, 1, 0., .7))
            self.assertEqual(model.gain, .27)
        self.assertTrue(model.update(3, 1, 0., .7))
        self.assertAlmostEqual(model.gain, .7)
        self.assertEqual(model.gain_changes, 1)
        self.assertFalse(model.update(3, 1, 0., .9))

    def test_prospective_history_remains_immutable_across_fallback(self):
        runtime = self.runtime(); controller = runtime.controller
        old_filter = controller.core.filter
        old_filter.step(1)
        self.fit(runtime)
        old_filter.step(-1)
        gains, actions = old_filter.transition_gains, tuple(old_filter.actions)
        self.assertEqual(gains, (.27, .6))
        self.assertTrue(runtime.authorise_recovery('operator', self.ready(runtime), 5))
        self.assertEqual(old_filter.transition_gains, gains)
        self.assertEqual(tuple(old_filter.actions), actions)
        self.assertEqual(controller.core.filter.transition_gains, ())
        controller.core.filter.step(1)
        self.assertEqual(controller.core.filter.transition_gains, (.27,))

    def test_signed_identity_evidence_and_legacy_bypass_guards_still_apply(self):
        runtime = self.runtime(); controller = runtime.controller
        self.fit(runtime)
        approval = sign_approval(SECRET, 'operator', 'supervisor', 0, 'early', 20)
        self.assertFalse(runtime.authorise_recovery('operator', approval, 0))
        approval = self.ready(runtime)
        wrong_signature = sign_approval(b'other-secret-of-sufficient-length', 'operator',
            'supervisor', controller.incident, 'other', 20)
        self.assertFalse(runtime.authorise_recovery('operator', wrong_signature, 5))
        self.assertFalse(controller.authorize_signed(approval, 5))
        self.assertFalse(controller.approve_recovery(True))
        with self.assertRaises(PermissionError):
            controller._reseed_observation(5, observed_now=5, position=.2, velocity=.1)
        self.assertEqual(controller.core.gain, .6)
        self.assertEqual(controller.recovery_epoch_resets, 0)
        self.assertTrue(runtime.authorise_recovery('operator', approval, 5))
        self.assertFalse(runtime.authorise_recovery('operator', approval, 5))
        self.assertEqual(controller.recovery_epoch_resets, 1)

    def test_abstention_and_freshness_guards_preserved_before_and_after_recovery(self):
        runtime = self.runtime(); self.fit(runtime)
        approval = self.ready(runtime)
        self.assertIsNone(runtime.tick().action)
        self.assertEqual(runtime.controller.core.gain, .6)
        self.assertTrue(runtime.authorise_recovery('operator', approval, 5))
        self.assertIsNotNone(runtime.tick().action)
        runtime.advance_time(6)
        self.assertIsNone(runtime.tick().action)
        self.assertEqual(runtime.controller.recovery_epoch_resets, 1)

    def test_inherited_feasibility_guard_does_not_treat_zero_as_safe(self):
        runtime = self.runtime(safe_position=.01, safe_velocity=.01)
        controller = runtime.controller
        controller.core.filter.initial_position = 2.
        controller.core.filter._replay()
        self.assertIsNone(runtime.tick().action)
        self.assertEqual(controller.recovery_epoch_resets, 0)

    def test_gate_configuration_is_preserved_in_new_epoch(self):
        runtime = self.runtime(gain=.35, evidence_window=6, minimum=5,
                               error_multiplier=2., minimum_shift=.04)
        self.fit(runtime, .7)
        self.assertTrue(runtime.authorise_recovery('operator', self.ready(runtime), 5))
        model = runtime.controller.core.drift_model
        self.assertEqual((model.initial, model.samples.maxlen, model.minimum,
                          model.error_multiplier, model.minimum_shift), (.35, 6, 5, 2., .04))

    def test_constructor_rejects_conflicting_policy_and_invalid_prior_before_ledger(self):
        for kwargs in ({'forget_on_recovery': False}, {'forget_on_recovery': 1},
                       {'consistent_filter': False}, {'consistent_filter': 1},
                       {'gain': True}, {'gain': 0.}, {'gain': float('nan')},
                       {'minimum': True}, {'learning_rate': .1}):
            before = set(self.directory.iterdir())
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.runtime(**kwargs)
            self.assertEqual(set(self.directory.iterdir()), before)

    def test_recovery_authorization_scope_clears_after_verifier_exception(self):
        runtime = self.runtime(); self.fit(runtime)
        approval = self.ready(runtime)
        original = runtime.controller.verifier.verify
        def broken(*args): raise RuntimeError('verifier unavailable')
        runtime.controller.verifier.verify = broken
        with self.assertRaisesRegex(RuntimeError, 'verifier unavailable'):
            runtime.authorise_recovery('operator', approval, 5)
        self.assertFalse(runtime.controller._identity_recovery_in_progress)
        self.assertEqual(runtime.controller.core.gain, .6)
        runtime.controller.verifier.verify = original
        self.assertTrue(runtime.authorise_recovery('operator', approval, 5))


if __name__ == '__main__': unittest.main()
