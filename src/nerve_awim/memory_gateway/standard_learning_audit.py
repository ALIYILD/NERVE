"""Independent sensor/action reconstruction of standard EMA applications.

This audit does not call the estimator under test or read physical truth. The
original episode validator must separately verify physical traces and provenance.
Legacy ``learning_updates`` is intentionally ignored: its optional-model counter
does not count standard-branch EMA applications. An authorized recovery flag is
an input receipt assertion, not a new authentication or approval mechanism.
"""
from math import isfinite

STEPS = 80
INITIAL_GAIN = .27
RETENTION = .82
MAX_PROCESSED = 4096
ARMS = ('frozen', 'legacy', 'single_use')


def _require(condition):
    if not condition:
        raise ValueError('invalid_standard_learning_evidence')


def _number(value):
    _require(type(value) in (int, float) and isfinite(value))
    return value


def audit(row, arm):
    """Audit one fixed 80-step recovery episode without rerunning the plant."""
    _require(type(arm) is str and arm in ARMS)
    try:
        _require(type(row) is dict and type(row['steps']) is int and row['steps'] == STEPS)
        _require(_number(row['initial_gain']) == INITIAL_GAIN)
        trace, event_rows = row['trace'], row['recovery_events']
        _require(type(trace) is list and len(trace) == STEPS)
        _require(type(event_rows) is list and len(event_rows) <= STEPS)
        events, last_event = {}, -1
        for event in event_rows:
            _require(type(event) is dict and type(event['step']) is int
                     and 0 < event['step'] < STEPS and event['step'] > last_event
                     and type(event['authorised']) is bool)
            _number(event['gain_before']); _number(event['gain_after'])
            last_event = event['step']
            events[last_event] = event
        rate = 0. if arm == 'frozen' else .08
        gain, origin, epochs = INITIAL_GAIN, 0, 1
        actions, readings, processed, unique = [], {}, set(), set()
        steps, total = [], 0
        for index, item in enumerate(trace):
            _require(type(item) is dict and type(item['step']) is int and item['step'] == index)
            _require(_number(item['gain_before_observation']) == gain)
            before, applications, fresh = gain, [], 0
            sensor = item['sensor']
            if sensor is not None:
                _require(type(sensor) is dict and type(sensor['timestamp']) is int
                         and 0 <= sensor['timestamp'] < index
                         and sensor['route'] in ('active', 'recovery')
                         and type(sensor['accepted']) is bool)
                velocity = _number(sensor['velocity'])
                if sensor['route'] == 'active' and sensor['accepted']:
                    local = sensor['timestamp']-origin
                    _require(0 <= local < len(actions))
                    readings[local] = velocity
                    # Original fitting order: all local transitions in ascending
                    # action index on each accepted active observation.
                    for transition in range(1, len(actions)):
                        if transition-1 not in readings or transition not in readings or actions[transition] == 0:
                            continue
                        sample = (readings[transition]-RETENTION*readings[transition-1])/actions[transition]
                        if not isfinite(sample) or abs(sample) > 2 or rate == 0:
                            continue
                        if arm == 'single_use' and (transition in processed or len(processed) >= MAX_PROCESSED):
                            continue
                        old_gain = gain
                        gain = max(.01, min(1., (1-rate)*gain+rate*sample))
                        identity = (origin, transition)
                        fresh += int(identity not in unique)
                        unique.add(identity)
                        processed.add(transition)
                        applications.append({'transition': transition,
                            'global_transition': origin+transition, 'sample': sample,
                            'gain_before': old_gain, 'gain_after': gain})
            if index in events:
                event = events[index]
                _require(sensor is not None and sensor['route'] == 'recovery'
                         and sensor['accepted'] is True)
                _require(event['gain_before'] == gain and event['gain_after'] == gain)
                if event['authorised']:
                    next_origin = sensor['timestamp']+1
                    _require(next_origin > origin)
                    origin = next_origin
                    actions, readings, processed = [], {}, set()
                    epochs += 1
            _require(_number(item['estimated_gain']) == gain)
            _require(type(item['history_before']) is int and item['history_before'] == len(actions))
            _require(type(item['action']) is int and item['action'] in (-1, 0, 1)
                     and item['action_source'] in ('controller', 'external_supervisor'))
            if item['action_source'] == 'controller':
                actions.append(item['action'])
            else:
                _require(item['action'] == 0)
            _require(type(item['history_after']) is int and item['history_after'] == len(actions))
            total += len(applications)
            steps.append({'step': index, 'epoch_origin': origin,
                'gain_before': before, 'gain_after': gain,
                'ema_applications': len(applications), 'unique_transitions': fresh,
                'applications': applications})
        _require(_number(row['final_gain']) == gain)
        return {'arm': arm, 'learning_rate': rate, 'ema_applications': total,
                'unique_transitions': len(unique), 'repeated_applications': total-len(unique),
                'epochs': epochs, 'final_gain': gain, 'steps': steps}
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError('invalid_standard_learning_evidence') from exc
