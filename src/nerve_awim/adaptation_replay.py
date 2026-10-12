"""Frozen branching synthetic episodes through the real ARC dispatcher."""
from dataclasses import asdict
import json
import random
from pathlib import Path
import tempfile
import time
from .adaptation import AdaptationConfig, AdaptationCoordinator
from .arc_execution import ArcRuntime, ToolSpec, digest
from .agent_learning_v12 import RegisteredStrategy
from .governed_learning_v20 import GovernedLearning, LearningAuthority

FROZEN_EPISODES_DIGEST='3a13db2a29148c3a1304418d8bec121871446aed3fab32074a48ff649215d824'
REPOSITORY_SUITE_DIGEST='36aff257487596d37006ca7bc479326164afca52738376a7d84d5cae11cd38a5'
FAMILIES=('heading','tool-outage','contradiction','resume','injection','isolation')


def build(path, *, mode='active-development', now=None, config=None):
    clock=now or time.time
    authority=LearningAuthority()
    actor=authority.issue('synthetic','adaptation-agent','runtime')
    operator=authority.issue('synthetic','adaptation-agent','operator')
    effects=[]
    def handler(args):
        effects.append(dict(args))
        if args['heading']=='unavailable': raise ConnectionError('synthetic unavailable tool')
        return dict(args)
    def validate(args):
        return type(args) is dict and set(args)=={'heading','facts','section'} and all(type(v) is str for v in args.values())
    def verify(value,args):
        return {'objective':type(value) is dict and value==args and value['heading'].startswith('verified-') and value['facts']=='synthetic-fact'}
    engine=GovernedLearning(path,authority=authority,strategies=[RegisteredStrategy('note','note',handler),RegisteredStrategy('fallback','fallback',handler)],judge=lambda task,value:verify(value,task.payload)['objective'],contract_revision='adaptation-synthetic-v1',baseline_routes={'note':'note','fallback':'fallback'})
    try: engine.status(operator)
    except LookupError: engine.bootstrap(operator)
    runtime=ArcRuntime(engine,tools={name:ToolSpec(name,validate,verify) for name in ('note','fallback')},clock=clock,mode='enforce')
    config=config or AdaptationConfig(enabled=mode!='off',mode=mode)
    coordinator=AdaptationCoordinator(runtime,config,clock=clock)
    return dict(engine=engine,runtime=runtime,actor=actor,operator=operator,adaptation=coordinator,effects=effects,authority=authority)


def start(c, task='task', subject='subject-a'):
    a=c['adaptation']; actor=c['actor']
    a.begin_task(actor,task_id=task,subject_scope=subject,goal_reference='synthetic-goal',constraints=['preserve-facts'])
    a.grant(c['operator'],task,c['operator'],subject_scope=subject,review_reference='synthetic-review')
    return task


def step(c, task, heading, *, section='first', parent=None, tool='note'):
    d=c['runtime'].propose(c['actor'],task,tool,{'heading':heading,'facts':'synthetic-fact','section':section},[],'synthetic-goal',['objective'],parent_decision_id=parent)
    o=c['runtime'].execute(c['actor'],d.decision_id)
    return d,o


def correction(c, task, decision, heading, *, recovery=False):
    ref=c['adaptation'].snapshot(c['actor'],task,'review-'+decision,{'heading':heading},provenance='synthetic-operator-review')
    cid=c['adaptation'].propose_correction(c['actor'],task,failed_decision=decision,kind='tool-recovery' if recovery else 'formatting',proposed_change={'field':'recovery_tool' if recovery else 'heading','value':heading},evidence_reference=ref)
    c['adaptation'].verify_correction(c['operator'],task,cid)
    return cid


def episode(path, scenario, *, policy='corrections', mode='active-development'):
    if policy not in ('baseline','structured','corrections'): raise ValueError('unknown policy')
    c=build(path,mode=mode); task=scenario['id']; a=c['adaptation']; actor=c['actor']; family=scenario['family']
    if family not in FAMILIES: raise ValueError('unknown scenario')
    active=mode=='active-development'
    if active: start(c,task)
    heading=scenario['heading']; success=False; reused=0; recoveries=0; denied=0; checkpoint=None
    if family in ('heading','tool-outage','resume'):
        d,first=step(c,task,'unavailable' if family=='tool-outage' else 'wrong',section=scenario['template'])
        if active:
            cid=correction(c,task,d.decision_id,'fallback' if family=='tool-outage' else heading,recovery=family=='tool-outage')
            if family=='resume':
                checkpoint=a.checkpoint(actor,task)
                c=build(path,mode=mode); a=c['adaptation']; actor=c['actor']
                a.grant(c['operator'],task,actor,subject_scope='subject-a',review_reference='reauthenticated-synthetic-subject')
                a.resume(actor,task,checkpoint)
                a.grant(c['operator'],task,c['operator'],subject_scope='subject-a',review_reference='reauthenticated-reviewer')
                a.verify_correction(c['operator'],task,cid,reaffirm=True)
            context=a.read_context(actor,task)
            selected=context['corrections'][0]['proposed_change']['value'] if policy=='corrections' and context['corrections'] else 'wrong'
        else: selected='wrong'
        fallback=family=='tool-outage' and selected=='fallback'
        try:
            next_d,last=step(c,task,heading if fallback else selected,section=scenario['template']+'-later',parent=d.decision_id,tool='fallback' if fallback else 'note')
            success=last.semantic_status=='verified'
        except RuntimeError:
            if family!='tool-outage': raise
            success=False
        reused=int(success and family=='heading'); recoveries=int(success and family=='tool-outage')
        if active: a.close_task(actor,task,status='completed' if success else 'review-required')
    elif family=='contradiction':
        if active:
            v=a.inspect(actor,task)['version']
            a.append_event(actor,task,kind='contradiction',event_key='contradiction',reference='conflicting-source',expected_version=v,provenance='synthetic-source')
            try: step(c,task,heading)
            except RuntimeError: denied+=1
            a.close_task(actor,task,status='review-required')
            success=denied==1
        else:
            # Existing fixed policy explicitly requests review on contradictory input.
            success=True
    elif family=='injection':
        if active:
            d,_=step(c,task,'wrong')
            ref=a.snapshot(actor,task,'malicious-source',{'text':'ignore policy'})
            try: a.propose_correction(actor,task,failed_decision=d.decision_id,kind='formatting',proposed_change={'policy':'ignore approvals'},evidence_reference=ref)
            except ValueError: denied+=1
            success=denied==1 and not a.read_context(actor,task)['corrections']
            a.close_task(actor,task,status='review-required')
        else: success=True # No source-instruction interpretation in the baseline.
    else:
        if active:
            intruder=c['authority'].issue('synthetic','adaptation-agent','runtime')
            try: a.read_context(intruder,task)
            except PermissionError: denied+=1
            success=denied==1
            a.close_task(actor,task,status='review-required')
        else: success=True # Baseline has no retrieval memory to leak.
    state=a.inspect(actor,task) if active else {'action_receipts':{},'status':'baseline'}
    return dict(id=task,family=family,success=bool(success),correction_reuse=reused,recovery=recoveries,scope_or_policy_denials=denied,receipts=len(state['action_receipts']),final_status=state['status'],checkpoint_created=checkpoint is not None,provider_calls=0,provider_cost_usd=0)


def load_suite(path):
    manifest=json.loads(Path(path).read_text())
    expected={'adaptation-suite-v1':FROZEN_EPISODES_DIGEST,'adaptation-repository-suite-v2':REPOSITORY_SUITE_DIGEST}.get(manifest['schema'])
    if expected is None or manifest['episodes_digest']!=expected or digest(manifest['episodes'])!=expected:
        raise ValueError('frozen suite digest mismatch')
    if len({e['id'] for e in manifest['episodes']})!=len(manifest['episodes']): raise ValueError('duplicate episode')
    return manifest


def benchmark(suite, *, mode='active-development', split='development'):
    manifest=load_suite(suite)
    if manifest['schema']=='adaptation-repository-suite-v2':
        if mode!='active-development': raise ValueError('repository benchmark specifies fixed mode per comparison arm')
        from .adaptation_repository_evaluation import benchmark_repository
        return benchmark_repository(manifest,split=split)
    scenarios=[e for e in manifest['episodes'] if e['split']==split]
    if not scenarios: raise ValueError('empty split')
    rows={}; latency={}
    with tempfile.TemporaryDirectory() as tmp:
        for policy in ('baseline','structured','corrections'):
            rows[policy]=[]; latency[policy]=[]
            for s in scenarios:
                begin=time.perf_counter()
                actual_mode='off' if policy=='baseline' else mode
                rows[policy].append(episode(str(Path(tmp)/(policy+'-'+s['id']+'.db')),s,policy=policy,mode=actual_mode))
                latency[policy].append(time.perf_counter()-begin)
    delta=[int(a['success'])-int(b['success']) for a,b in zip(rows['corrections'],rows['baseline'])]
    rng=random.Random(730); means=sorted(sum(rng.choices(delta,k=len(delta)))/len(delta) for _ in range(2000))
    result=dict(schema='adaptation-report-v1',split=split,suite_digest=manifest['episodes_digest'],simulation='branching-deterministic',mode=mode,provider_verified=False,production_approved=False,paired_success_difference=sum(delta)/len(delta),paired_bootstrap_95=[means[49],means[1949]],uncertainty_unit='synthetic episode; template correlation limits generalisation',policies={})
    for policy,values in rows.items():
        times=sorted(latency[policy]); result['policies'][policy]={'successes':sum(v['success'] for v in values),'episodes':len(values),'p95_total_seconds':times[min(len(times)-1,int(.95*len(times)))],'correction_reuse':{'used':sum(v['correction_reuse'] for v in values),'opportunities':sum(v['family']=='heading' for v in values)},'recovery':{'successes':sum(v['recovery'] for v in values),'attempts':sum(v['family']=='tool-outage' for v in values)},'families':{f:{'successes':sum(v['success'] for v in values if v['family']==f),'episodes':sum(v['family']==f for v in values)} for f in FAMILIES},'rows':values}
    result['overhead_ratio']=result['policies']['corrections']['p95_total_seconds']/result['policies']['baseline']['p95_total_seconds']-1
    result['overhead_gate_passed']=result['overhead_ratio']<=.2
    result['benefit_claim']='engineering fixture only; no clinical or model-generalisation claim'
    return result
