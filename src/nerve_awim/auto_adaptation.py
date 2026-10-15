"""Bounded sandbox adaptation state machine; trusted host execution and labels.

Pure JSON transitions are persisted by the goal supervisor. No model-generated
code, external calls, clinical policy changes, or production release authority.
"""
from copy import deepcopy
import json

from .outcome_forecast import summarize_outcomes


def initial_state(scope, strategies):
    if type(scope) is not str or not 1 <= len(scope) <= 128:
        raise ValueError('explicit bounded scope required')
    if type(strategies) is not list or not 2 <= len(strategies) <= 8 or any(type(s) is not str or not 1 <= len(s) <= 128 for s in strategies) or len(set(strategies)) != len(strategies):
        raise ValueError('distinct registered strategy names required')
    return dict(schema='auto-adaptation-v1', scope=scope, strategies=strategies[:],
                active=strategies[0], previous=None, version=0, events=[],
                baseline=None, cooldown=0, canary_remaining=0, canary_failures=0,
                switches=0, rollbacks=0, killed=False, production_authorized=False)


def observe(state, event):
    """Accept fresh chronological feedback for the exact policy that executed.

    Identical retries are idempotent. Missing labels never count as successes.
    A label is a trusted host judgment, not the agent's own success assertion.
    """
    required = {'id', 'observed_at', 'success', 'scope', 'strategy', 'version'}
    if type(event) is not dict or set(event) != required:
        raise ValueError('exact observation schema required')
    result = deepcopy(state)
    if result['killed']:
        raise PermissionError('adaptation stopped')
    for old in result['events']:
        if old['id'] == event['id']:
            if old != event:
                raise ValueError('conflicting feedback retry')
            return result
    if event['scope'] != state['scope'] or event['strategy'] != state['active'] or type(event['version']) is not int or event['version'] != state['version']:
        raise ValueError('feedback scope or executed policy mismatch')
    values = [{k: e[k] for k in ('id', 'observed_at', 'success')} for e in result['events'] + [event]]
    # Reuse the existing outcome learner's type/size checks, but require host
    # ingestion order too; retroactive labels cannot change earlier switches.
    summarize_outcomes(values, window=4, warmup=4)
    if result['events'] and event['observed_at'] <= result['events'][-1]['observed_at']:
        raise ValueError('strictly chronological feedback required')
    result['events'].append(deepcopy(event))
    if event['success'] is not None:
        result['cooldown'] = max(0, result['cooldown'] - 1)
        known = [e['success'] for e in result['events'] if e['success'] is not None]
        if result['baseline'] is None and len(known) >= 4:
            result['baseline'] = sum(known[:4]) / 4
        if result['canary_remaining']:
            result['canary_remaining'] -= 1
            result['canary_failures'] += int(not event['success'])
            if result['canary_failures'] >= 2:
                result['active'] = result['previous']
                result['version'] += 1
                result['rollbacks'] += 1
                result['canary_remaining'] = 0
                result['cooldown'] = 8
    return result


def detect(state):
    events = [{k: e[k] for k in ('id', 'observed_at', 'success')} for e in state['events']]
    forecast = summarize_outcomes(events, window=4, warmup=4)
    current = [e['success'] for e in state['events'] if e['version'] == state['version'] and e['success'] is not None][-4:]
    eligible = (not state['killed'] and state['baseline'] is not None
                and state['baseline'] >= .75 and len(current) == 4
                and not state['cooldown'] and not state['canary_remaining']
                and state['switches'] < 4)
    return {'triggered': bool(eligible and sum(current) <= 1),
            'current_successes': sum(current), 'current_observations': len(current),
            'forecast': forecast, 'policy_version': state['version']}


def evaluate(state, tasks, retained, *, execute, judge):
    """Selection on new tasks; canary outcomes remain withheld until switching.

    Each task is {task: JSON, expected: JSON}. Predictors receive task only;
    trusted independent judge receives the expected result. The reference and
    all alternatives have identical tasks and call budgets.
    """
    if not detect(state)['triggered']:
        return {'eligible': False, 'reason': 'no_change_trigger', 'version': state['version']}
    if not 4 <= len(tasks) <= 20 or not 4 <= len(retained) <= 20:
        raise ValueError('bounded selection and retained tasks required')
    payloads = [json.dumps(e['task'], sort_keys=True, allow_nan=False) for e in tasks + retained]
    if len(set(payloads)) != len(payloads) or any(len(p.encode()) > 16384 for p in payloads):
        raise ValueError('distinct bounded selection and retained tasks required')
    scores = {}
    for strategy in state['strategies']:
        outcomes = []
        for episode in tasks + retained:
            output = execute(deepcopy(episode['task']), strategy)
            success = judge(deepcopy(episode['task']), output, deepcopy(episode['expected']))
            if type(success) is not bool:
                raise ValueError('independent boolean judgment required')
            outcomes.append(success)
        scores[strategy] = outcomes
    baseline = scores[state['active']]
    candidates = [s for s, outcomes in scores.items() if sum(outcomes[:len(tasks)]) > sum(baseline[:len(tasks)])
                  and not any(a and not b for a, b in zip(baseline, outcomes))]
    candidate = max(candidates, key=lambda s: sum(scores[s])) if candidates else None
    return {'eligible': candidate is not None, 'candidate': candidate, 'scope': state['scope'],
            'observation_digest': detect(state)['forecast']['state_digest'],
            'version': state['version'], 'incumbent': state['active'], 'scores': scores,
            'selection_count': len(tasks), 'retained_count': len(retained),
            'calls': len(scores) * (len(tasks) + len(retained))}


def switch(state, evaluation):
    result = deepcopy(state)
    if not evaluation.get('eligible'):
        return result
    if (not detect(state)['triggered'] or evaluation.get('scope') != state['scope']
            or evaluation.get('version') != state['version'] or evaluation.get('incumbent') != state['active']
            or evaluation.get('observation_digest') != detect(state)['forecast']['state_digest']
            or evaluation.get('candidate') not in state['strategies']):
        raise ValueError('stale or foreign evaluation')
    # Recheck measured evidence rather than trusting the eligibility flag.
    count = evaluation['selection_count']
    baseline = evaluation['scores'][state['active']]
    candidate = evaluation['scores'][evaluation['candidate']]
    if (len(candidate) != count + evaluation['retained_count'] or len(baseline) != len(candidate)
            or any(type(v) is not bool for v in baseline + candidate)
            or sum(candidate[:count]) <= sum(baseline[:count])
            or any(a and not b for a, b in zip(baseline, candidate))):
        raise ValueError('improvement and no-regression evidence required')
    result.update(previous=state['active'], active=evaluation['candidate'],
                  version=state['version']+1, cooldown=8, canary_remaining=8, canary_failures=0,
                  switches=state['switches']+1)
    return result


def stop(state):
    result = deepcopy(state)
    result['killed'] = True
    return result
