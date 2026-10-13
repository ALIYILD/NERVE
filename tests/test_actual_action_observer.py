"""Synthetic factual-action observation; never authorises controller execution."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from copy import deepcopy
from dataclasses import replace
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from nerve_awim.actual_action_observer import ActualActionObserver
from nerve_awim.consistent_dynamics import ProspectiveGainFilter, ConsistentDynamicsRuntime
from nerve_awim.identity_v26 import VerifiedIdentity


class Verifier:
    def __init__(self, identity=None):
        self.identity = identity or VerifiedIdentity(
            'reporter', 'test-idp', 'tenant-a/observer',
            frozenset({'actual-action-observer'}), 100)

    def verify(self, token, now):
        return self.identity if token == 'verified' else None


class ActualActionObserverTests(unittest.TestCase):
    def observer(self, **kwargs):
        return ActualActionObserver(verifier=kwargs.pop('verifier', Verifier()),
            issuer='test-idp', audience='tenant-a/observer',
            subjects=frozenset({'reporter'}), **kwargs)

    def state(self, observer):
        return (deepcopy(observer._filter.__dict__), observer.snapshot(), observer._last_now)

    def action(self, observer, **kwargs):
        values = dict(now=1, step=0, action=1, gain=.27)
        values.update(kwargs)
        return observer.record_action('verified', **values)

    def test_authority_checks_each_identity_dimension_without_mutating(self):
        identity = Verifier().identity
        identities = [None, object(), replace(identity, issuer='other'),
            replace(identity, audience='tenant-b/observer'),
            replace(identity, subject='intruder'),
            replace(identity, roles=frozenset({'recovery-supervisor'})),
            replace(identity, roles={'actual-action-observer'}),
            replace(identity, expires_at=0), replace(identity, expires_at=True),
            replace(identity, expires_at=1.)]
        for invalid in identities:
            with self.subTest(identity=invalid):
                verifier = Verifier()
                verifier.identity = invalid
                observer = self.observer(verifier=verifier)
                before = self.state(observer)
                with self.assertRaises(PermissionError): self.action(observer)
                self.assertEqual(self.state(observer), before)

    def test_each_mutating_operation_requires_verified_token(self):
        observer = self.observer()
        self.action(observer)
        operations = [lambda: observer.record_action('bad', now=2, step=1, action=0, gain=.2),
            lambda: observer.record_unknown('bad', now=2, step=1),
            lambda: observer.observe('bad', now=2, step=0, position=0., velocity=0.)]
        for operation in operations:
            before = self.state(observer)
            with self.assertRaises(PermissionError): operation()
            self.assertEqual(self.state(observer), before)

    def test_expiry_boundary_and_monotonic_host_time(self):
        observer = self.observer()
        self.action(observer, now=100)
        before = self.state(observer)
        with self.assertRaises(PermissionError): self.action(observer, now=101, step=1)
        for now in (True, 99, -1, 100., float('nan')):
            with self.subTest(now=now):
                with self.assertRaises(ValueError): self.action(observer, now=now, step=1)
                self.assertEqual(self.state(observer), before)
        # Equal host time is allowed; action sequence still must advance.
        self.action(observer, now=100, step=1)

    def test_factual_actions_propagate_independent_physics(self):
        observer = self.observer(retention=.5)
        p = v = 0.
        for step, (action, gain) in enumerate(((1,.2),(-1,.8),(0,.3),(1,.4))):
            forecast = self.action(observer, now=step, step=step, action=action, gain=gain)
            v = .5*v + gain*action
            p += v
            self.assertAlmostEqual(forecast.velocity, v)
            self.assertAlmostEqual(forecast.position, p)
            self.assertEqual(forecast.status, 'observed_action_forecast')
        self.assertEqual(observer._filter.transition_gains, (.2,.8,.3,.4))

    def test_gap_is_unknown_not_zero_and_only_latest_checkpoint_recovers(self):
        observer = self.observer()
        self.action(observer)
        forecast = self.action(observer, now=2, step=2, action=0)
        self.assertIsNone(forecast.position)
        self.assertIsNone(forecast.velocity)
        self.assertFalse(observer.snapshot()['known'])
        self.assertEqual(observer.snapshot()['history_steps'], 1)
        before = self.state(observer)
        with self.assertRaisesRegex(ValueError, 'current_checkpoint_required'):
            observer.observe('verified', now=3, step=0, position=.2, velocity=.2)
        self.assertEqual(self.state(observer), before)
        forecast = self.action(observer, now=3, step=3)
        self.assertIsNone(forecast.velocity)
        checkpoint = observer.observe('verified', now=4, step=3, position=2., velocity=.5)
        self.assertTrue(checkpoint['known'])
        self.assertEqual(checkpoint['epoch_origin'], 4)
        self.assertEqual(checkpoint['history_steps'], 0)
        forecast = self.action(observer, now=5, step=4, action=-1, gain=.2)
        self.assertAlmostEqual(forecast.velocity, .82*.5-.2)
        self.assertAlmostEqual(forecast.position, 2.+.82*.5-.2)
        before = self.state(observer)
        with self.assertRaisesRegex(ValueError, 'sensor_before_observer_epoch'):
            observer.observe('verified', now=6, step=3, position=2., velocity=.5)
        self.assertEqual(self.state(observer), before)

    def test_explicit_unknown_never_invents_action(self):
        observer = self.observer()
        result = observer.record_unknown('verified', now=1, step=0)
        self.assertEqual(result.status, 'unknown_action_history')
        self.assertIsNone(result.velocity)
        self.assertEqual(observer._filter.actions, [])
        self.assertEqual(observer.next_step, 1)
        observer.observe('verified', now=2, step=0, position=.4, velocity=.1)
        self.assertEqual(observer.snapshot()['position'], .4)

    def test_delayed_reading_preserves_historical_gain_and_changes_estimate(self):
        observer = self.observer(retention=.5)
        self.action(observer, gain=.2)
        self.action(observer, now=2, step=1, gain=.8)
        before = observer.snapshot()['velocity']
        observer.observe('verified', now=3, step=0, position=.4, velocity=.2)
        self.assertEqual(observer._filter.transition_gains, (.2,.8))
        self.assertNotEqual(observer.snapshot()['velocity'], before)
        # With both observation residuals zero, replay exactly preserves physics.
        observer.observe('verified', now=4, step=0, position=.2, velocity=.2)
        self.assertAlmostEqual(observer.snapshot()['velocity'], .9)
        self.assertAlmostEqual(observer.snapshot()['position'], 1.1)

    def test_invalid_actions_and_gains_do_not_mutate(self):
        observer = self.observer()
        for key, values in {'action':(True,1.,2,None), 'step':(True,-1,.5),
                'gain':(True,0.,1.1,float('nan'),float('inf'))}.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    before = self.state(observer)
                    with self.assertRaises(ValueError): self.action(observer, **{key:value})
                    self.assertEqual(self.state(observer), before)
        self.action(observer)
        before = self.state(observer)
        with self.assertRaises(ValueError): self.action(observer, now=2)
        self.assertEqual(self.state(observer), before)

    def test_invalid_sensor_values_do_not_mutate_or_advance_clock(self):
        observer = self.observer()
        self.action(observer)
        for key, values in {'position':(True,float('nan'),float('inf'),1e7),
                'velocity':(True,float('-inf'),-1e7), 'step':(True,-1,1,.5)}.items():
            for value in values:
                args = dict(now=2, step=0, position=.2, velocity=.2)
                args[key] = value
                before = self.state(observer)
                with self.assertRaises(ValueError): observer.observe('verified', **args)
                self.assertEqual(self.state(observer), before)

    def test_filter_failure_rolls_back_action_and_sensor_copies(self):
        observer = self.observer()
        self.action(observer)
        def broken(candidate, *args, **kwargs):
            candidate.actions.append(-1)
            raise OverflowError('synthetic injected replay overflow')
        for method, operation in (
                ('step', lambda: self.action(observer, now=2, step=1)),
                ('observe', lambda: observer.observe('verified', now=2, step=0, position=.2, velocity=.2))):
            before = self.state(observer)
            with patch.object(ProspectiveGainFilter, method, broken):
                with self.assertRaises(OverflowError): operation()
            self.assertEqual(self.state(observer), before)

    def test_real_numeric_bound_failure_does_not_commit_new_action(self):
        observer = self.observer()
        observer.record_unknown('verified', now=1, step=0)
        observer.observe('verified', now=2, step=0, position=1e6, velocity=1e6)
        before = self.state(observer)
        with self.assertRaises(ValueError): self.action(observer, now=3, step=1)
        self.assertEqual(self.state(observer), before)

    def test_history_quota_is_bounded_and_explicit_checkpoint_resets_epoch(self):
        observer = self.observer(max_history=2)
        self.action(observer)
        self.action(observer, now=2, step=1)
        forecast = self.action(observer, now=3, step=2)
        self.assertEqual(forecast.status, 'history_budget_exhausted')
        self.assertIsNone(forecast.position)
        self.assertFalse(observer.snapshot()['known'])
        self.assertEqual(observer.snapshot()['history_steps'], 2)
        self.assertEqual(observer.next_step, 3)
        observer.observe('verified', now=4, step=2, position=.4, velocity=.1)
        self.action(observer, now=5, step=3)
        self.assertEqual(observer.snapshot()['history_steps'], 1)

    def test_concurrent_duplicate_reports_commit_only_once(self):
        observer = self.observer()
        barrier = Barrier(8)
        def submit(_):
            barrier.wait(timeout=5)
            try:
                return self.action(observer).status
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(submit, range(8)))
        self.assertEqual(results.count('observed_action_forecast'), 1)
        self.assertEqual(results.count('replayed_or_invalid_action_step'), 7)
        self.assertEqual(observer.next_step, 1)
        self.assertEqual(observer._filter.actions, [1])
        self.assertAlmostEqual(observer.snapshot()['position'], .27)

    def test_constructor_rejects_bool_and_invalid_numeric_configuration(self):
        for kwargs in ({'retention':True}, {'retention':1.}, {'initial_gain':False},
                {'initial_gain':float('nan')}, {'max_history':True},
                {'max_history':0}, {'max_history':10001}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError): self.observer(**kwargs)

    def test_observer_does_not_change_blocked_controller_or_authorise_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = ConsistentDynamicsRuntime(verifier=Verifier(), issuer='test-idp',
                audience='tenant-a/observer', secret=b'synthetic-only-observer-test-secret',
                ledger_path=str(Path(temp)/'recovery.sqlite'), max_missing=1)
            runtime.sensor_missing()
            controller = runtime.controller
            before = (controller.phase, deepcopy(controller.core.filter.__dict__), controller.core.gain)
            observer = self.observer()
            self.action(observer, action=-1)
            observer.observe('verified', now=2, step=0, position=-.2, velocity=-.2)
            self.assertEqual((controller.phase, controller.core.filter.__dict__, controller.core.gain), before)
            with self.assertRaises(RuntimeError): controller.choose()
            self.assertIsNone(runtime.tick().action)


if __name__ == '__main__':
    unittest.main()
