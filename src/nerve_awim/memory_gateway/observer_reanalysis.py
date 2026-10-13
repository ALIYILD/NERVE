"""Fixed training-only observational replay, never counterfactual control proof."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from ..actual_action_observer import ActualActionObserver
from ..identity_v26 import VerifiedIdentity
from . import evidence_gated_study as study


class _ResearchReporter:
    def verify(self, token, now):
        if token == 'verified-trace':
            return VerifiedIdentity('trace-reporter','synthetic','observer-reanalysis',
                                    frozenset({'actual-action-observer'}),now+1)


def project(trace):
    """Only historically available observation/action/model fields cross here."""
    return [{'step':row['step'],'action':row['action'],'gain':row['estimated_gain'],
             'sensor':({key:row['sensor'][key] for key in ('timestamp','position','velocity')}
                       if row['sensor'] is not None and row['sensor']['accepted'] else None)}
            for row in trace]


def replay(inputs):
    if type(inputs) is not list or len(inputs) != 80:
        raise ValueError('bounded_observation_roster_required')
    observer = ActualActionObserver(verifier=_ResearchReporter(),issuer='synthetic',
        audience='observer-reanalysis',subjects=frozenset({'trace-reporter'}),max_history=80)
    forecasts = []
    for index, item in enumerate(inputs):
        if (type(item) is not dict or set(item) != {'step','action','gain','sensor'}
                or type(item['step']) is not int or item['step'] != index):
            raise ValueError('invalid_observation_projection')
        sensor = item['sensor']
        if sensor is not None:
            if type(sensor) is not dict or set(sensor) != {'timestamp','position','velocity'}:
                raise ValueError('invalid_sensor_projection')
            observer.observe('verified-trace',now=index,step=sensor['timestamp'],
                             position=sensor['position'],velocity=sensor['velocity'])
        forecast = observer.record_action('verified-trace',now=index,step=index,
                                         action=item['action'],gain=item['gain'])
        if forecast.velocity is None:
            raise ValueError('unexpected_unknown_forecast')
        forecasts.append(asdict(forecast))
    return forecasts


def analyze(report):
    if type(report) is not dict or report.get('status') != 'complete' or type(report.get('rows')) is not list:
        raise ValueError('invalid_completed_study')
    if len(report['rows']) > 320:
        raise ValueError('oversized_study')
    expected = {(seed,scenario,arm) for seed in study.SPLITS['train']
                for scenario in study.SCENARIOS for arm in study.ARMS}
    rows = {}
    for row in report['rows']:
        if type(row) is not dict or type(row.get('split')) is not str or row['split'] not in study.SPLITS:
            raise ValueError('invalid_split')
        if row['split'] != 'train': continue
        clean = dict(row); clean.pop('split')
        episode = clean['episode']
        identity = episode['seed'],episode['scenario'],clean['arm']
        if identity not in expected or identity in rows:
            raise ValueError('invalid_training_roster')
        study.worker.validate(clean,*identity)
        # All observer predictions are completed before true outcomes are scored.
        forecasts = replay(project(episode['trace']))
        scored = []
        for step, forecast in zip(episode['trace'],forecasts):
            scored.append({'step':step['step'],'action_source':step['action_source'],
                'forecast':forecast,'legacy_error':step['prediction_error'],
                'observer_error':abs(forecast['velocity']-step['true_velocity'])})
        rows[identity] = scored
    if set(rows) != expected:
        raise ValueError('incomplete_training_roster')
    summaries = []
    for scenario in study.SCENARIOS:
        for arm in study.ARMS:
            for source in ('all','controller','external_supervisor'):
                subset = [s for seed in study.SPLITS['train'] for s in rows[(seed,scenario,arm)]
                          if source == 'all' or s['action_source'] == source]
                if not subset: raise ValueError('empty_registered_stratum')
                legacy = sum(s['legacy_error'] for s in subset)/len(subset)
                observed = sum(s['observer_error'] for s in subset)/len(subset)
                summaries.append({'arm':arm,'scenario':scenario,'action_source':source,
                    'episodes':len(study.SPLITS['train']),'steps':len(subset),
                    'legacy_mae':legacy,'observer_mae':observed,'observer_minus_legacy':observed-legacy})
    return {'protocol':'actual-action-observer-reanalysis-v1','status':'complete',
            'training_episodes':len(rows),'observed_steps':sum(len(v) for v in rows.values()),
            'summaries':summaries,
            'rows':[{'seed':key[0],'scenario':key[1],'arm':key[2],'steps':value}
                    for key,value in sorted(rows.items())],
            'new_episodes':0,'heldout_outcomes_analyzed':False,'actions_changed':False,
            'candidate_promoted':False,'model_weights_trained':False,
            'scope':'Retrospective prequential observer replay on fixed training trajectories. Not a counterfactual control or prospective learning result.'}


def _sources():
    files = tuple(dict.fromkeys(study.SOURCES + (
        'src/nerve_awim/actual_action_observer.py',
        'src/nerve_awim/memory_gateway/observer_reanalysis.py',
        'scripts/analyze_actual_action_observer.py')))
    return {name:sha256((study.recovery.ROOT/name).read_bytes()).hexdigest() for name in files}


def run(directory, claims, coordinator_directory, coordinator_journal):
    pins = _sources()
    path = Path(directory)/'report.json'
    before = path.read_bytes()
    study.validate_receipt(directory,claims,coordinator_directory,coordinator_journal)
    if before != path.read_bytes(): raise ValueError('source_receipt_changed')
    result = analyze(json.loads(before))
    if before != path.read_bytes(): raise ValueError('source_receipt_changed')
    if _sources() != pins: raise ValueError('source_code_changed')
    result['source_receipt_sha256'] = sha256(before).hexdigest()
    result['source_sha256'] = pins
    return result
