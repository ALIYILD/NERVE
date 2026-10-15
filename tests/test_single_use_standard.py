"""Single-use fitting correctness fixtures, not performance experiments."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.integrated_v13 import SensorOnlyController
from nerve_awim.recovery_v25 import sign_approval
from nerve_awim.single_use_standard import (SingleUseStandardGain,
    SingleUseStandardController, SingleUseStandardRuntime)

SECRET = b'synthetic-single-use-standard-secret'


class Verifier:
    def verify(self, token, now):
        if token in ('operator', 'agent'):
            role = 'recovery-supervisor' if token == 'operator' else 'agent'
            return VerifiedIdentity(token, 'test', 'nerve', frozenset({role}), now+10)


class SingleUseGainTests(unittest.TestCase):
    def test_exact_original_first_ema_update_and_duplicate_invariance(self):
        legacy = SensorOnlyController(learning_rate=.5)
        fixed = SingleUseStandardController(learning_rate=.5)
        for controller in (legacy, fixed):
            controller.filter.step(1); controller.filter.step(1)
            controller.ingest(0, velocity=.1)
            controller.ingest(1, velocity=.3)
        self.assertEqual(fixed.gain, legacy.gain)
        self.assertAlmostEqual(fixed.gain, .244)
        for _ in range(3):
            fixed.ingest(1, velocity=.3); legacy.ingest(1, velocity=.3)
            self.assertAlmostEqual(fixed.gain, .244)
        self.assertNotEqual(legacy.gain, fixed.gain)
        self.assertEqual(fixed.drift_model.processed, {1})
        self.assertEqual(fixed.observation_count, 5)  # Packet count, not unique evidence.
        self.assertEqual(fixed.estimator, 'standard')

    def test_missing_predecessor_can_arrive_late_without_losing_transition(self):
        fixed = SingleUseStandardController(learning_rate=.5)
        fixed.filter.step(1); fixed.filter.step(1)
        fixed.ingest(1, velocity=.3)
        self.assertEqual(fixed.drift_model.processed, set())
        self.assertEqual(fixed.gain, .27)
        fixed.ingest(0, velocity=.1)
        self.assertAlmostEqual(fixed.gain, .244)
        self.assertEqual(fixed.drift_model.processed, {1})

    def test_later_correction_updates_filter_but_not_consumed_fitting_pair(self):
        fixed = SingleUseStandardController(learning_rate=.5)
        fixed.filter.step(1); fixed.filter.step(1)
        fixed.ingest(0, velocity=.1); fixed.ingest(1, velocity=.3)
        before = fixed.filter.state
        fixed.ingest(1, velocity=.8)
        self.assertNotEqual(fixed.filter.state, before)
        self.assertEqual(fixed.filter.readings[1][1], .8)
        self.assertAlmostEqual(fixed.gain, .244)
        self.assertEqual(fixed.drift_model.processed, {1})

    def test_ema_depends_on_first_usable_pair_order_not_claimed_permutation_invariant(self):
        results = []
        for order in ((0, 1, 2), (2, 1, 0)):
            fixed = SingleUseStandardController(learning_rate=.5)
            for _ in range(3): fixed.filter.step(1)
            for index in order: fixed.ingest(index, velocity=(.1, .3, .5)[index])
            self.assertEqual(fixed.drift_model.processed, {1, 2})
            before = fixed.gain
            for index in order: fixed.ingest(index, velocity=(.1, .3, .5)[index])
            self.assertEqual(fixed.gain, before)
            results.append(before)
        self.assertAlmostEqual(results[0], .249)
        self.assertAlmostEqual(results[1], .240)

    def test_original_sample_bounds_and_gain_clipping_not_drift_bounds(self):
        for sample, expected in ((2., 1.), (-2., .01), (1.4, 1.), (-.5, .01)):
            model = SingleUseStandardGain(learning_rate=1.)
            self.assertTrue(model.update(1, 1, 0., sample))
            self.assertEqual(model.gain, expected)
            self.assertEqual(model.processed, {1})
        model = SingleUseStandardGain()
        self.assertFalse(model.update(1, 1, 0., 2.001))
        self.assertEqual(model.processed, set())
        self.assertTrue(model.update(1, 1, 0., 1.4))

    def test_invalid_and_zero_action_evidence_is_atomic_and_not_consumed(self):
        model = SingleUseStandardGain(learning_rate=.5)
        for args in ((True,1,0.,.3), (-1,1,0.,.3), (1,True,0.,.3),
                     (1,0,0.,.3), (1,1,True,.3), (1,1,0.,float('nan')),
                     (1,1,float('inf'),.3), (1,1,0.,.3,1.),
                     (1,1,0.,.3,True), (1,1,1e308,-1e308)):
            before = deepcopy(vars(model))
            self.assertFalse(model.update(*args))
            self.assertEqual(vars(model), before)
        self.assertTrue(model.update(1, -1, .1, -.136))
        self.assertAlmostEqual(model.gain, .244)

    def test_bounded_processed_budget_retains_gain_without_consuming_more(self):
        model = SingleUseStandardGain(learning_rate=.5, max_processed=2)
        self.assertTrue(model.update(1, 1, 0., .4))
        self.assertTrue(model.update(2, 1, 0., .6))
        self.assertTrue(model.budget_exhausted)
        before = deepcopy(vars(model))
        for timestamp in range(3, 20):
            self.assertFalse(model.update(timestamp, 1, 0., .8))
            self.assertEqual(vars(model), before)

    def test_zero_rate_remains_frozen_without_evidence_consumption(self):
        model = SingleUseStandardGain(learning_rate=0.)
        self.assertFalse(model.update(1, 1, 0., .6))
        self.assertEqual(model.gain, .27); self.assertEqual(model.processed, set())
        fixed = SingleUseStandardController(learning_rate=0.)
        self.assertIsNone(fixed.drift_model)
        fixed.filter.step(1); fixed.filter.step(1)
        fixed.ingest(0, velocity=.1); fixed.ingest(1, velocity=.3)
        self.assertEqual(fixed.gain, .27)

    def test_strict_constructor_configuration(self):
        for kwargs in ({'initial': True}, {'initial': 0.}, {'initial': float('nan')},
                       {'learning_rate': True}, {'learning_rate': -1.}, {'learning_rate': 1.1},
                       {'learning_rate': float('inf')}, {'max_processed': True},
                       {'max_processed': 0}, {'max_processed': 10001}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): SingleUseStandardGain(**kwargs)
        with self.assertRaises(ValueError): SingleUseStandardController(estimator='drift')


class SingleUseRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)

    def runtime(self, **kwargs):
        return SingleUseStandardRuntime(verifier=Verifier(), issuer='test', audience='nerve',
            secret=SECRET, ledger_path=str(self.directory/'ledger.sqlite'),
            max_missing=1, recovery_samples=2, **kwargs)

    def test_signed_recovery_resets_local_identity_budget_but_preserves_learned_gain(self):
        runtime = self.runtime(learning_rate=.5, max_processed=1)
        core = runtime.controller.core
        core.filter.step(1); core.filter.step(1)
        runtime.observe(0, velocity=.1); runtime.observe(1, velocity=.3)
        model = core.drift_model
        self.assertAlmostEqual(core.gain, .244)
        self.assertTrue(model.budget_exhausted)
        runtime.sensor_missing()
        self.assertIsNone(runtime.tick().action)
        runtime.observe_recovery(4, observed_now=4, position=.1, velocity=.1)
        runtime.observe_recovery(5, observed_now=5, position=.2, velocity=.1)
        approval = sign_approval(SECRET, 'operator', 'supervisor', runtime.controller.incident, 'nonce', 20)
        before = deepcopy(vars(model))
        for token in ('bad', 'agent'):
            self.assertFalse(runtime.authorise_recovery(token, approval, 5))
            self.assertEqual(vars(model), before)
        self.assertTrue(runtime.authorise_recovery('operator', approval, 5))
        self.assertIs(core.drift_model, model)
        self.assertAlmostEqual(core.gain, .244)
        self.assertEqual(model.processed, set())
        self.assertFalse(model.budget_exhausted)
        self.assertEqual(runtime.controller.epoch_origin, 6)
        core.filter.step(1); core.filter.step(1)
        runtime.observe(6, velocity=.1); runtime.observe(7, velocity=.3)
        self.assertAlmostEqual(core.gain, .231)
        self.assertEqual(model.processed, {1})
        runtime.observe(7, velocity=.3)
        self.assertAlmostEqual(core.gain, .231)
        self.assertFalse(runtime.authorise_recovery('operator', approval, 7))
        self.assertEqual(model.processed, {1})

    def test_zero_rate_runtime_and_rejection_before_ledger_creation(self):
        for kwargs in ({'estimator': 'drift'}, {'learning_rate': True}, {'max_processed': 0}):
            with self.assertRaises(ValueError): self.runtime(**kwargs)
            self.assertFalse((self.directory/'ledger.sqlite').exists())
        runtime = self.runtime(learning_rate=0.)
        self.assertIsNone(runtime.controller.core.drift_model)
        self.assertEqual(runtime.controller.core.estimator, 'standard')


if __name__ == '__main__': unittest.main()
