#!/usr/bin/env python3
"""Exploratory dev700 robustness; no holdout access or promotion."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
import run_scientific_runpod_gate as base
from nerve_awim.memory_gateway import scientific_task_bank as bank

gate=base.gate
VERSION='scientific-runpod-robustness-36.5-v1'
SEEDS=(20261015,20261016,20261017)
REPLICATES=((20261015,20261015),(20261016,20261015),(20261017,20261015),(20261015,20261016))

def pins():
    result=base.pins();root=Path(__file__).resolve().parents[1]
    result[str(Path(__file__).resolve().relative_to(root))]=base.digest(Path(__file__).read_bytes())
    return result

def tasks_at(path,expected_hash):
    raw=path.read_bytes()
    if base.digest(raw)!=expected_hash:raise ValueError('development_input_changed')
    tasks=json.loads(raw)
    if len(tasks)!=700 or len({t['task_id'] for t in tasks})!=700 or any(t['split']!='dev' for t in tasks) or Counter(t['stratum'] for t in tasks)!=Counter({s:100 for s in bank.STRATA}):raise ValueError('dev700_seven_strata_required')
    for t in tasks:
        if bank._hash({k:v for k,v in t.items() if k!='content_sha256'})!=t['content_sha256']:raise ValueError('task_content_changed')
    return tasks

def payload(task,seed):
    p=gate.prepared_for(task,'candidate')
    if p['route']=='deterministic_abstention':return None
    result=dict(model=base.MODEL,temperature=0,seed=seed,stream=False,max_tokens=128,messages=[{'role':'system','content':p['system']},{'role':'user','content':p['user']}])
    result['response_format']={'type':'json_schema','json_schema':{'name':'scientific_measurement','strict':True,'schema':p['schema']}}
    return result

def ordered(tasks,order_seed):
    return sorted(tasks,key=lambda t:(hashlib.sha256(f'{order_seed}:robustness-order:{t["task_id"]}'.encode()).hexdigest(),t['task_id']))

def entries(tasks):
    result=[]
    for replicate,(seed,order_seed) in enumerate(REPLICATES):
        for task in ordered(tasks,order_seed):result.append((replicate,seed,order_seed,task))
    return result

def register(root,input_path,bank_manifest,prior):
    manifest=base.read(bank_manifest);prior_reg=base.read(prior/'dry/registration.json')
    tasks=tasks_at(input_path,manifest['files']['dev'])
    if base.digest(bank_manifest.read_bytes())!='e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6':raise ValueError('original_bank_required')
    if any(prior_reg['sources'].get(k)!=v for k,v in base.pins().items()):raise ValueError('original_v3_sources_changed')
    identity=base.identity()
    if identity!=prior_reg['identity']:raise ValueError('substrate_changed')
    root.mkdir(mode=0o700)
    raw=input_path.read_bytes()
    with (root/'private-input.json').open('xb') as f:f.write(raw)
    (root/'private-input.json').chmod(0o600)
    schedule=[dict(replicate=i,seed=s,order_seed=o,task_id=t['task_id'],payload_sha256=base.digest(base.canonical(payload(t,s)).encode())) for i,s,o,t in entries(tasks)]
    reg=dict(version=VERSION,scope='exploratory_development_only',promotion_authorized=False,holdout_accessed=False,identity=identity,sources=pins(),bank_manifest_sha256=base.digest(bank_manifest.read_bytes()),input_sha256=base.digest(raw),seeds=list(SEEDS),replicates=[{'seed':s,'order_seed':o} for s,o in REPLICATES],schedule_sha256=base.digest(base.canonical(schedule).encode()),order_rule='sha256(order_seed:robustness-order:task_id)',seed_variance='sample variance across first three runs with shared order',order_sensitivity='paired correctness flips between seed20261015 on two shuffled orders; descriptive single-seed contrast',rows=2800,items_per_stratum_per_run=100,timeout_seconds=prior_reg['timeout_seconds'],max_attempts_per_call=3,max_logical_calls=sum(payload(t,s) is not None for _,s,_,t in entries(tasks)),max_wall_seconds=7200,hourly_usd=prior_reg['hourly_usd'],cost_method=prior_reg['cost_method'],interval='95% Wilson per stratum/run; descriptive marginal, no pooled independent300-item claim',safety='counts of answered incorrect and abstention on expected answers; synthetic validity only',ux='n/a')
    base.write(root/'registration.json',reg)
    return dict(registered=True,registration_sha256=base.digest((root/'registration.json').read_bytes()),rows=reg['rows'],model_calls=reg['max_logical_calls'],replicates=reg['replicates'])

def summary(reg,rows,elapsed,attempts,timeouts,complete,error,attempt_latencies=None):
    strata={}
    for st in bank.STRATA:
        runs=[]
        for i,(seed,order_seed) in enumerate(REPLICATES):
            chosen=[r for r in rows if r['replicate']==i and r['stratum']==st];correct=sum(r['score']['strict_correct'] for r in chosen)
            runs.append(dict(seed=seed,order_seed=order_seed,n=len(chosen),correct=correct,failures=len(chosen)-correct,ci95=base.wilson(correct,len(chosen)),answered_incorrect=sum(r['score']['answer_status']=='answer' and not r['score']['strict_correct'] for r in chosen),false_abstentions=sum(r['score']['answer_status']=='abstain' and not r['score']['strict_correct'] for r in chosen),format_valid=sum(r['score']['format_valid'] for r in chosen),model_calls=sum(r['model_calls'] for r in chosen)))
        rates=[r['correct']/r['n'] for r in runs[:3] if r['n']==100]
        first={r['task_id']:r['score']['strict_correct'] for r in rows if r['replicate']==0 and r['stratum']==st};second={r['task_id']:r['score']['strict_correct'] for r in rows if r['replicate']==3 and r['stratum']==st};common=first.keys()&second.keys()
        strata[st]=dict(runs=runs,seed_sample_variance=statistics.variance(rates) if len(rates)==3 else None,seed_accuracy_range=[min(rates),max(rates)] if rates else None,order_comparison=dict(paired_n=len(common),gains=sum(not first[t] and second[t] for t in common),losses=sum(first[t] and not second[t] for t in common),flips=sum(first[t]!=second[t] for t in common)),hypothesis_failure_count=sum(r['failures'] for r in runs[:3]))
    full=complete and len(rows)==2800
    usage={key:sum(r['usage'][key] for r in rows if r['usage']) for key in ('prompt_tokens','completion_tokens','total_tokens')}
    abstentions=sum(r['score']['answer_status']=='abstain' for r in rows)
    correct_abstentions=sum(r['score']['answer_status']=='abstain' and r['score']['strict_correct'] for r in rows)
    latencies=attempt_latencies or []
    return dict(version=VERSION,complete=full,status='complete_exploratory' if full else 'incomplete_infrastructure',promotion_authorized=False,holdout_accessed=False,identity=reg['identity'],wall_seconds=elapsed,allocated_cost_estimate_usd=elapsed*reg['hourly_usd']/3600,cost_method=reg['cost_method'],strata=strata,logical_model_calls=sum(r['model_calls'] for r in rows),physical_attempts=attempts,timeouts=timeouts,measured_tokens=usage,error_type=error,axes={'accuracy':'per-stratum/run counts and Wilson intervals','efficiency':{'wall_seconds':elapsed,'model_calls':sum(r['model_calls'] for r in rows),'measured_tokens':usage,'physical_attempt_latency_median_seconds':statistics.median(latencies) if latencies else None,'physical_attempt_latency_max_seconds':max(latencies) if latencies else None,'capacity_delta_vs_frozen_v3':0,'capacity_definition':'same model weights and deterministic policy; no learned parameters added; GPU peak memory not measured'},'robustness':'three model seeds at fixed shuffled order; separate matched same-seed two-order comparison','safety':{'answered_incorrect':sum(r['score']['answer_status']=='answer' and not r['score']['strict_correct'] for r in rows),'false_abstentions':sum(r['score']['answer_status']=='abstain' and not r['score']['strict_correct'] for r in rows),'abstentions':abstentions,'correct_abstentions':correct_abstentions,'abstention_precision':correct_abstentions/abstentions if abstentions else None,'domain_verifier_violations':'n/a: no separate domain verifier; frozen strict scorer supplies answer integrity counts','scope':'synthetic answer integrity, not real-world safety evidence'},'ux':'n/a'},interpretation='Reused development instances; exploratory. Seed variance uses first3 runs; order comparison is a single matched seed, not a general causal order effect. No promotion or holdout.')

def run(root):
    reg=base.read(root/'registration.json');tasks=tasks_at(root/'private-input.json',reg['input_sha256'])
    if pins()!=reg['sources'] or base.identity()!=reg['identity']:raise ValueError('registration_changed')
    base.write(root/'consumed.json',{'registration_sha256':base.digest((root/'registration.json').read_bytes())})
    start=time.monotonic();rows=[];failure=None
    try:
        for index,(replicate,seed,order_seed,task) in enumerate(entries(tasks)):
            if time.monotonic()-start+3*reg['timeout_seconds']>reg['max_wall_seconds']:raise TimeoutError('wall_budget')
            p=payload(task,seed);usage=None;finish=None
            if p is None:raw='ABSTAIN'
            else:raw,usage,finish=base.attempt(root,index,p,reg['timeout_seconds'])
            row=dict(replicate=replicate,seed=seed,order_seed=order_seed,task_id=task['task_id'],stratum=task['stratum'],raw_output=raw,usage=usage,finish_reason=finish,model_calls=int(p is not None),score=gate.score(raw,task,gate.prepared_for(task,'candidate')))
            base.write(root/f'row-{index:03d}.json',row);rows.append(row)
        if pins()!=reg['sources'] or base.identity()!=reg['identity']:raise ValueError('identity_changed')
    except Exception as error:failure=type(error).__name__
    report=dict(complete=failure is None,rows=rows,error_type=failure,wall_seconds=time.monotonic()-start,registration_sha256=base.digest((root/'registration.json').read_bytes()))
    base.write(root/'private-report.json',report)
    return verify(root,save=True)

def verify(root,save=False):
    reg=base.read(root/'registration.json');report=base.read(root/'private-report.json');tasks=tasks_at(root/'private-input.json',reg['input_sha256']);binding=base.digest((root/'registration.json').read_bytes())
    if pins()!=reg['sources'] or report['registration_sha256']!=binding or base.read(root/'consumed.json')['registration_sha256']!=binding:raise ValueError('binding_changed')
    rows=report['rows'];attempts=0;timeouts=0;attempt_latencies=[]
    if type(report['complete']) is not bool or report['complete']!=(report['error_type'] is None):raise ValueError('terminal_status_changed')
    if not math.isfinite(report['wall_seconds']) or not 0<=report['wall_seconds']<=reg['max_wall_seconds']:raise ValueError('invalid_wall_time')
    claims={}
    for path in root.glob('attempt-*-claim.json'):
        index=int(path.name.split('-')[1]);claims.setdefault(index,[]).append(path)
    if any(not 0<=i<2800 for i in claims):raise ValueError('unexpected_attempt_index')
    if len(rows)>2800 or report['complete'] and len(rows)!=2800:raise ValueError('row_count_changed')
    schedule=[]
    for index,(replicate,seed,order_seed,task) in enumerate(entries(tasks)):
        p=payload(task,seed);schedule.append(dict(replicate=replicate,seed=seed,order_seed=order_seed,task_id=task['task_id'],payload_sha256=base.digest(base.canonical(p).encode())))
        group=sorted(claims.get(index,[]));completed=None
        if len(group)>3:raise ValueError('retry_limit')
        for number,path in enumerate(group):
            if path.name!=f'attempt-{index:03d}-{number}-claim.json' or p is None:raise ValueError('attempt_sequence')
            c=base.read(path);result=base.read(root/f'attempt-{index:03d}-{number}-result.json');attempts+=1;timeouts+=int(result['status']=='timeout')
            envelope={'url':base.ORIGIN+'/v1/chat/completions','method':'POST','headers':{'Content-Type':'application/json'},'body':base.canonical(p)}
            if c!={'request':envelope,'request_sha256':base.digest(base.canonical(envelope).encode()),'timeout_seconds':reg['timeout_seconds']}:raise ValueError('request_changed')
            if result['status'] not in ('complete','timeout','error') or number<len(group)-1 and result['status']!='timeout':raise ValueError('attempt_status')
            if not math.isfinite(result['elapsed_seconds']) or result['elapsed_seconds']<0:raise ValueError('invalid_attempt_time')
            attempt_latencies.append(result['elapsed_seconds'])
            if result['status']=='complete':completed=base.decode(result['wire'])
        if index>=len(rows):
            if index>len(rows) and group:raise ValueError('unexpected_attempt')
            continue
        raw,usage,finish=completed if p is not None else ('ABSTAIN',None,None)
        expected=dict(replicate=replicate,seed=seed,order_seed=order_seed,task_id=task['task_id'],stratum=task['stratum'],raw_output=raw,usage=usage,finish_reason=finish,model_calls=int(p is not None),score=gate.score(raw,task,gate.prepared_for(task,'candidate')))
        if rows[index]!=expected or base.read(root/f'row-{index:03d}.json')!=expected:raise ValueError('row_changed')
    if base.digest(base.canonical(schedule).encode())!=reg['schedule_sha256']:raise ValueError('schedule_changed')
    if report['complete'] and sum(r['model_calls'] for r in rows)!=reg['max_logical_calls']:raise ValueError('logical_call_count_changed')
    result=summary(reg,rows,report['wall_seconds'],attempts,timeouts,report['complete'],report['error_type'],attempt_latencies);result['registration_sha256']=binding
    if save:base.write(root/'aggregate.json',result)
    elif base.read(root/'aggregate.json')!=result:raise ValueError('aggregate_changed')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['register','run','verify']);p.add_argument('--directory',type=Path,required=True);p.add_argument('--input',type=Path);p.add_argument('--bank-manifest',type=Path);p.add_argument('--prior',type=Path);a=p.parse_args()
    result=register(a.directory,a.input,a.bank_manifest,a.prior) if a.mode=='register' else globals()[a.mode](a.directory)
    print(json.dumps(result,sort_keys=True,indent=2))
if __name__=='__main__':main()
