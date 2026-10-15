"""Local runtime fixtures; no registered experimental stream is consumed."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.forecast_runtime import ForecastResearchRuntime
from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.phase_forecast import PhaseAwareForecaster
from nerve_awim.recovery_v25 import sign_approval
from nerve_awim.runtime_v28 import NerveResearchRuntime

SECRET = b'synthetic-forecast-test-secret-32bytes'


class Verifier:
    def verify(self, token, now):
        roles = {'reporter': {'actual-action-observer'},
                 'recovery': {'recovery-supervisor'}, 'agent': {'agent'}}
        if token == 'expired':
            return VerifiedIdentity('reporter', 'test', 'forecast',
                                    frozenset({'actual-action-observer'}), now-1)
        if token in roles:
            return VerifiedIdentity(token, 'test', 'forecast', frozenset(roles[token]), now+1)


class ForecastRuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.counter = 0

    def runtime(self, **kwargs):
        self.counter += 1
        return NerveResearchRuntime(verifier=Verifier(), issuer='test', audience='forecast',
            secret=SECRET, ledger_path=str(self.directory/f'{self.counter}.sqlite'), **kwargs)

    def forecaster(self, **kwargs):
        return PhaseAwareForecaster(verifier=Verifier(), issuer='test', audience='forecast',
                                    subjects=frozenset({'reporter'}), **kwargs)

    def wrapper(self, **kwargs):
        return ForecastResearchRuntime(self.runtime(), self.forecaster(), **kwargs)

    def confirm(self, wrapped, step=0, now=None):
        result = wrapped.tick()
        return wrapped.report_executed('reporter', now=step if now is None else now,
            step=step, action=result.action, source='controller')

    def test_tick_never_confirms_execution_or_changes_returned_command(self):
        wrapped = self.wrapper()
        before = wrapped.forecaster.snapshot()
        result = wrapped.tick()
        self.assertEqual(result, self.runtime().tick())
        self.assertEqual(wrapped.forecaster.snapshot(), before)
        self.assertEqual(wrapped.snapshot()['pending_step'], 0)
        history = list(wrapped.controller.core.filter.actions)
        with self.assertRaisesRegex(RuntimeError, 'executed_action_report_required'):
            wrapped.tick()
        self.assertEqual(wrapped.controller.core.filter.actions, history)

    def test_captured_controller_prediction_not_mutable_caller_state(self):
        wrapped = self.wrapper()
        gain, velocity = wrapped.controller.core.gain, wrapped.controller.core.filter.state.velocity
        result = wrapped.tick()
        wrapped.controller.core.gain = .9
        forecast = wrapped.report_executed('reporter', now=0, step=0,
                                           action=result.action, source='controller')
        self.assertEqual(forecast.velocity, .82*velocity+gain*result.action)
        self.assertEqual(wrapped.forecaster.snapshot()['next_step'], 1)

    def test_reporting_requires_separate_reporter_authority_and_is_atomic(self):
        wrapped = self.wrapper(); result = wrapped.tick(); before = wrapped.snapshot()
        for token in ('agent', 'recovery', 'expired', 'unknown'):
            with self.assertRaises(PermissionError):
                wrapped.report_executed(token, now=0, step=0, action=result.action, source='controller')
            self.assertEqual(wrapped.snapshot(), before)
            with self.assertRaises(PermissionError): wrapped.report_unknown(token, now=0, step=0)
            self.assertEqual(wrapped.snapshot(), before)

    def test_wrong_step_action_source_and_replay_rejected(self):
        wrapped = self.wrapper(); result = wrapped.tick(); before = wrapped.snapshot()
        for change in ({'step': True}, {'step': 1}, {'source': 'agent'},
                       {'source': 'external_supervisor'}, {'action': True},
                       {'action': -1 if result.action != -1 else 1}):
            args = dict(now=0, step=0, action=result.action, source='controller'); args.update(change)
            with self.assertRaises(ValueError): wrapped.report_executed('reporter', **args)
            self.assertEqual(wrapped.snapshot(), before)
        wrapped.report_executed('reporter', now=0, step=0, action=result.action, source='controller')
        with self.assertRaisesRegex(ValueError, 'no_matching_pending_action'):
            wrapped.report_executed('reporter', now=0, step=0, action=result.action, source='controller')

    def test_late_report_requires_explicit_unknown_and_monotonic_clock(self):
        wrapped = self.wrapper(); result = wrapped.tick(); before = wrapped.snapshot()
        with self.assertRaisesRegex(ValueError, 'outside_deadline'):
            wrapped.report_executed('reporter', now=2, step=0, action=result.action, source='controller')
        self.assertEqual(wrapped.snapshot(), before)
        forecast = wrapped.report_unknown('reporter', now=2, step=0)
        self.assertIsNone(forecast.velocity)
        self.assertFalse(wrapped.forecaster.snapshot()['known'])
        result = wrapped.tick()
        with self.assertRaisesRegex(ValueError, 'monotonic'):
            wrapped.report_executed('reporter', now=1, step=1, action=result.action, source='controller')
        wrapped.report_executed('reporter', now=2, step=1, action=result.action, source='controller')
        self.assertFalse(wrapped.forecaster.snapshot()['known'])

    def test_external_action_requires_abstention_and_does_not_recover(self):
        wrapped = ForecastResearchRuntime(self.runtime(max_missing=1), self.forecaster())
        wrapped.sensor_missing(); result = wrapped.tick()
        self.assertIsNone(result.action)
        with self.assertRaises(ValueError):
            wrapped.report_executed('reporter', now=0, step=0, action=0, source='controller')
        forecast = wrapped.report_executed('reporter', now=0, step=0, action=0, source='external_supervisor')
        self.assertEqual(forecast.source, 'external_supervisor')
        self.assertNotEqual(wrapped.controller.phase, 'active')

    def test_observation_mirror_requires_actual_accepted_sensor_and_is_once_only(self):
        wrapped = self.wrapper(); self.confirm(wrapped)
        with self.assertRaisesRegex(ValueError, 'accepted_observation_required'):
            wrapped.report_observation('reporter', now=1, step=0)
        self.assertTrue(wrapped.observe(0, position=.2, velocity=.1))
        before = wrapped.snapshot()
        with self.assertRaises(PermissionError): wrapped.report_observation('agent', now=1, step=0)
        self.assertEqual(wrapped.snapshot(), before)
        wrapped.report_observation('reporter', now=1, step=0)
        self.assertEqual(wrapped.snapshot()['pending_observations'], 0)
        with self.assertRaises(ValueError): wrapped.report_observation('reporter', now=1, step=0)

    def test_unknown_history_recovered_only_by_accepted_current_observation(self):
        wrapped = self.wrapper(); wrapped.tick()
        wrapped.report_unknown('reporter', now=0, step=0)
        self.assertFalse(wrapped.forecaster.snapshot()['known'])
        wrapped.observe(0, position=.2, velocity=.1)
        wrapped.report_observation('reporter', now=1, step=0)
        self.assertTrue(wrapped.forecaster.snapshot()['known'])
        self.assertEqual(wrapped.forecaster.snapshot()['velocity'], .1)

    def test_recovery_authority_still_requires_identity_and_signed_approval(self):
        wrapped = ForecastResearchRuntime(self.runtime(max_missing=1, recovery_samples=2), self.forecaster())
        wrapped.sensor_missing(); wrapped.tick()
        wrapped.report_executed('reporter', now=0, step=0, action=0, source='external_supervisor')
        wrapped.observe_recovery(1, observed_now=1, position=.1, velocity=.1)
        wrapped.observe_recovery(2, observed_now=2, position=.2, velocity=.2)
        wrapped.advance_time(2)
        approval = sign_approval(SECRET, 'recovery', 'supervisor', wrapped.controller.incident, 'nonce', 20)
        self.assertFalse(wrapped.authorise_recovery('reporter', approval, 2))
        self.assertTrue(wrapped.authorise_recovery('recovery', approval, 2))
        self.assertEqual(wrapped.controller.phase, 'active')
        self.assertEqual(wrapped.snapshot()['pending_observations'], 2)

    def test_rejected_or_partial_sensor_never_becomes_accepted_receipt(self):
        wrapped = self.wrapper(); self.confirm(wrapped)
        wrapped.observe(0, position=.2)
        with self.assertRaises(ValueError): wrapped.report_observation('reporter', now=1, step=0)
        with patch.object(wrapped.runtime, 'observe_recovery', return_value=False):
            self.assertFalse(wrapped.observe_recovery(0, observed_now=0, position=.2, velocity=.1))
        with self.assertRaises(ValueError): wrapped.report_observation('reporter', now=1, step=0)

    def test_bounded_observation_receipts_evict_without_changing_controller(self):
        wrapped = self.wrapper(max_pending_observations=1)
        self.confirm(wrapped)
        wrapped.observe(0, position=.1, velocity=.1)
        self.confirm(wrapped, 1)
        wrapped.observe(1, position=.2, velocity=.1)
        self.assertEqual(wrapped.snapshot()['evicted_observations'], 1)
        self.assertEqual(wrapped.snapshot()['pending_observations'], 1)
        with self.assertRaises(ValueError): wrapped.report_observation('reporter', now=2, step=0)
        wrapped.report_observation('reporter', now=2, step=1)

    def test_router_failure_keeps_pending_command_and_does_not_call_controller_again(self):
        wrapped = self.wrapper(); result = wrapped.tick(); before = wrapped.snapshot()
        with patch.object(wrapped.forecaster, 'record_action', side_effect=RuntimeError('observer unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'observer unavailable'):
                wrapped.report_executed('reporter', now=0, step=0, action=result.action, source='controller')
        self.assertEqual(wrapped.snapshot(), before)
        wrapped.report_unknown('reporter', now=0, step=0)
        self.assertEqual(len(wrapped.controller.core.filter.actions), 1)

    def test_history_budget_exhaustion_never_invents_external_prediction(self):
        wrapped = ForecastResearchRuntime(self.runtime(max_missing=1), self.forecaster(max_history=1))
        self.confirm(wrapped)
        wrapped.sensor_missing()
        self.assertIsNone(wrapped.tick().action)
        result = wrapped.report_executed('reporter', now=1, step=1, action=0,
                                         source='external_supervisor')
        self.assertIsNone(result.velocity)
        self.assertEqual(result.status, 'history_budget_exhausted')
        self.assertIsNone(wrapped.snapshot()['pending_step'])
        self.assertNotEqual(wrapped.controller.phase, 'active')

    def test_failed_tick_cannot_be_retried_as_new_execution(self):
        wrapped = self.wrapper()
        with patch.object(wrapped.runtime, 'tick', side_effect=RuntimeError('controller error')) as tick:
            with self.assertRaisesRegex(RuntimeError, 'controller error'): wrapped.tick()
            with self.assertRaisesRegex(RuntimeError, 'requires_new_session'): wrapped.tick()
            self.assertEqual(tick.call_count, 1)
        self.assertTrue(wrapped.snapshot()['tick_failed'])
        self.assertIsNone(wrapped.snapshot()['pending_step'])

    def test_fresh_attachment_required_and_configuration_must_match(self):
        for change in ('tick', 'time', 'observer', 'retention', 'gain'):
            runtime, forecaster = self.runtime(), self.forecaster()
            if change == 'tick': runtime.tick()
            if change == 'time': runtime.advance_time(0)
            if change == 'observer': forecaster.record_unknown('reporter', now=0, step=0)
            if change == 'retention': forecaster = self.forecaster(retention=.8)
            if change == 'gain': forecaster = self.forecaster(initial_gain=.3)
            with self.assertRaises(ValueError): ForecastResearchRuntime(runtime, forecaster)
        for args in ({'max_report_delay': True}, {'max_report_delay': -1},
                     {'max_pending_observations': 0}, {'max_pending_observations': 10001}):
            with self.assertRaises(ValueError): self.wrapper(**args)


if __name__ == '__main__': unittest.main()
