"""Paired synthetic observation-recovery study; no hardware or LLM training.

A fixed host supervisor applies zero input whenever the controller abstains.
That command is explicitly simulated and scored, and is not presumed safe.
Only noisy observations enter the controller. Ground truth stays in scoring.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import secrets
import tempfile
from pathlib import Path

from nerve_awim.identity_v26 import VerifiedIdentity
from nerve_awim.recovery_v25 import sign_approval
from nerve_awim.runtime_v28 import NerveResearchRuntime

STEPS = 80
RETENTION = .82
TARGET = 1.2
INITIAL_GAIN = .27
ISSUER = 'synthetic://recovery-study'
AUDIENCE = 'synthetic-research'


class SyntheticVerifier:
    """Explicit test identity adapter; not network authentication."""

    def verify(self, token, now):
        if token != 'synthetic-host-approval':
            return None
        return VerifiedIdentity('synthetic-supervisor', ISSUER, AUDIENCE,
                                frozenset({'recovery-supervisor'}), now + 1)


def _inputs(seed, scenario, adaptive):
    if (type(seed) is not int or not 0 <= seed < 2**63
            or type(scenario) is not str or scenario not in ('stationary', 'drift')
            or type(adaptive) is not bool):
        raise ValueError('invalid recovery study inputs')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _schedule(seed):
    rng = random.Random(seed)
    result = []
    for t in range(STEPS):
        # Consume the same draws regardless of blackout and controller actions.
        random_drop = rng.random() < .12
        result.append(dict(origin=t, dropped=35 <= t < 50 or random_drop,
                           position_noise=rng.gauss(0, .03),
                           velocity_noise=rng.gauss(0, .025)))
    return result


def episode(seed: int, scenario: str, adaptive: bool) -> dict:
    _inputs(seed, scenario, adaptive)
    schedule = _schedule(seed)
    trace, events = [], []
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
    return row


def _metrics(trace, events):
    active = sum(r['action_source'] == 'controller' for r in trace)
    return dict(active_steps=active, supervisor_steps=STEPS-active,
                violations=sum(r['violation'] for r in trace),
                mean_goal_error=sum(r['goal_error'] for r in trace) / STEPS,
                mean_prediction_error=sum(r['prediction_error'] for r in trace) / STEPS,
                successful_recoveries=sum(r['authorised'] for r in events))


def _same(actual, expected):
    # JSON canonicalization preserves bool/int distinctions and rejects NaN.
    return json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(
        expected, sort_keys=True, allow_nan=False)


def _require(condition):
    if not condition:
        raise ValueError("invalid recovery episode evidence")


def validate(row, seed, scenario, adaptive):
    """Validate trace arithmetic and provenance; not remote execution attestation."""
    _inputs(seed, scenario, adaptive)
    keys = {'seed', 'scenario', 'adaptive', 'steps', 'schedule_sha256', 'trace',
            'recovery_events', 'metrics', 'learning_updates', 'initial_gain',
            'final_gain', 'promoted', 'model_weights_trained'}
    trace_keys = {'step', 'exogenous', 'sensor', 'action', 'action_source', 'phase',
                  'incident', 'history_before', 'history_after',
                  'gain_before_observation', 'estimated_gain', 'estimated_velocity',
                  'predicted_velocity', 'true_gain', 'true_position', 'true_velocity',
                  'goal_error', 'prediction_error', 'violation', 'learning_updates'}
    try:
        _require(type(row) is dict and set(row) == keys)
        for key, value in dict(seed=seed, scenario=scenario, adaptive=adaptive,
                               steps=STEPS, initial_gain=INITIAL_GAIN,
                               promoted=False, model_weights_trained=False).items():
            _require(_same(row[key], value))
        schedule = _schedule(seed)
        _require(row['schedule_sha256'] == _digest(schedule))
        trace = row['trace']
        events = row['recovery_events']
        _require(type(trace) is list and len(trace) == STEPS and type(events) is list)
        event_steps = set()
        last_event_step = -1
        for event in events:
            _require(type(event) is dict and set(event) == {
                'step', 'incident', 'authorised', 'gain_before', 'gain_after'})
            _require(type(event['step']) is int and 0 < event['step'] < STEPS)
            _require(event['step'] not in event_steps and event['step'] > last_event_step)
            last_event_step = event['step']
            event_steps.add(event['step'])
            _require(type(event['incident']) is int and event['incident'] > 0)
            _require(type(event['authorised']) is bool)
            for key in ('gain_before', 'gain_after'):
                _require(type(event[key]) in (int, float) and math.isfinite(event[key]))
            _require(event['gain_before'] == event['gain_after'])
        position = velocity = 0.
        for t, item in enumerate(trace):
            _require(type(item) is dict and set(item) == trace_keys)
            _require(type(item['step']) is int and item['step'] == t)
            _require(_same(item['exogenous'], schedule[t]))
            _require(type(item['action']) is int and item['action'] in (-1, 0, 1))
            _require(item['action_source'] in ('controller', 'external_supervisor'))
            _require(item['phase'] in ('active', 'supervision_required', 'awaiting_approval'))
            for key in ('incident', 'history_before', 'history_after', 'learning_updates'):
                _require(type(item[key]) is int and item[key] >= 0)
            for key in ('gain_before_observation', 'estimated_gain', 'estimated_velocity',
                        'predicted_velocity', 'true_gain', 'true_position', 'true_velocity',
                        'goal_error', 'prediction_error'):
                _require(type(item[key]) in (int, float) and math.isfinite(item[key]))
            _require(.01 <= item['estimated_gain'] <= 1)
            _require(item['history_after'] == item['history_before'] + int(item['action_source'] == 'controller'))
            if item['action_source'] == 'external_supervisor':
                _require(item['action'] == 0 and item['phase'] != 'active')
            else:
                _require(item['phase'] == 'active')
            expected_sensor = None
            if t and not schedule[t - 1]['dropped']:
                expected_sensor = dict(timestamp=t-1,
                    position=position + schedule[t - 1]['position_noise'],
                    velocity=velocity + schedule[t - 1]['velocity_noise'])
                sensor = item['sensor']
                _require(type(sensor) is dict and set(sensor) == set(expected_sensor) | {'route', 'accepted'})
                for key, value in expected_sensor.items():
                    _require(_same(sensor[key], value))
                _require(sensor['route'] in ('active', 'recovery') and type(sensor['accepted']) is bool)
                _require(sensor['route'] == ('active' if trace[t - 1]['phase'] == 'active' else 'recovery'))
                if sensor['route'] == 'active':
                    _require(sensor['accepted'] is True)
            else:
                _require(item['sensor'] is None)
            recovered = False
            if t in event_steps:
                _require(expected_sensor is not None and item['sensor']['route'] == 'recovery')
                event = next(e for e in events if e['step'] == t)
                _require(event['gain_after'] == item['estimated_gain'])
                _require(event['incident'] == item['incident'])
                recovered = event['authorised']
                _require(item['sensor']['accepted'] is True)
                if event['authorised']:
                    _require(item['phase'] == 'active' and item['history_before'] == 0)
            _require(item['history_before'] == (0 if recovered or not t else trace[t - 1]['history_after']))
            if t and trace[t - 1]['phase'] != 'active' and item['phase'] == 'active':
                _require(recovered)
            _require(item['gain_before_observation'] == (trace[t - 1]['estimated_gain'] if t else INITIAL_GAIN))
            if not adaptive:
                _require(item['estimated_gain'] == INITIAL_GAIN and item['learning_updates'] == 0)
            if not expected_sensor or item['sensor']['route'] == 'recovery':
                _require(item['learning_updates'] == 0)
                _require(item['estimated_gain'] == item['gain_before_observation'])
            gain = INITIAL_GAIN if scenario == 'stationary' else (.27, .48, .15, .4)[t // 20]
            velocity = RETENTION * velocity + gain * item['action']
            position += velocity
            prediction = RETENTION * item['estimated_velocity'] + item['estimated_gain'] * item['action']
            for key, value in dict(true_gain=gain, true_velocity=velocity,
                                   true_position=position, predicted_velocity=prediction,
                                   goal_error=abs(position - TARGET),
                                   prediction_error=abs(prediction - velocity),
                                   violation=abs(position) > 6 or abs(velocity) > 2).items():
                _require(_same(item[key], value))
        _require(_same(row['metrics'], _metrics(trace, events)))
        _require(type(row['learning_updates']) is int)
        _require(row['learning_updates'] == sum(r['learning_updates'] for r in trace))
        _require(_same(row['final_gain'], trace[-1]['estimated_gain']))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError('invalid recovery episode evidence') from exc
    return None
