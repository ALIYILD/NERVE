"""Host-owned operational simulations for measuring NERVE's learned models.

This module owns true transitions. Induction receives only the resulting ledger,
never this implementation. This is a deterministic, synthetic study, not clinical
validation or an unrestricted autonomous agent. No credentials or effects.
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import random
import time
from .contracts import Policy, canonical, digest
from .ledger import Ledger, migrate
from .compiler import compile_rules, Simulator
from .reflection import reflect
from .generalization import infer, FRAME_BACKEND
from .registry import Registry
from .replay import replay
from .fidelity import assess
from .planner import plan
from ..governed_learning_v20 import LearningAuthority
from ..agentos_learning import AgentOSLearning

ACTIONS={'workflow':['inspect','validate','finish'],
         'retry_api':['request','refresh','retry'],
         'data_transform':['parse','normalize','export']}


def host_step(initial, action):
    """Pure host simulator; all unsuccessful actions retain state and consume cost."""
    state=deepcopy(initial)
    family=state['family']
    expected=ACTIONS[family]
    stage=state['stage']
    if stage >= 3 or action != expected[stage]:
        return state,stage == 3
    if family == 'workflow' and not state['approved']:
        return state,False
    if family == 'retry_api':
        if stage == 0:
            state['attempts']+=1
        elif stage == 1:
            state['token']='fresh'
        elif state['token'] == 'fresh' and state['attempts'] < 2:
            state['attempts']+=1
        else:
            return state,False
    if family == 'data_transform':
        if stage == 0:
            state['payload']=state['payload'].strip()
        elif stage == 1:
            state['payload']=state['payload'].lower()
        else:
            state['exported']=state['payload']
    state['stage']+=1
    return state,state['stage'] == 3


def tasks(seed, per_family):
    if type(per_family) is not int or not 2 <= per_family <= 100:
        raise ValueError('two to 100 episodes per family required')
    rng=random.Random(seed)
    result=[]
    for family in ACTIONS:
        for i in range(per_family):
            nonce=''.join(rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(10))
            result.append({'id':f'{family}_{seed}_{i}','initial':{'family':family,'stage':0,
                'parameter':f'work_{seed}_{nonce}','approved':True,'attempts':0,'token':'expired',
                'payload':'  '+nonce+'  ','exported':''}})
    return result


def record(ledger, actor, cases, split):
    for task in cases:
        initial=task['initial']
        family=initial['family']
        ledger.episode(actor,episode=task['id'],source=task['id'],family=family,split=split,initial=initial)
        state=initial
        for i,action in enumerate(ACTIONS[family]):
            tid=task['id']+'_'+str(i)
            prediction={**state,'stage':3}
            ledger.reserve(actor,transition_id=tid,episode=task['id'],sequence=i,action=action,
                           previous=state,prediction=prediction,model='direct_finish_baseline')
            state,completed=host_step(state,action)
            ledger.complete(actor,tid,outcome=state,completion=completed)


def execute_task(program, task, *, strategy='model', max_actions=5):
    """Host measures actual simulated actions, including failed/unknown outcomes."""
    started=time.perf_counter()
    state=deepcopy(task['initial'])
    trace=[]
    simulated_nodes=0
    abstained=False
    for _ in range(max_actions):
        if state['stage'] == 3:
            break
        if strategy == 'direct_finish':
            action=ACTIONS[state['family']][-1]
        elif strategy == 'capable_script':
            action=ACTIONS[state['family']][state['stage']]
        else:
            decision=plan(program,state,ACTIONS[state['family']],max_nodes=100)
            simulated_nodes+=decision['simulated_nodes']
            if decision['status'] != 'planned':
                abstained=True
                break
            action=decision['actions'][0]
        previous=state
        state,completed=host_step(state,action)
        trace.append({'action':action,'before_hash':digest(previous),'after_hash':digest(state),'completed':completed})
        if strategy == 'direct_finish':
            break
    success=state['stage'] == 3
    if state['family'] == 'data_transform' and success:
        success=state['exported'] == task['initial']['payload'].strip().lower()
    return {'task_id':task['id'],'family':state['family'],'success':success,'abstained':abstained,
            'simulator_actions':len(trace),'real_actions':0,'simulated_nodes':simulated_nodes,
            'provider_calls':0,'tokens':0,'provider_cost':0,'latency_ms':(time.perf_counter()-started)*1000,
            'policy_violations':int(not task['initial']['approved'] and state['stage'] > 0),
            'trace':trace}


def summarize(rows):
    by_family={}
    for row in rows:
        item=by_family.setdefault(row['family'],{'episodes':0,'success':0,'abstentions':0,'simulator_actions':0,'simulated_nodes':0,'policy_violations':0})
        item['episodes']+=1
        item['success']+=int(row['success'])
        item['abstentions']+=int(row['abstained'])
        for field in ('simulator_actions','simulated_nodes','policy_violations'):
            item[field]+=row[field]
    return {'episodes':len(rows),'success':sum(r['success'] for r in rows),'abstentions':sum(r['abstained'] for r in rows),
            'metrics_by_family':by_family,'provider_calls':0,'provider_cost':0,'real_actions':0}


def run_study(directory, *, final_per_family=80, final_seed=9001):
    """Selection then a single frozen final pass, with same tasks/budgets for controls.

    A new study directory is mandatory. The durable final-source claim is committed
    before any rule induction. Final payloads are generated only after freezing.
    Reusing a directory fails closed; no final optimization/retry is performed.
    """
    if type(final_per_family) is not int or not 2 <= final_per_family <= 100:
        raise ValueError('two to 100 final episodes per family required')
    if type(final_seed) is not int or not 1 <= final_seed <= 1000000 or final_seed in (1729,3001,19001):
        raise ValueError('fresh disjoint bounded final seed required')
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/'study.sqlite3'
    if path.exists():
        raise ValueError('fresh study directory required; final evidence cannot be recycled')
    policy=Policy(enabled=True,model_backend=FRAME_BACKEND)
    migrate(path)
    auth=LearningAuthority()
    trainer=auth.issue('offline','study','trainer')
    evaluator=auth.issue('offline','study','evaluator')
    ledger=Ledger(path,auth)
    scope=ledger.scope(evaluator,'evaluator')
    # Source reservation contains independent generation identities, no answer data.
    with ledger.db() as db:
        for family in ACTIONS:
            for i in range(final_per_family):
                db.execute('INSERT INTO wm_final VALUES(?,?,?,?,0)',(scope,f'{family}_{final_seed}_{i}','capability_study',None))
    record(ledger,trainer,tasks(1729,4),'train')
    record(ledger,evaluator,tasks(3001,2),'selection')
    training=ledger.episodes(trainer)
    exact_rules=reflect(training)['rules']
    frame_rules=infer(training)['rules']
    if not frame_rules:
        raise ValueError('training did not yield supported frame hypotheses')
    registry=Registry(ledger)
    programs={'exact_memory':compile_rules(exact_rules),
              'frame_rules':compile_rules(frame_rules,backend=FRAME_BACKEND)}
    candidates={}
    selection=tasks(3001,2)
    for name,program in programs.items():
        rules=exact_rules if name == 'exact_memory' else frame_rules
        model=registry.put(trainer,rules,program,replace(policy,model_backend=program['backend']))
        replay_report=replay(program,training)
        fidelity=assess(rules,program)
        rows=[execute_task(program,task) for task in selection]
        candidates[name]={'model_id':model,'replay':replay_report,'fidelity':fidelity,
                          'selection':summarize(rows)}
    eligible=[name for name,c in candidates.items() if c['replay']['replay_pass'] and c['fidelity']['status']=='pass']
    if not eligible:
        raise ValueError('no replay-verified candidate')
    selected=max(eligible,key=lambda name:(candidates[name]['selection']['success'],-sum(v['simulated_nodes'] for v in candidates[name]['selection']['metrics_by_family'].values()),name))
    model=candidates[selected]['model_id']
    registry.freeze(evaluator,model)
    # Predeclared ablations: a one-member frame model versus selection from the
    # bounded population; retained history versus learning only the latest family.
    recent_rules=infer([ep for ep in training if ep['family']=='data_transform'])['rules']
    programs['recent_family_only']=compile_rules(recent_rules,backend=FRAME_BACKEND)
    programs['selected_population']=programs[selected]
    # Persist consumption and frozen identity before final generation/execution.
    with ledger.db() as db:
        db.execute('UPDATE wm_final SET model=?,consumed=1 WHERE scope=? AND run=? AND consumed=0',(model,scope,'capability_study'))
    final_tasks=tasks(final_seed,final_per_family)
    final={}
    detailed={}
    for name in ('direct_finish','capable_script','exact_memory','frame_rules','selected_population','recent_family_only'):
        program=programs.get(name)
        rows=[execute_task(program,task,strategy=name if name in ('direct_finish','capable_script') else 'model') for task in final_tasks]
        final[name]=summarize(rows)
        detailed[name]=rows
    # Existing Agent OS host judges each model's evidence handoff from host facts.
    host=AgentOSLearning(directory/'agentos')
    handoffs=[]
    for row in detailed[selected]:
        evidence={'id':row['task_id'],'exit_code':0 if row['success'] else 1,
                  'artifact_exists':row['success'],'qa_passed':row['success'],'memory_written':False}
        output={'status':'done' if row['success'] else 'failed','passed':row['success'],'memory_saved':False}
        receipt=host.observe('world-model-study',evidence,output,mode='world-model-offline')
        handoffs.append(receipt['success'])
    prohibited=deepcopy(final_tasks[0])
    prohibited['initial']['approved']=False
    policy_probe=execute_task(programs[selected],prohibited)
    drift=deepcopy(final_tasks[0])
    drift['initial']['new_sensor']=None
    drift_probe=execute_task(programs[selected],drift)
    transfer=tasks(19001,2)
    retention=summarize([execute_task(programs[selected],t) for t in transfer])
    report={'schema_version':1,'evidence_mode':'offline deterministic host simulations',
            'selected':selected,'model_id':model,'candidates':candidates,'final':final,'final_seed':final_seed,
            'ablation_effects':{'frame_over_exact_successes':final['frame_rules']['success']-final['exact_memory']['success'],
                'population_over_single_frame_successes':final['selected_population']['success']-final['frame_rules']['success'],
                'retained_history_over_recent_only_successes':final['frame_rules']['success']-final['recent_family_only']['success']},
            'retention':retention,'policy_probe':policy_probe,'schema_drift_probe':drift_probe,
            'host_handoff_verified':sum(handoffs),'host_handoff_total':len(handoffs),
            'holdout_status':'consumed','eligibility':False,'deployment_authorized':False,
            'status':'offline_gain_over_weak_baseline' if final[selected]['success'] > final['direct_finish']['success'] else 'no_gain',
            'capable_control_gain':final[selected]['success']-final['capable_script']['success'],
            'limitations':['synthetic deterministic families with shared mechanics; no real-world or clinical claim',
                          'induction and all rules are deterministic; no live LLM used',
                          'capable scripted planner is a matched ceiling control',
                          'eligibility remains false pending sealed-process authority and complete release gates']}
    (directory/'final-traces.json').write_text(json.dumps(detailed,indent=2)+'\n')
    (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
