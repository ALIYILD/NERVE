"""Training-only stale-gain diagnosis; associations do not establish causation."""
from hashlib import sha256
import json
from pathlib import Path
from . import evidence_gated_study as study

ARMS = study.ARMS[4:]
INTERVALS = ((50,60),(60,80))


def _mean(values):
    return sum(values)/len(values) if values else None


def _json(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def analyze(report):
    if type(report) is not dict or report.get('status') != 'complete' or type(report.get('rows')) is not list:
        raise ValueError('completed_gated_study_required')
    if len(report['rows']) > 320: raise ValueError('oversized_study')
    expected = {(seed,scenario,arm) for seed in study.SPLITS['train'] for scenario in study.SCENARIOS for arm in study.ARMS}
    training = {}
    for row in report['rows']:
        if type(row) is not dict or row.get('split') not in study.SPLITS:
            raise ValueError('invalid_split')
        if row['split'] != 'train': continue
        clean = dict(row); clean.pop('split')
        ep = clean['episode']; identity = (ep['seed'],ep['scenario'],clean['arm'])
        if identity not in expected or identity in training: raise ValueError('invalid_training_roster')
        study.worker.validate(clean,*identity)
        training[identity] = clean
    if set(training) != expected: raise ValueError('incomplete_training_roster')
    intervals = []; recoveries = []; groups = []
    for scenario in study.SCENARIOS:
        for arm in ARMS:
            control = 'frozen_'+arm[-2:]
            subset = [training[seed,scenario,arm] for seed in study.SPLITS['train']]
            for low,high in INTERVALS:
                pairs = [(r['episode']['trace'][t],training[r['episode']['seed'],scenario,control]['episode']['trace'][t])
                         for r in subset for t in range(low,high)]
                intervals.append({'scenario':scenario,'arm':arm,'control':control,
                    'start_step':low,'end_step_exclusive':high,'steps':len(pairs),
                    'controller_steps':sum(a['action_source']=='controller' for a,b in pairs),
                    'informative_updates':sum(a['learning_updates'] for a,b in pairs),
                    'mean_estimated_gain':_mean([a['estimated_gain'] for a,b in pairs]),
                    'mean_goal_error':_mean([a['goal_error'] for a,b in pairs]),
                    'control_mean_goal_error':_mean([b['goal_error'] for a,b in pairs]),
                    'paired_goal_delta':_mean([a['goal_error']-b['goal_error'] for a,b in pairs])})
            grouped = {False:[],True:[]}; episodes = {False:0,True:0}
            for row in subset:
                ep = row['episode']; trace = ep['trace']; seed = ep['seed']
                events = [event for event in ep['recovery_events'] if event['authorised']]
                if len(events) != 1: raise ValueError('one_authorized_recovery_required')
                event = events[0]; step = event['step']
                changes = [t for t in range(1,step+1) if trace[t]['estimated_gain'] != trace[t-1]['estimated_gain']]
                updates = [t for t in range(step+1) if trace[t]['learning_updates'] > 0]
                elevated = event['gain_after'] > ep['initial_gain']
                baseline = training[seed,scenario,control]['episode']['trace']
                indices = [t for t in range(step,len(trace)) if trace[t]['action_source']=='controller']
                deltas = [trace[t]['goal_error']-baseline[t]['goal_error'] for t in indices]
                grouped[elevated].extend(deltas); episodes[elevated] += 1
                recoveries.append({'seed':seed,'scenario':scenario,'arm':arm,'recovery_step':step,
                    'gain_at_recovery':event['gain_after'],'nominal_gain':ep['initial_gain'],
                    'elevated_gain':elevated,'last_gain_change_age':step-changes[-1] if changes else None,
                    'last_informative_update_age':step-updates[-1] if updates else None,
                    'post_recovery_controller_steps':len(deltas),'paired_goal_delta':_mean(deltas),
                    'recorded_recovery_window':row['learning_evidence'][step]['samples']})
            for elevated,values in grouped.items():
                groups.append({'scenario':scenario,'arm':arm,'elevated_gain':elevated,
                    'episodes':episodes[elevated],'controller_steps':len(values),
                    'paired_goal_delta':_mean(values)})
    return {'protocol':'recovery-gain-training-diagnostic-v1','status':'complete',
        'training_episodes':len(training),'intervals':intervals,'recoveries':recoveries,'groups':groups,
        'new_episodes':0,'heldout_outcomes_analyzed':False,'candidate_improvement_claimed':False,
        'candidate_promoted':False,'model_weights_trained':False,
        'scope':'Training-only descriptive associations, not causal evidence. Global trace indices determine ages; recovery-window sample timestamps are not treated as global time. Elevated means greater than configured nominal gain; other group means not elevated.',
        'next_action':'register_recovery_epoch_gain_candidate_with_mismatched_nominal_controls'}


def _sources():
    names = tuple(dict.fromkeys(study.SOURCES + (
        'src/nerve_awim/memory_gateway/recovery_gain_diagnostic.py',
        'scripts/diagnose_recovery_gain.py')))
    return {name:sha256((study.recovery.ROOT/name).read_bytes()).hexdigest() for name in names}


def run(directory,claims,coordinator_directory,coordinator_journal):
    path = Path(directory)/'report.json'; before = path.read_bytes(); pins = _sources()
    study.validate_receipt(directory,claims,coordinator_directory,coordinator_journal)
    if path.read_bytes() != before: raise ValueError('study_changed_during_validation')
    result = analyze(json.loads(before))
    if path.read_bytes() != before or _sources() != pins: raise ValueError('diagnostic_source_changed')
    result['source_receipt_sha256'] = sha256(before).hexdigest(); result['source_sha256'] = pins
    return result
