"""Matched development-only prequential gain experiment, including wrong priors."""
from dataclasses import asdict
from pathlib import Path
from hashlib import sha256
import json
import math
import secrets
import tempfile
import time

from ..runtime_v28 import NerveResearchRuntime
from ..single_use_standard import SingleUseStandardRuntime
from ..prequential_gain import PrequentialGainRuntime
from ..recovery_v25 import sign_approval
from . import recovery_adaptation as fixture
from . import standard_learning_audit as learning_audit
from . import standard_learning_demo as standard

ARMS = ('frozen','single_use','selector')
PLANTS = {'nominal':(.27,)*4,'lower':(.18,)*4,'higher':(.4,)*4,'drift':(.27,.48,.15,.4)}


def sources():
    files = tuple(dict.fromkeys(standard.SOURCES+('src/nerve_awim/prequential_gain.py',
        'src/nerve_awim/memory_gateway/prequential_gain_demo.py','scripts/demo_prequential_gain.py')))
    return {name:sha256((standard.ROOT/name).read_bytes()).hexdigest() for name in files}


def _same(a,b): return fixture._same(a,b)


def _require(condition):
    if not condition: raise ValueError('invalid_prequential_development_evidence')


def _shadow(controller):
    return controller.core.drift_model.gain if controller.core.drift_model is not None else controller.core.gain


def execute(arm,plant):
    if type(arm) is not str or arm not in ARMS or type(plant) is not str or plant not in PLANTS:
        raise ValueError('fixed_development_case_required')
    pins = sources(); started = time.monotonic(); schedule = fixture._schedule(9)
    trace = []; recoveries = []; position = velocity = 0.; secret = secrets.token_bytes(32)
    constructor = {'frozen':NerveResearchRuntime,'single_use':SingleUseStandardRuntime,'selector':PrequentialGainRuntime}[arm]
    with tempfile.TemporaryDirectory(prefix='nerve-prequential-development-') as directory:
        runtime = constructor(verifier=fixture.SyntheticVerifier(),issuer=fixture.ISSUER,audience=fixture.AUDIENCE,
            secret=secret,ledger_path=str(Path(directory)/'approvals.sqlite'),max_missing=5,recovery_samples=3,
            evidence_minimum=2,risk_aversion=.25,safe_position=6.,safe_velocity=2.,min_samples=6,
            target=fixture.TARGET,learning_rate=0. if arm=='frozen' else .08,estimator='standard',horizon=3,bound=6.)
        controller = runtime.controller
        for step in range(80):
            if time.monotonic()-started > 30: raise TimeoutError('development_episode_budget')
            shadow_before = _shadow(controller); sensor = None
            if step:
                noise = schedule[step-1]
                if not noise['dropped']:
                    sensor = dict(timestamp=step-1,position=position+noise['position_noise'],velocity=velocity+noise['velocity_noise'])
                    if controller.phase=='active':
                        sensor['route']='active'
                        sensor['accepted']=runtime.observe(sensor['timestamp'],position=sensor['position'],velocity=sensor['velocity'])
                    else:
                        sensor['route']='recovery'
                        sensor['accepted']=runtime.observe_recovery(sensor['timestamp'],observed_now=step-1,
                            position=sensor['position'],velocity=sensor['velocity'])
                        if controller.recovery_ready():
                            gain_before = _shadow(controller)
                            approval = sign_approval(secret,'synthetic-supervisor','supervisor',controller.incident,f'prequential-{step}',step)
                            granted = runtime.authorise_recovery('synthetic-host-approval',approval,step-1)
                            recoveries.append(dict(step=step,incident=controller.incident,authorised=granted,
                                                   gain_before=gain_before,gain_after=_shadow(controller)))
                runtime.advance_time(step-1)
            selected_gain = controller.core.gain; shadow_gain = _shadow(controller)
            estimate = controller.core.filter.state.velocity; history_before = len(controller.core.filter.actions)
            before = controller.selector_snapshot() if arm=='selector' else None
            result = runtime.tick()
            if result.action is None and result.phase=='active': raise RuntimeError('development_controller_infeasible')
            action = 0 if result.action is None else result.action
            after = controller.selector_snapshot() if arm=='selector' else None
            prediction = fixture.RETENTION*estimate+selected_gain*action
            # Only the environment sees the hidden gain and true state.
            true_gain = PLANTS[plant][step//20]
            velocity = fixture.RETENTION*velocity+true_gain*action; position += velocity
            trace.append(dict(step=step,sensor=sensor,command=asdict(result),action=action,
                action_source='controller' if result.action is not None else 'external_supervisor',
                history_before=history_before,history_after=len(controller.core.filter.actions),
                gain_before_observation=shadow_before,estimated_gain=shadow_gain,selected_gain=selected_gain,
                estimated_velocity=estimate,predicted_velocity=prediction,selector_before=before,selector_after=after,
                true_gain=true_gain,true_position=position,true_velocity=velocity,
                goal_error=abs(position-fixture.TARGET),prediction_error=abs(prediction-velocity),
                violation=abs(position)>6 or abs(velocity)>2))
    row = dict(arm=arm,plant=plant,seed=9,steps=80,initial_gain=.27,final_gain=trace[-1]['estimated_gain'],
        trace=trace,recovery_events=recoveries,metrics=_metrics(trace),source_sha256=pins,
        elapsed_seconds=time.monotonic()-started)
    row['learning_audit'] = learning_audit.audit(row,'single_use' if arm=='selector' else arm)
    validate(row,arm,plant)
    if sources()!=pins: raise ValueError('source_drift')
    return row


def _metrics(trace):
    return {'mean_goal_error':sum(t['goal_error'] for t in trace)/80,
            'mean_prediction_error':sum(t['prediction_error'] for t in trace)/80,
            'violations':sum(t['violation'] for t in trace),
            'supervisor_steps':sum(t['command']['action'] is None for t in trace)}


def validate(row,arm,plant):
    _require(type(row) is dict and set(row)=={'arm','plant','seed','steps','initial_gain','final_gain','trace','recovery_events','metrics','source_sha256','elapsed_seconds','learning_audit'})
    _require(type(row['elapsed_seconds']) in (int,float) and math.isfinite(row['elapsed_seconds']) and row['elapsed_seconds']>=0)
    _require(type(row) is dict and row['arm']==arm and arm in ARMS and row['plant']==plant and plant in PLANTS)
    _require(type(row['seed']) is int and row['seed']==9 and row['steps']==80)
    _require(row['source_sha256']==sources())
    trace=row['trace']; _require(type(trace) is list and len(trace)==80)
    _require(_same(row['learning_audit'],learning_audit.audit(row,'single_use' if arm=='selector' else arm)))
    events={}
    for event in row['recovery_events']:
        _require(set(event)=={'step','incident','authorised','gain_before','gain_after'})
        _require(type(event['incident']) is int and event['incident']>0)
        events[event['step']]=event
    position=velocity=0.; schedule=fixture._schedule(9)
    for step,item in enumerate(trace):
        _require(set(item)=={'step','sensor','command','action','action_source','history_before','history_after','gain_before_observation','estimated_gain','selected_gain','estimated_velocity','predicted_velocity','selector_before','selector_after','true_gain','true_position','true_velocity','goal_error','prediction_error','violation'})
        _require(set(item['command'])=={'action','phase','incident'})
        _require(type(item['command']['incident']) is int and item['command']['incident']>=0)
        _require(type(item['step']) is int and item['step']==step)
        sensor=item['sensor']
        if step and not schedule[step-1]['dropped']:
            _require(type(sensor) is dict and set(sensor)=={'timestamp','position','velocity','route','accepted'})
            _require(_same(sensor['timestamp'],step-1))
            _require(sensor['route']==('active' if trace[step-1]['command']['phase']=='active' else 'recovery'))
            _require(_same(sensor['position'],position+schedule[step-1]['position_noise']))
            _require(_same(sensor['velocity'],velocity+schedule[step-1]['velocity_noise']))
        else: _require(sensor is None)
        event=events.get(step)
        recovered=event is not None and event['authorised']
        if event is not None:
            _require(sensor is not None and sensor['route']=='recovery' and sensor['accepted'] is True)
            _require(event['incident']==item['command']['incident'])
            if recovered: _require(item['command']['phase']=='active' and item['history_before']==0)
        if step and trace[step-1]['command']['phase']!='active' and item['command']['phase']=='active':
            _require(recovered)
        action=item['action']; _require(type(action) is int and action in (-1,0,1))
        _require(_same(item['command']['action'],action if item['action_source']=='controller' else None))
        _require(item['action_source'] in ('controller','external_supervisor'))
        _require(item['command']['phase'] in ('active','supervision_required','awaiting_approval'))
        _require(.01<=item['selected_gain']<=1.)
        _require(item['command']['phase']=='active' if item['action_source']=='controller' else item['command']['phase']!='active')
        for key in ('selected_gain','estimated_velocity','predicted_velocity'):
            _require(type(item[key]) in (int,float) and math.isfinite(item[key]))
        if arm!='selector':
            _require(item['selected_gain']==item['estimated_gain'])
            _require(item['selector_before'] is None and item['selector_after'] is None)
        gain=PLANTS[plant][step//20]; velocity=fixture.RETENTION*velocity+gain*action;position+=velocity
        prediction=fixture.RETENTION*item['estimated_velocity']+item['selected_gain']*action
        expected=dict(true_gain=gain,true_velocity=velocity,true_position=position,predicted_velocity=prediction,
                      goal_error=abs(position-fixture.TARGET),prediction_error=abs(prediction-velocity),
                      violation=abs(position)>6 or abs(velocity)>2)
        for key,value in expected.items(): _require(_same(item[key],value))
    if arm=='selector': _audit_selector(row)
    _require(_same(row['metrics'],_metrics(trace)))
    return True


def _audit_selector(row):
    """Reconstruct fixed-budget selector receipts from prior action/sensor data.

    This 80-step fixture cannot hit the runtime's 128-step age or pending limits.
    No true plant fields enter the reconstruction.
    """
    pending={}; scores=[]; counts=dict(resolved=0,evicted=0,expired=0,recovery_resets=0)
    events={e['step']:e for e in row['recovery_events']}
    for item in row['trace']:
        step=item['step']; sensor=item['sensor']
        if sensor and sensor['accepted'] and sensor['route']=='active' and sensor['timestamp'] in pending:
            record=pending.pop(sensor['timestamp'])
            scores.append(dict(record,observed_velocity=sensor['velocity'],
                nominal_error=abs(record['nominal_forecast']-sensor['velocity']),
                learned_error=abs(record['learned_forecast']-sensor['velocity'])))
            scores=scores[-4:]; counts['resolved']+=1
        if step in events and events[step]['authorised']:
            pending.clear(); scores.clear(); counts['recovery_resets']+=1
        mode='learned' if len(scores)==4 and all(r['learned_error']<r['nominal_error'] for r in scores) else 'nominal'
        gain=item['estimated_gain'] if mode=='learned' else .27
        def snapshot():
            return dict(mode=mode,nominal_gain=.27,shadow_gain=item['estimated_gain'],selected_gain=gain,
                        pending=list(pending.values()),scores=scores,counts=counts)
        _require(_same(item['selector_before'],snapshot()))
        _require(item['selected_gain']==gain)
        if item['action_source']=='controller' and item['action']!=0:
            velocity=item['estimated_velocity']; action=item['action']; shadow=item['estimated_gain']
            _require(step not in pending)
            pending[step]=dict(timestamp=step,velocity=velocity,action=action,nominal_gain=.27,shadow_gain=shadow,
                nominal_forecast=fixture.RETENTION*velocity+.27*action,
                learned_forecast=fixture.RETENTION*velocity+shadow*action)
        _require(_same(item['selector_after'],snapshot()))


def compare(rows):
    indexed={}
    for row in rows:
        validate(row,row['arm'],row['plant'])
        identity=(row['plant'],row['arm'])
        if identity in indexed: raise ValueError('duplicate_development_case')
        indexed[identity]=row
    if set(indexed)!={(p,a) for p in PLANTS for a in ARMS}: raise ValueError('incomplete_development_roster')
    comparisons=[]
    for baseline in ('frozen','single_use'):
        strata=[]
        for plant in PLANTS:
            candidate=indexed[plant,'selector']['metrics']; control=indexed[plant,baseline]['metrics']
            deltas={key:candidate[key]-control[key] for key in candidate}
            passed=candidate['violations']==0 and all(value <= (1e-12 if key.startswith('mean_') else 0) for key,value in deltas.items())
            strata.append(dict(plant=plant,deltas=deltas,nonregression=passed))
        gain=-sum(s['deltas']['mean_goal_error'] for s in strata)
        comparisons.append(dict(baseline=baseline,strata=strata,sum_goal_gain=gain,
                                passed=all(s['nonregression'] for s in strata) and gain>1e-5))
    return {'passed':all(c['passed'] for c in comparisons),'comparisons':comparisons}


def run_demo():
    pins=sources(); start=time.monotonic(); rows=[]
    for plant in PLANTS:
        for arm in ARMS:
            if time.monotonic()-start>360: raise TimeoutError('development_budget')
            rows.append(execute(arm,plant))
    if time.monotonic()-start>360: raise TimeoutError('development_budget')
    if sources()!=pins: raise ValueError('source_drift')
    screen=compare(rows)
    return dict(protocol='prequential-gain-development-v1',status='complete',rows=rows,episodes=12,plant_steps=960,
        screen=screen,source_sha256=pins,registered_streams_used=False,heldout_outcomes_analyzed=False,
        performance_improvement_claimed=False,candidate_promoted=False,model_weights_trained=False,
        recommendation='register_fresh_study' if screen['passed'] else 'retain_baselines_and_diagnose')
