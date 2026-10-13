"""Online synthetic integration proof, never a performance or deployment study.

Development seeds only in the CLI. Ground truth is confined to simulated plant
execution and outcome scoring; authenticated reports contain actual actions.
"""
from copy import deepcopy
from dataclasses import asdict
import secrets
import tempfile
from pathlib import Path

from ..runtime_v28 import NerveResearchRuntime
from ..recovery_v25 import sign_approval
from ..forecast_runtime import ForecastResearchRuntime
from ..phase_forecast import PhaseAwareForecaster
from . import recovery_adaptation as baseline
from .recovery_adaptation import (STEPS, RETENTION, TARGET, INITIAL_GAIN, ISSUER, AUDIENCE,
    SyntheticVerifier, _inputs, _schedule, _digest, _metrics, validate)
from .observer_reanalysis import _ResearchReporter
from . import phase_forecast_episode as replay


def _state(controller):
    """Selected estimator/recovery state, excluding secrets and filesystem paths."""
    return deepcopy({'phase':controller.phase,'incident':controller.incident,
        'gain':controller.core.gain,'filter_state':asdict(controller.core.filter.state),
        'actions':list(controller.core.filter.actions),
        'fresh_count':controller.fresh_count,'approvals':controller.approvals,
        'audit':list(controller.audit),'last_packet':controller.last_packet,
        'recovery_after':controller.recovery_after,
        'last_recovery_timestamp':controller.last_recovery_timestamp,
        'epoch_origin':controller.epoch_origin,
        'processed':sorted(controller.core.drift_model.processed) if controller.core.drift_model else []})


def online_episode(seed: int, scenario: str, adaptive: bool, *, enabled=True) -> dict:
    _inputs(seed, scenario, adaptive)
    if type(enabled) is not bool:
        raise ValueError('enabled_must_be_bool')
    schedule = _schedule(seed)
    trace, events, forecasts, states = [], [], [], []
    position = velocity = 0.
    updates = 0
    secret = secrets.token_bytes(32)
    with tempfile.TemporaryDirectory(prefix='nerve-synthetic-recovery-') as directory:
        runtime = NerveResearchRuntime(
            verifier=SyntheticVerifier(), issuer=ISSUER, audience=AUDIENCE,
            secret=secret, ledger_path=str(Path(directory) / 'approvals.sqlite'),
            max_missing=5, recovery_samples=3, evidence_minimum=2,
            risk_aversion=.25, safe_position=6., safe_velocity=2.,
            min_samples=6, target=TARGET, learning_rate=.08 if adaptive else 0.,
            estimator='drift', horizon=3, bound=6.)
        if enabled:
            runtime = ForecastResearchRuntime(runtime, PhaseAwareForecaster(
                verifier=_ResearchReporter(), issuer='synthetic', audience='observer-reanalysis',
                subjects=frozenset({'trace-reporter'}), max_history=STEPS))
        controller = runtime.controller
        for t in range(STEPS):
            gain_before = controller.core.gain
            fit_before = (len(controller.core.drift_model.processed)
                          if controller.core.drift_model else 0)
            sensor = None
            if t:
                exogenous = schedule[t - 1]
                if not exogenous['dropped']:
                    sensor = dict(timestamp=t - 1,
                                  position=position + exogenous['position_noise'],
                                  velocity=velocity + exogenous['velocity_noise'])
                    if controller.phase == 'active':
                        runtime.observe(sensor['timestamp'], position=sensor['position'],
                                        velocity=sensor['velocity'])
                        sensor['route'] = 'active'
                        sensor['accepted'] = True
                    else:
                        sensor['route'] = 'recovery'
                        sensor['accepted'] = runtime.observe_recovery(
                            sensor['timestamp'], observed_now=t - 1,
                            position=sensor['position'], velocity=sensor['velocity'])
                        if controller.recovery_ready():
                            incident = controller.incident
                            retained_gain = controller.core.gain
                            approval = sign_approval(secret, 'synthetic-supervisor',
                                                     'supervisor', incident,
                                                     f'synthetic-{t}-{incident}', t)
                            granted = runtime.authorise_recovery(
                                'synthetic-host-approval', approval, t - 1)
                            events.append(dict(step=t, incident=incident,
                                               authorised=granted,
                                               gain_before=retained_gain,
                                               gain_after=controller.core.gain))
                if enabled and sensor is not None and sensor['accepted']:
                    runtime.report_observation('verified-trace',now=t,step=sensor['timestamp'])
                runtime.advance_time(t - 1)
            gain = controller.core.gain
            fit_after = (len(controller.core.drift_model.processed)
                         if controller.core.drift_model else 0)
            fitted = max(0, fit_after - fit_before)
            updates += fitted
            estimated_velocity = controller.core.filter.state.velocity
            history_before = len(controller.core.filter.actions)
            result = runtime.tick()
            if result.action is None and result.phase == 'active':
                raise RuntimeError('active controller infeasible; no supported external-action observation history')
            action = result.action if result.action is not None else 0
            source = 'controller' if result.action is not None else 'external_supervisor'
            prediction = RETENTION * estimated_velocity + gain * action
            plant_gain = INITIAL_GAIN if scenario == 'stationary' else (.27, .48, .15, .4)[t // 20]
            velocity = RETENTION * velocity + plant_gain * action
            position += velocity
            # Actual action is reported only after the synthetic plant executes it.
            # The resulting forecast is recorded before any outcome scoring.
            if enabled:
                forecast = runtime.report_executed('verified-trace',now=t,step=t,
                                                   action=action,source=source)
                forecasts.append(asdict(forecast))
            states.append(_state(controller))
            trace.append(dict(step=t, exogenous=schedule[t], sensor=sensor,
                              action=action, action_source=source, phase=result.phase,
                              incident=result.incident, history_before=history_before,
                              history_after=len(controller.core.filter.actions),
                              gain_before_observation=gain_before, estimated_gain=gain,
                              estimated_velocity=estimated_velocity,
                              predicted_velocity=prediction, true_gain=plant_gain,
                              true_position=position, true_velocity=velocity,
                              goal_error=abs(position - TARGET),
                              prediction_error=abs(prediction - velocity),
                              violation=abs(position) > 6 or abs(velocity) > 2,
                              learning_updates=fitted))
    row = dict(seed=seed, scenario=scenario, adaptive=adaptive, steps=STEPS,
               schedule_sha256=_digest(schedule), trace=trace, recovery_events=events,
               metrics=_metrics(trace, events), learning_updates=updates,
               initial_gain=INITIAL_GAIN, final_gain=trace[-1]['estimated_gain'],
               promoted=False, model_weights_trained=False)
    validate(row, seed, scenario, adaptive)
    return {'episode':row,'forecasts':forecasts,'controller_states':states,'enabled':enabled}



def run_demo():
    rows = []
    for scenario in ('stationary','drift'):
        for adaptive in (False,True):
            original = baseline.episode(9,scenario,adaptive)
            disabled = online_episode(9,scenario,adaptive,enabled=False)
            enabled = online_episode(9,scenario,adaptive,enabled=True)
            if not baseline._same(original,disabled['episode']):
                raise ValueError('development_driver_diverged_from_original')
            if not baseline._same(disabled['episode'],enabled['episode']):
                raise ValueError('forecast_changed_control_trajectory')
            if not baseline._same(disabled['controller_states'],enabled['controller_states']):
                raise ValueError('forecast_changed_controller_state')
            expected = replay.replay(replay.project(original['trace']))
            if not baseline._same(expected,enabled['forecasts']):
                raise ValueError('online_replay_forecast_mismatch')
            rows.append({'seed':9,'scenario':scenario,'adaptive':adaptive,
                'online':enabled,'original_trajectory_sha256':_digest(original),
                'trajectory_unchanged':True,'controller_states_unchanged':True,
                'online_matches_replay':True,
                'metrics':replay.score(original['trace'],enabled['forecasts'])})
    return {'protocol':'online-forecast-development-demo-v1','status':'complete',
        'rows':rows,'online_episodes':4,'comparison_episodes':8,
        'plant_steps':12*STEPS,'performance_improvement_claimed':False,
        'candidate_promoted':False,'model_weights_trained':False,'deployed':False,
        'scope':'Development seed 9 only; online wiring and noninterference proof, not independent performance evidence.'}
