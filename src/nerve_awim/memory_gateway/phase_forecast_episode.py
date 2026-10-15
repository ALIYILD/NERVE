"""Prediction-only routing on matched controller trajectories.

The forecaster sees only recorded observations, actions, and model estimates.
True outcomes enter only scoring after the entire forecast sequence is produced.
No router output feeds back into the original controller or its learning process.
"""
from dataclasses import asdict
import json
import math
from time import perf_counter

from ..phase_forecast import PhaseAwareForecaster
from . import evidence_gated_episode as control
from .observer_reanalysis import _ResearchReporter

ARMS = control.ARMS
STEPS = control.episode.STEPS


def project(trace):
    return [{'step': row['step'], 'action': row['action'],
             'gain': row['estimated_gain'], 'source': row['action_source'],
             'controller_velocity': (row['predicted_velocity']
                                     if row['action_source'] == 'controller' else None),
             'sensor': ({key: row['sensor'][key]
                         for key in ('timestamp', 'position', 'velocity')}
                        if row['sensor'] is not None and row['sensor']['accepted'] else None)}
            for row in trace]


def replay(inputs):
    if type(inputs) is not list or len(inputs) != STEPS:
        raise ValueError('bounded_forecast_roster_required')
    router = PhaseAwareForecaster(verifier=_ResearchReporter(), issuer='synthetic',
        audience='observer-reanalysis', subjects=frozenset({'trace-reporter'}),
        max_history=STEPS)
    forecasts = []
    for index, item in enumerate(inputs):
        if (type(item) is not dict or set(item) != {
                'step', 'action', 'gain', 'source', 'controller_velocity', 'sensor'}
                or type(item['step']) is not int or item['step'] != index):
            raise ValueError('invalid_forecast_projection')
        sensor = item['sensor']
        if sensor is not None:
            if type(sensor) is not dict or set(sensor) != {'timestamp', 'position', 'velocity'}:
                raise ValueError('invalid_sensor_projection')
            router.observe('verified-trace', now=index, step=sensor['timestamp'],
                           position=sensor['position'], velocity=sensor['velocity'])
        forecasts.append(asdict(router.record_action('verified-trace', now=index,
            step=index, action=item['action'], gain=item['gain'], source=item['source'],
            controller_velocity=item['controller_velocity'])))
    return forecasts


def score(trace, forecasts):
    if len(trace) != STEPS or len(forecasts) != STEPS:
        raise ValueError('incomplete_forecast_scores')
    missing = sum(forecast['velocity'] is None for forecast in forecasts)
    return {
        'legacy_mae': sum(step['prediction_error'] for step in trace)/STEPS,
        'routed_mae': (None if missing else sum(
            abs(forecast['velocity']-step['true_velocity'])
            for step, forecast in zip(trace, forecasts))/STEPS),
        'controller_predictions_preserved': all(
            forecast['velocity'] == step['predicted_velocity']
            for step, forecast in zip(trace, forecasts)
            if step['action_source'] == 'controller'),
        'actions_changed': False,
        'missing_forecasts': missing,
    }


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def execute(seed, scenario, arm):
    start = perf_counter()
    original = control.execute(seed, scenario, arm)
    forecasts = replay(project(original['episode']['trace']))
    result = {'control': original, 'forecasts': forecasts,
              'metrics': score(original['episode']['trace'], forecasts),
              'elapsed_seconds': perf_counter()-start}
    validate(result, seed, scenario, arm)
    return result


def validate(row, seed, scenario, arm):
    if type(row) is not dict or set(row) != {'control', 'forecasts', 'metrics', 'elapsed_seconds'}:
        raise ValueError('invalid_phase_forecast_episode')
    elapsed = row['elapsed_seconds']
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('invalid_elapsed_time')
    control.validate(row['control'], seed, scenario, arm)
    trace = row['control']['episode']['trace']
    forecasts = replay(project(trace))
    if type(row['forecasts']) is not list or _canonical(row['forecasts']) != _canonical(forecasts):
        raise ValueError('routed_forecast_mismatch')
    metrics = score(trace, forecasts)
    if type(row['metrics']) is not dict or _canonical(row['metrics']) != _canonical(metrics):
        raise ValueError('forecast_metrics_mismatch')
