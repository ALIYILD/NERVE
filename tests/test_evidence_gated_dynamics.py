import copy
from pathlib import Path
import tempfile
import unittest

from nerve_awim.evidence_gated_dynamics import EvidenceGatedGain, EvidenceGatedRuntime
from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.recovery_v25 import sign_approval


SECRET = b'synthetic-evidence-gated-secret-32'


class Verifier:
    def verify(self, token, now):
        if token == 'valid':
            return VerifiedIdentity('operator', 'test', 'nerve',
                frozenset({'recovery-supervisor'}), now + 100)


class EvidenceGatedTests(unittest.TestCase):
    def runtime(self, directory, **kwargs):
        return EvidenceGatedRuntime(verifier=Verifier(), issuer='test', audience='nerve',
            secret=SECRET, ledger_path=str(Path(directory) / 'ledger.sqlite'),
            estimator='drift', max_missing=1, recovery_samples=2, **kwargs)

    def test_minimum_evidence_is_required_even_for_large_shift(self):
        model = EvidenceGatedGain()
        for timestamp in range(3):
            self.assertTrue(model.update(timestamp, 1, 0., .8))
            self.assertEqual(model.gain, .27)
            self.assertEqual(model.gain_changes, 0)
            self.assertIsNone(model.last_threshold)
        self.assertTrue(model.update(3, 1, 0., .8))
        self.assertAlmostEqual(model.gain, .8)
        self.assertEqual(model.gain_changes, 1)
        self.assertAlmostEqual(model.last_threshold, .03)

    def test_stationary_and_small_noisy_shifts_hold_gain(self):
        for samples in ([.27] * 12, [.25, .29, .28, .26] * 3,
                        [.28, .29, .30, .29] * 3):
            model = EvidenceGatedGain()
            for timestamp, value in enumerate(samples):
                self.assertTrue(model.update(timestamp, 1, 0., value))
                self.assertEqual(model.gain, .27)
            self.assertEqual(model.gain_changes, 0)
            self.assertEqual(len(model.processed), 12)

    def test_clear_shift_adapts_and_stable_evidence_does_not_churn(self):
        model = EvidenceGatedGain()
        for timestamp, value in enumerate([.27] * 4 + [.6] * 8):
            self.assertTrue(model.update(timestamp, -1, .2, .82 * .2 - value))
        self.assertAlmostEqual(model.gain, .6)
        self.assertEqual(model.gain_changes, 1)
        self.assertAlmostEqual(model.variance, 0.)

    def test_high_variance_blocks_shift_until_new_consistent_evidence(self):
        model = EvidenceGatedGain()
        for timestamp, value in enumerate([-.2, 1.2, -.2, 1.2]):
            self.assertTrue(model.update(timestamp, 1, 0., value))
        self.assertAlmostEqual(model.variance, .49)
        self.assertGreater(model.last_threshold, abs(.5 - .27))
        self.assertEqual(model.gain, .27)
        for timestamp in range(4, 8):
            self.assertTrue(model.update(timestamp, 1, 0., .5))
        self.assertEqual(model.gain, .5)
        self.assertEqual(model.gain_changes, 1)

    def test_invalid_and_duplicate_evidence_never_changes_any_state(self):
        model = EvidenceGatedGain()
        model.update(1, 1, 0., .4)
        for args in ((1, 1, 0., .8), (True, 1, 0., .4), (-1, 1, 0., .4),
                     (2, True, 0., .4), (2, 0, 0., .4), (2, 1, True, .4),
                     (2, 1, float('nan'), .4), (2, 1, 0., float('inf')),
                     (2, 1, 0., 1.31), (2, 1, 0., -.31), (2, 1, 0., .4, 1.)):
            before = copy.deepcopy(vars(model))
            self.assertFalse(model.update(*args))
            self.assertEqual(vars(model), before)

    def test_out_of_order_window_uses_transition_time_and_rejects_old_data(self):
        model = EvidenceGatedGain()
        for timestamp in (4, 2, 5, 3):
            self.assertTrue(model.update(timestamp, 1, 0., .6))
        self.assertEqual([stamp for stamp, _ in model.samples], [2, 3, 4, 5])
        before = copy.deepcopy(vars(model))
        self.assertFalse(model.update(1, 1, 0., .9))
        self.assertEqual(vars(model), before)
        self.assertTrue(model.update(6, 1, 0., .6))
        self.assertEqual([stamp for stamp, _ in model.samples], [3, 4, 5, 6])

    def test_forget_retains_gain_but_requires_fresh_minimum_evidence(self):
        model = EvidenceGatedGain()
        for timestamp in range(4):
            model.update(timestamp, 1, 0., .7)
        model.forget_window()
        self.assertAlmostEqual(model.gain, .7)
        self.assertEqual(len(model.samples), 0)
        self.assertEqual(model.evidence_resets, 1)
        self.assertIsNone(model.last_threshold)
        self.assertFalse(model.update(0, 1, 0., .1))
        for timestamp in range(4, 7):
            self.assertTrue(model.update(timestamp, 1, 0., .1))
            self.assertAlmostEqual(model.gain, .7)
        self.assertTrue(model.update(7, 1, 0., .1))
        self.assertAlmostEqual(model.gain, .1)
        self.assertEqual(model.gain_changes, 2)

    def test_clipping_keeps_accepted_shifts_in_model_bounds(self):
        for value, expected in ((1.3, 1.), (-.3, .01)):
            model = EvidenceGatedGain()
            for timestamp in range(4):
                self.assertTrue(model.update(timestamp, 1, 0., value))
            self.assertEqual(model.gain, expected)

    def test_strict_configuration(self):
        for kwargs in ({'minimum': True}, {'minimum': 1}, {'minimum': 5},
                       {'window': True}, {'window': 65}, {'window': 3.},
                       {'minimum': 4.}, {'initial': True}, {'initial': 0.},
                       {'error_multiplier': True}, {'error_multiplier': 0.},
                       {'error_multiplier': 11.}, {'error_multiplier': float('nan')},
                       {'minimum_shift': True}, {'minimum_shift': 0.},
                       {'minimum_shift': .51}, {'minimum_shift': float('inf')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                EvidenceGatedGain(**kwargs)
        with tempfile.TemporaryDirectory() as temp:
            for kwargs in ({'forget_on_recovery': 1}, {'learning_rate': .1},
                           {'prior_weight': 4.}, {'prior_weight': 8.}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    self.runtime(temp, **kwargs)

    def test_recovery_requires_identity_and_preserves_gain_with_both_policies(self):
        for forget in (False, True):
            with self.subTest(forget=forget), tempfile.TemporaryDirectory() as temp:
                runtime = self.runtime(temp, forget_on_recovery=forget, planning_horizon=3)
                controller = runtime.controller
                model = controller.core.drift_model
                self.assertIsInstance(model, EvidenceGatedGain)
                for timestamp in range(4):
                    model.update(timestamp, 1, 0., .6)
                controller.core.gain = model.gain
                controller.core.filter.set_next_gain(model.gain)
                before = copy.deepcopy(vars(model))
                runtime.sensor_missing()
                runtime.observe_recovery(1, observed_now=1, position=.1, velocity=.1)
                runtime.observe_recovery(2, observed_now=2, position=.2, velocity=.2)
                approval = sign_approval(SECRET, 'operator', 'supervisor',
                    controller.incident, 'nonce', 200)
                self.assertFalse(runtime.authorise_recovery('bad', approval, 100))
                self.assertEqual(vars(model), before)
                with self.assertRaises(ValueError):
                    controller._reseed_observation(-1, observed_now=-1, position=0., velocity=0.)
                self.assertEqual(vars(model), before)
                self.assertTrue(runtime.authorise_recovery('valid', approval, 100))
                self.assertEqual(model.gain, before['gain'])
                self.assertEqual(controller.core.filter.b, model.gain)
                self.assertEqual(model.processed, set())
                self.assertEqual(len(model.samples), 0 if forget else 4)
                if not forget:
                    self.assertEqual([stamp for stamp, _ in model.samples], [-4, -3, -2, -1])
                self.assertIsNotNone(runtime.tick().action)

    def test_runtime_missing_pairs_dedup_and_prospective_filter_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            controller = self.runtime(temp).controller
            controller.core.filter.step(1)
            controller.core.filter.step(1)
            controller.ingest(1, velocity=.8)
            model = controller.core.drift_model
            self.assertEqual(len(model.samples), 0)
            controller.ingest(0, velocity=.27)
            self.assertEqual(len(model.samples), 1)
            self.assertEqual(model.gain, .27)
            self.assertEqual(controller.core.filter.b, .27)
            before = copy.deepcopy(vars(model))
            controller.ingest(0, velocity=.27)
            self.assertEqual(vars(model), before)
            self.assertEqual(controller.core.filter.transition_gains, (.27, .27))


if __name__ == '__main__':
    unittest.main()
