"""Apache-2.0. Bounded observational learning from externally judged outcomes.

The host owns authorization, labels, scope and persistence. Replaying its unique
chronological events reconstructs the learned state without counting observations
twice. Forecasts are scored BEFORE seeing each outcome. No action or release API.
"""
from collections import deque
from hashlib import sha256
import json
import math

REVISION = 'nerve-outcome-forecast-v1'


def forecast_outcomes(events, *, window=20, warmup=20):
    """Learn rolling Beta(1,1) outcome frequencies; compare frozen and growing controls.

    Events: {id: opaque str, observed_at: finite timestamp, success: bool | None}.
    Inputs must represent ONE exact authorized task/model/domain scope. None is
    missing feedback, never success. Rates are heuristic, not calibrated safety
    probabilities. The bounded retained history is the source of truth.
    """
    if type(window) is not int or not 2 <= window <= 200:
        raise ValueError('window must be between 2 and 200')
    if type(warmup) is not int or not 2 <= warmup <= 200:
        raise ValueError('warmup must be between 2 and 200')
    if type(events) is not list or len(events) > 2000:
        raise ValueError('at most 2000 observations per scope')
    unique = {}
    for event in events:
        if type(event) is not dict or set(event) != {'id', 'observed_at', 'success'}:
            raise ValueError('exact observation contract required')
        ident, stamp, success = event['id'], event['observed_at'], event['success']
        if (type(ident) is not str or not 1 <= len(ident) <= 128 or
                type(stamp) not in (int, float) or not math.isfinite(stamp) or
                (success is not None and type(success) is not bool)):
            raise ValueError('invalid observation')
        if ident in unique and unique[ident] != event:
            raise ValueError('conflicting duplicate observation')
        unique[ident] = dict(event)
    ordered = sorted(unique.values(), key=lambda e: (e['observed_at'], e['id']))
    recent = deque(maxlen=window)
    count = successes = missing = scored = 0
    frozen = None
    losses = {'adaptive': 0., 'frozen': 0., 'expanding': 0., 'neutral': 0.}
    predictions = []
    # Equal timestamps are a batch: no outcome in a batch predicts a peer.
    from itertools import groupby
    for _, batch in groupby(ordered, key=lambda e: e['observed_at']):
        batch = list(batch)
        rates = {'adaptive': (1 + sum(recent)) / (2 + len(recent)),
                 'expanding': (1 + successes) / (2 + count),
                 'frozen': frozen, 'neutral': .5}
        for event in batch:
            value = event['success']
            if value is None:
                missing += 1
                continue
            if frozen is not None:
                scored += 1
                for arm in losses:
                    losses[arm] += (rates[arm] - int(value)) ** 2
                predictions.append({'adaptive': rates['adaptive'], 'frozen': frozen,
                                    'expanding': rates['expanding'], 'actual': int(value)})
        for event in batch:
            if event['success'] is not None:
                count += 1
                successes += int(event['success'])
                recent.append(int(event['success']))
        if frozen is None and count >= warmup:
            frozen = (1 + successes) / (2 + count)
    metrics = {arm: loss / scored if scored else None for arm, loss in losses.items()}
    return {'revision': REVISION, 'observations': count, 'missing': missing,
            'duplicates_ignored': len(events) - len(unique), 'scored': scored,
            'window': window, 'warmup': warmup,
            'next_success_estimate': (1 + sum(recent)) / (2 + len(recent)),
            'state_digest': sha256(json.dumps(ordered, sort_keys=True, allow_nan=False).encode()).hexdigest(),
            'brier': metrics, 'predictions': predictions,
            'automatic_action_authorized': False,
            'limitation': 'Observational prediction only. Descriptive temporal scores, not causal or clinical efficacy evidence.'}


def summarize_outcomes(events, **kwargs):
    """Metadata-only host view: no event IDs, bodies or individual labels returned."""
    result = forecast_outcomes(events, **kwargs)
    result.pop('predictions')
    return result
