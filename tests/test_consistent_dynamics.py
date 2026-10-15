import tempfile
import unittest
from functools import partial
from pathlib import Path
from unittest.mock import patch

from nerve_awim.consistent_dynamics import ProspectiveGainFilter, ConsistentDynamicsRuntime
from nerve_awim.fusion_v12 import FusedState, LaggedPositionVelocityFilter
from nerve_awim.memory_gateway import recovery_adaptation as experiment
from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.recovery_v25 import sign_approval

SECRET = b'synthetic-test-only-secret-32bytes'


class Verifier:
    def verify(self, token, now):
        if token == 'valid':
            return VerifiedIdentity('operator', 'test', 'nerve', frozenset({'recovery-supervisor'}), now+100)


class ConsistentDynamicsTests(unittest.TestCase):
    def runtime(self, directory, **kwargs):
        return ConsistentDynamicsRuntime(verifier=Verifier(), issuer='test', audience='nerve',
            secret=SECRET, ledger_path=str(Path(directory)/'ledger.sqlite'), **kwargs)

    def test_constant_gain_matches_existing_filter_with_delayed_corrections(self):
        old, new = LaggedPositionVelocityFilter(), ProspectiveGainFilter()
        for action in (1, -1, 0, 1):
            old.step(action); new.step(action)
        for timestamp, position, velocity in ((2, .3, .1), (0, .2, .25), (3, .5, .2)):
            old.observe(timestamp, position=position, velocity=velocity)
            new.observe(timestamp, position=position, velocity=velocity)
            self.assertEqual(old.states, new.states)
            self.assertEqual(old.innovations, new.innovations)

    def test_learning_only_changes_future_propagation(self):
        f = ProspectiveGainFilter(a=.5, b=.2)
        f.step(1)
        previous = f.state
        f.set_next_gain(.8)
        f.step(1)
        self.assertEqual(f.states[1], previous)
        self.assertAlmostEqual(f.state.velocity, .9)
        f.observe(0, position=.2, velocity=.2)
        self.assertAlmostEqual(f.state.velocity, .9)
        self.assertEqual(f.transition_gains, (.2, .8))
        before = (list(f.actions), list(f.transition_gains), list(f.states))
        for value in (True, float('nan'), 0., 2.):
            with self.assertRaises(ValueError): f.set_next_gain(value)
        with self.assertRaises(ValueError): f.step(True)
        self.assertEqual(before, (f.actions, list(f.transition_gains), f.states))

    def test_sensor_updates_gain_and_future_filter_coefficient(self):
        with tempfile.TemporaryDirectory() as temp:
            c = self.runtime(temp, estimator='drift', learning_rate=.08).controller
            c.core.filter.step(1); c.core.filter.step(1)
            c.ingest(0, position=.27, velocity=.27)
            c.ingest(1, position=1., velocity=.8)
            self.assertNotEqual(c.core.gain, .27)
            self.assertEqual(c.core.filter.b, c.core.gain)
            self.assertEqual(c.core.filter.transition_gains, (.27, .27))
            c.core.filter.step(1)
            self.assertEqual(c.core.filter.transition_gains[-1], c.core.gain)
            previous = c.core.gain
            with self.assertRaises(ValueError): c.ingest(-1, velocity=.5)
            self.assertEqual(c.core.filter.b, previous)

    def test_signed_recovery_keeps_gain_resets_history_and_preserves_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = self.runtime(temp, max_missing=1, recovery_samples=2, planning_horizon=3)
            c = runtime.controller
            c.core.gain = .4
            c.core.filter.set_next_gain(.4)
            runtime.sensor_missing()
            with self.assertRaises(RuntimeError): c.choose()
            self.assertIsNone(runtime.tick().action)
            runtime.observe_recovery(1, observed_now=1, position=.1, velocity=.1)
            runtime.observe_recovery(2, observed_now=2, position=.2, velocity=.2)
            approval = sign_approval(SECRET, 'operator', 'supervisor', c.incident, 'nonce', 200)
            self.assertFalse(c.authorize(approval))
            self.assertFalse(c.authorize_signed(approval, 100))
            self.assertFalse(runtime.authorise_recovery('bad', approval, 100))
            self.assertTrue(runtime.authorise_recovery('valid', approval, 100))
            self.assertEqual(c.core.filter.transition_gains, ())
            self.assertEqual(c.core.filter.b, .4)
            self.assertEqual(c.core.filter.state.position, .2)
            self.assertIsNotNone(runtime.tick().action)
            self.assertFalse(runtime.authorise_recovery('valid', approval, 100))
            runtime.advance_time(3)
            self.assertIsNone(runtime.tick().action)

    def test_candidate_options_strict(self):
        with tempfile.TemporaryDirectory() as temp:
            for horizon in (True, 0, 6, 1., float('nan')):
                with self.assertRaises(ValueError): self.runtime(temp, planning_horizon=horizon)
            with self.assertRaises(ValueError): self.runtime(temp, consistent_filter=1)

    def test_later_envelope_failure_is_not_hidden_by_safe_first_step(self):
        with tempfile.TemporaryDirectory() as temp:
            c = self.runtime(temp, safe_position=.1, planning_horizon=1).controller
            c.core.filter.states[-1] = FusedState(0., .1, .1, .1)
            self.assertEqual(c.choose(), 0)
            c.planning_horizon = 3
            before = c.infeasible
            with self.assertRaisesRegex(RuntimeError, 'no feasible planning sequence'):
                c.choose()
            self.assertEqual(c.infeasible, before+1)
            self.assertEqual(c.core.filter.actions, [])

    def test_historical_coefficients_cannot_be_mutated_through_public_view(self):
        f = ProspectiveGainFilter()
        f.step(1)
        with self.assertRaises(TypeError): f.transition_gains[0] = .8
        with self.assertRaises(AttributeError): f.transition_gains = (.8,)

    def test_mixed_gain_delayed_innovation_matches_independent_calculation(self):
        f = ProspectiveGainFilter(a=.5, b=.2)
        f.step(1)
        f.set_next_gain(.8)
        f.step(1)
        f.observe(0, position=.4)
        # First predicted covariance: Pxx=.1254, Pxv=.0254; R=.0025.
        corrected_p = .2 + (.1254/.1279)*.2
        corrected_v = .2 + (.0254/.1279)*.2
        expected_v = .5*corrected_v + .8
        self.assertAlmostEqual(f.state.velocity, expected_v)
        self.assertAlmostEqual(f.state.position, corrected_p+expected_v)

    def test_planning_depth_changes_choice_and_radius_remains_a_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            c = self.runtime(temp, target=1.2, safe_position=1., planning_horizon=1).controller
            c.core.filter.states[-1] = FusedState(0., 1., .1, .1)
            self.assertEqual(c.choose(), 0)
            c.planning_horizon = 3
            self.assertEqual(c.choose(), -1)
            with patch.object(c.auditor.calibrator, 'radius', return_value=10.):
                with self.assertRaises(RuntimeError): c.choose()
            self.assertEqual(c.core.filter.actions, [])

    def test_smoke_factorial_controls_are_executable_and_baseline_matches(self):
        baseline = experiment.episode(3, 'drift', True)
        for consistent in (False, True):
            for horizon in (1, 3):
                with patch.object(experiment, 'NerveResearchRuntime', partial(
                        ConsistentDynamicsRuntime, consistent_filter=consistent, planning_horizon=horizon)):
                    row = experiment.episode(3, 'drift', True)
                experiment.validate(row, 3, 'drift', True)
                self.assertEqual(row['schedule_sha256'], baseline['schedule_sha256'])
                self.assertEqual(row['metrics']['violations'], 0)
                self.assertEqual(row['metrics']['successful_recoveries'], 1)
                if not consistent and horizon == 1:
                    self.assertEqual(row, baseline)
