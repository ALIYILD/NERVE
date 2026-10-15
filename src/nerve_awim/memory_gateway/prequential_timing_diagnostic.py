"""Read-only timing diagnosis of verified fixed development selector traces."""
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path

from . import prequential_gain_demo as demo

MAX_COMPRESSED = 4*1024*1024
MAX_EXPANDED = 24*1024*1024


def sources():
    pins = demo.sources()
    name = 'src/nerve_awim/memory_gateway/prequential_timing_diagnostic.py'
    pins[name] = sha256((demo.standard.ROOT/name).read_bytes()).hexdigest()
    return pins


def _require(value):
    if not value: raise ValueError('invalid_prequential_timing_evidence')


def _unique(pairs):
    result = {}
    for key,value in pairs:
        if key in result: raise ValueError('duplicate_json_key')
        result[key] = value
    return result


def _constant(value): raise ValueError('nonfinite_json_number')


def _read(path):
    with Path(path).open('rb') as stream: raw = stream.read(MAX_COMPRESSED+1)
    _require(len(raw) <= MAX_COMPRESSED)
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream: expanded = stream.read(MAX_EXPANDED+1)
    _require(len(expanded) <= MAX_EXPANDED)
    return raw,json.loads(expanded,object_pairs_hook=_unique,parse_constant=_constant)


def validate(report):
    keys = {'protocol','status','rows','episodes','plant_steps','screen','source_sha256',
            'registered_streams_used','heldout_outcomes_analyzed','performance_improvement_claimed',
            'candidate_promoted','model_weights_trained','recommendation'}
    _require(type(report) is dict and set(report) == keys)
    _require(report['protocol'] == 'prequential-gain-development-v1' and report['status'] == 'complete')
    _require(type(report['episodes']) is int and report['episodes'] == 12)
    _require(type(report['plant_steps']) is int and report['plant_steps'] == 960)
    for key in ('registered_streams_used','heldout_outcomes_analyzed','performance_improvement_claimed',
                'candidate_promoted','model_weights_trained'): _require(report[key] is False)
    pins = demo.sources()
    _require(len(pins) == 24 and report['source_sha256'] == pins)
    rows = report['rows']
    _require(type(rows) is list and len(rows) == 12)
    for row,(plant,arm) in zip(rows,[(p,a) for p in demo.PLANTS for a in demo.ARMS]):
        demo.validate(row,arm,plant)
    screen = demo.compare(rows)
    _require(demo._same(report['screen'],screen))
    _require(report['recommendation'] == ('register_fresh_study' if screen['passed'] else 'retain_baselines_and_diagnose'))


def load_verified(path):
    pins = sources(); before,report = _read(path)
    validate(report)
    after,_ = _read(path)
    if before != after: raise ValueError('timing_source_artifact_changed')
    if pins != sources(): raise ValueError('timing_source_code_changed')
    return {'report':report,'source_artifact_sha256':sha256(before).hexdigest(),'source_sha256':pins}


def _summary(steps):
    counts = {'steps':len(steps)}
    for key in ('eligible','eligible_controller_command','eligible_nonzero_command','eligible_external_step',
                'controller_zero_action','external_zero_action','missing_velocity','rejected_sensor'):
        counts[key] = sum(item[key] for item in steps)
    counts['window_reasons'] = {reason:sum(item['reason'] == reason for item in steps)
                               for reason in ('insufficient_four','mixed_or_tied_window','eligible')}
    counts['resolved_outcomes'] = {outcome:sum(score['outcome'] == outcome for item in steps for score in item['new_scores'])
                                   for outcome in ('win','tie','loss')}
    return counts


def analyze(report):
    """Caller must validate receipt first; this function only reads snapshots."""
    cases = []
    for row in report['rows']:
        if row['arm'] != 'selector': continue
        recoveries = [event['step'] for event in row['recovery_events'] if event['authorised']]
        seen, steps, switches, intervals = set(), [], [], []
        previous_mode, interval_start, first_full = 'nominal', None, None
        for item in row['trace']:
            index = item['step']; snapshot = item['selector_before']; scores = snapshot['scores']
            if len(scores) == 4 and first_full is None: first_full = index
            eligible = snapshot['mode'] == 'learned'
            reason = ('eligible' if eligible else 'insufficient_four' if len(scores) < 4 else 'mixed_or_tied_window')
            if snapshot['mode'] != previous_mode:
                preceding = [step for step in recoveries if step <= index]
                following = [step for step in recoveries if step > index]
                switches.append({'step':index,'from':previous_mode,'to':snapshot['mode'],
                    'steps_since_authorized_recovery':index-preceding[-1] if preceding else None,
                    'steps_until_next_authorized_recovery':following[0]-index if following else None})
                previous_mode = snapshot['mode']
            if eligible and interval_start is None: interval_start = index
            if not eligible and interval_start is not None:
                intervals.append({'start':interval_start,'end_exclusive':index}); interval_start = None
            new_scores = []
            for score in scores:
                if score['timestamp'] in seen: continue
                seen.add(score['timestamp'])
                delta = score['learned_error']-score['nominal_error']
                new_scores.append({'forecast_step':score['timestamp'],'resolved_step':index,
                    'delay_steps':index-score['timestamp'],'outcome':'win' if delta < 0 else 'loss' if delta > 0 else 'tie',
                    'learned_error':score['learned_error'],'nominal_error':score['nominal_error']})
            sensor = item['sensor']; controller = item['action_source'] == 'controller'
            steps.append({'step':index,'retrospective_phase':index//20,'eligible':eligible,
                'eligible_controller_command':eligible and controller,
                'eligible_nonzero_command':eligible and controller and item['action'] != 0,
                'eligible_external_step':eligible and not controller,
                'controller_zero_action':controller and item['action'] == 0,
                'external_zero_action':not controller and item['action'] == 0,
                'missing_velocity':sensor is None or sensor.get('velocity') is None,
                'rejected_sensor':sensor is not None and not sensor['accepted'],
                'reason':reason,'window_size':len(scores),'new_scores':new_scores})
        if interval_start is not None: intervals.append({'start':interval_start,'end_exclusive':80})
        _require(len(seen) == row['trace'][-1]['selector_after']['counts']['resolved'])
        cases.append({'plant':row['plant'],'arm':'selector','first_full_window_step':first_full,
            'authorized_recovery_steps':recoveries,'eligibility_intervals':intervals,'switches':switches,
            'summary':_summary(steps),'phases':[dict(phase=phase,start=20*phase,end_exclusive=20*(phase+1),
                **_summary([item for item in steps if item['retrospective_phase'] == phase])) for phase in range(4)],
            'steps':steps})
    return {'protocol':'prequential-timing-diagnostic-v1','status':'diagnostic_complete',
        'cases':cases,'verified_source_episodes':12,'selector_episodes_analyzed':4,
        'recommendation':'review_evidence_timing_before_registering_new_hypothesis',
        'next_action':'review_evidence_timing_and_register_new_hypothesis',
        'new_episodes':0,'heldout_outcomes_analyzed':False,'promotion_authorized':False,
        'goal_achieved':False,'model_weights_trained':False,
        'scope':'Recorded seed-9 development evidence only. Twenty-step phases are retrospective labels, never selector inputs. Zero actions provide no gain discrimination. Eligibility is distinct from controller commands and nonzero actions. No threshold tuning or population performance claim.'}


def run(path):
    verified = load_verified(path)
    result = analyze(verified['report'])
    after,_ = _read(path)
    if sha256(after).hexdigest() != verified['source_artifact_sha256']: raise ValueError('timing_source_artifact_changed')
    if sources() != verified['source_sha256']: raise ValueError('timing_source_code_changed')
    result.update({key:verified[key] for key in ('source_artifact_sha256','source_sha256')})
    return result
