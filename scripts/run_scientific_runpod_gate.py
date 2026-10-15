#!/usr/bin/env python3
"""Versioned private Runpod gate. Register before run; aggregate-only output.

The only network operation allowed is the pod's loopback Ollama service; a Linux
Runpod identity is mandatory. Local replay/testing never calls the network.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from nerve_awim.memory_gateway import scientific_candidate_v3_study as gate

VERSION='scientific-runpod-slice2-v1'
MODEL='qwen2.5-coder:7b'
DIGEST='dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364'
POD='lg0svvuenxvbno'
ORIGIN='http://127.0.0.1:11434'

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(b): return hashlib.sha256(b).hexdigest()
def read(p): return json.loads(Path(p).read_bytes())
def write(p,x):
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        f.write(canonical(x)+'\n');f.flush();os.fsync(f.fileno())
def network(path,body=None,timeout=30):
    if platform.system()!='Linux' or os.environ.get('RUNPOD_POD_ID')!=POD:
        raise RuntimeError('inference_requires_registered_runpod')
    req=urllib.request.Request(ORIGIN+path,data=body,headers={'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as response:
        raw=response.read(1000001)
    if len(raw)>1000000: raise ValueError('oversize_response')
    return raw

def identity():
    m=next(m for m in json.loads(network('/api/tags'))['models'] if m['name']==MODEL)
    if m['digest']!=DIGEST: raise ValueError('model_changed')
    runtime=json.loads(network('/api/version'))
    if runtime!={'version':'0.40.5'}:raise ValueError('runtime_changed')
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True).strip()
    if gpu not in ('NVIDIA A40','A40'):raise ValueError('gpu_changed')
    return {'pod_id':POD,'gpu':gpu,'model':MODEL,'model_digest':DIGEST,'runtime':runtime}

def pins():
    root=Path(__file__).resolve().parents[1]
    return {str(p.relative_to(root)):digest(p.read_bytes()) for p in [Path(__file__).resolve(),*sorted((root/'src').rglob('*.py'))]}

def plan(tasks):
    if len(tasks)!=100 or len({t['task_id'] for t in tasks})!=100 or Counter(t['stratum'] for t in tasks)!=Counter({s:20 for s in gate.STRATA}):
        raise ValueError('fixed_100_item_roster_required')
    lookup={t['task_id']:t for t in tasks};entries=[]
    for tid,arm in gate.schedule(tasks):
        task=lookup[tid];p=gate.prepared_for(task,arm);route=gate._route(task,arm);payload=None
        if route=='model':
            payload=dict(model=MODEL,temperature=0,seed=20261015,stream=False,max_tokens=128,messages=[{'role':'system','content':p['system']},{'role':'user','content':p['user']}])
            if p['schema'] is not None:
                payload['response_format']={'type':'json_schema','json_schema':{'name':'scientific_measurement','strict':True,'schema':p['schema']}}
        entries.append(dict(task_id=tid,arm=arm,route=route,payload=payload,prepared_sha256=gate._hash(p)))
    if sum(e['route']=='model' for e in entries)!=160:raise ValueError('call_budget_changed')
    return entries

def decode(wire):
    value=json.loads(wire)
    if value['model']!=MODEL or len(value['choices'])!=1:raise ValueError('response_identity')
    c=value['choices'][0];m=c['message'];raw=m['content']
    if c['finish_reason'] not in ('stop','length') or m['role']!='assistant' or m.get('tool_calls') or m.get('function_call') or not isinstance(raw,str) or not 0<len(raw)<=16384:raise ValueError('response_contract')
    usage={k:value['usage'][k] for k in ('prompt_tokens','completion_tokens','total_tokens')};gate._usage(usage)
    return raw,usage,c['finish_reason']

def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]

def aggregate(rows,complete):
    arms={}
    for arm in gate.ARMS:
        arms[arm]={}
        for s in gate.STRATA:
            subset=[r for r in rows if r['arm']==arm and r['stratum']==s];k=sum(r['score']['strict_correct'] for r in subset)
            arms[arm][s]={'n':len(subset),'strict_correct':k,'strict_ci95':wilson(k,len(subset)),'format_valid':sum(r['score']['schema_valid'] is True for r in subset)}
    totals={a:sum(v['strict_correct'] for v in strata.values()) for a,strata in arms.items()}
    full=complete and all(v['n']==20 for strata in arms.values() for v in strata.values())
    passed=full and all(totals['candidate']>totals[a] for a in ('baseline','always_abstain','random')) and all(arms['candidate'][s]['strict_correct']>=arms['always_abstain'][s]['strict_correct'] for s in gate.STRATA)
    return dict(arms=arms,verdict=('promote_proposal' if passed else 'retain_incumbent') if full else 'incomplete_infrastructure',complete=full,promotion_authorized=False,item_level_evidence_exported=False)

def register(root,kind,reference,manifest,dry=None):
    if kind not in ('dry','slice2'):raise ValueError('study_kind_required')
    ref=read(reference/'registration.json');report=read(reference/'receipt/report.json')
    if report['status']!='complete' or len(report['rows'])!=400 or report['model_calls']!=160:raise ValueError('complete_reference_required')
    if report['registration_sha256']!=digest((reference/'registration.json').read_bytes()):raise ValueError('reference_binding_changed')
    checkout=Path(__file__).resolve().parents[1]
    for name,sha in ref['sources'].items():
        if name.startswith('source/src/') and digest((checkout/name.removeprefix('source/')).read_bytes())!=sha:raise ValueError('development_source_changed')
    partition=read(reference/'partition-preregistration.json')
    actual_manifest=read(manifest)
    if actual_manifest['name']!='slice2' or digest(manifest.read_bytes())!=partition['slices']['slice2']['manifest_sha256']:raise ValueError('original_slice2_manifest_required')
    maximum=max(r['elapsed_seconds'] for r in report['rows'] if r['model_calls'])
    if not math.isfinite(maximum) or maximum<=0:raise ValueError('invalid_latency')
    if ref['identity']['model']['digest']!=DIGEST or ref['seed']!=20261015:raise ValueError('dev_reference_changed')
    if kind=='dry':
        inputs=read(reference/'dev-input.json');tasks=inputs['tasks']
        if any(t['split']!='dev' for t in tasks) or plan(tasks)!=ref['schedule']:raise ValueError('exact_dev_configuration_required')
    else:
        result=verify(dry)
        if not result['dry_admission_passed']:raise ValueError('dry_not_qualified')
        dr=read(dry/'registration.json')
        if dr['sources']!=pins() or dr['identity']!=identity():raise ValueError('dry_binding_changed')
    root.mkdir(mode=0o700)
    reg=dict(version=VERSION,kind=kind,identity=identity(),sources=pins(),reference_registration_sha256=digest((reference/'registration.json').read_bytes()),reference_report_sha256=digest((reference/'receipt/report.json').read_bytes()),seed=20261015,timeout_seconds=3*maximum,measured_runpod_max_latency_seconds=maximum,retries=2,retry_on='timeout_only; identical URL/method/headers/body; first completed response',max_wall_seconds=7200,max_logical_calls=160,max_physical_attempts=480,hourly_usd=0.59,price_source='Runpod list_pods live read 2026-10-15; cost field',cost_method='allocated wall_seconds * hourly_usd / 3600; estimate, not invoice',acceptance='complete 400 rows; candidate strict total beats each control; candidate in each stratum >= always_abstain',interval='95% Wilson marginal descriptive, no multiplicity correction',promotion_authorized=False,manifest=read(manifest),manifest_sha256=digest(manifest.read_bytes()),dry_registration_sha256=digest((dry/'registration.json').read_bytes()) if dry else None,dry_aggregate_sha256=digest((dry/'aggregate.json').read_bytes()) if dry else None)
    if kind=='dry':
        write(root/'private-input.json',tasks);reg['input_sha256']=digest((root/'private-input.json').read_bytes())
    else:reg['input_sha256']=reg['manifest']['content_sha256']
    write(root/'registration.json',reg)
    return {'registered':kind,'registration_sha256':digest((root/'registration.json').read_bytes()),'timeout_seconds':reg['timeout_seconds']}

def attempt(root,index,payload,timeout):
    body=canonical(payload).encode();envelope={'url':ORIGIN+'/v1/chat/completions','method':'POST','headers':{'Content-Type':'application/json'},'body':body.decode()};request_hash=digest(canonical(envelope).encode())
    for number in range(3):
        name=f'attempt-{index:03d}-{number}';write(root/(name+'-claim.json'),dict(request=envelope,request_sha256=request_hash,timeout_seconds=timeout))
        started=time.monotonic()
        try:wire=network('/v1/chat/completions',body,timeout)
        except Exception as error:
            is_timeout=isinstance(error,(TimeoutError,socket.timeout)) or isinstance(error,urllib.error.URLError) and isinstance(error.reason,(TimeoutError,socket.timeout))
            write(root/(name+'-result.json'),dict(status='timeout' if is_timeout else 'error',elapsed_seconds=time.monotonic()-started,error_type=type(error).__name__))
            if not is_timeout or number==2:raise
        else:
            write(root/(name+'-result.json'),dict(status='complete',elapsed_seconds=time.monotonic()-started,wire=wire.decode()))
            return decode(wire)

def run(root):
    reg=read(root/'registration.json')
    if pins()!=reg['sources'] or identity()!=reg['identity']:raise ValueError('registration_changed')
    raw=(root/'private-input.json').read_bytes()
    if digest(raw)!=reg['input_sha256']:raise ValueError('input_changed')
    tasks=json.loads(raw);entries=plan(tasks);lookup={t['task_id']:t for t in tasks}
    write(root/'consumed.json',{'registration_sha256':digest((root/'registration.json').read_bytes())})
    start=time.monotonic();rows=[];failure=None
    try:
        for index,e in enumerate(entries):
            if time.monotonic()-start+3*reg['timeout_seconds']>reg['max_wall_seconds']:raise TimeoutError('wall_budget')
            task=lookup[e['task_id']];prepared=gate.prepared_for(task,e['arm']);usage=None;finish=None
            if e['route']=='model':raw,usage,finish=attempt(root,index,e['payload'],reg['timeout_seconds'])
            else:raw=gate._random_raw(task,prepared) if e['arm']=='random' else 'ABSTAIN'
            row=dict(task_id=e['task_id'],arm=e['arm'],stratum=task['stratum'],raw_output=raw,usage=usage,finish_reason=finish,model_calls=int(e['route']=='model'),score=gate.score(raw,task,prepared))
            write(root/f'row-{index:03d}.json',row);rows.append(row)
        if identity()!=reg['identity'] or pins()!=reg['sources']:raise ValueError('identity_changed')
    except Exception as error:failure=type(error).__name__
    elapsed=time.monotonic()-start
    report={'rows':rows,'complete':failure is None,'error_type':failure,'wall_seconds':elapsed,'registration_sha256':digest((root/'registration.json').read_bytes())}
    write(root/'private-report.json',report)
    result=verify(root,save=True)
    return result

def verify(root,save=False):
    reg=read(root/'registration.json');report=read(root/'private-report.json');tasks=read(root/'private-input.json');entries=plan(tasks);lookup={t['task_id']:t for t in tasks}
    binding=digest((root/'registration.json').read_bytes())
    if pins()!=reg['sources'] or digest((root/'private-input.json').read_bytes())!=reg['input_sha256'] or report['registration_sha256']!=binding or read(root/'consumed.json')['registration_sha256']!=binding:raise ValueError('binding_changed')
    rows=report['rows'];attempts=0;timeouts=0
    if len(rows)>400 or report['complete'] and len(rows)!=400 or not math.isfinite(report['wall_seconds']) or not 0<=report['wall_seconds']<=reg['max_wall_seconds']:raise ValueError('invalid_terminal_report')
    for index,e in enumerate(entries):
        group=sorted(root.glob(f'attempt-{index:03d}-*-claim.json'))
        completed=None
        if len(group)>3:raise ValueError('retry_count')
        for number,path in enumerate(group):
            if path.name!=f'attempt-{index:03d}-{number}-claim.json' or e['route']!='model':raise ValueError('attempt_sequence')
            c=read(path);result=read(root/f'attempt-{index:03d}-{number}-result.json');attempts+=1;timeouts+=int(result['status']=='timeout')
            envelope={'url':ORIGIN+'/v1/chat/completions','method':'POST','headers':{'Content-Type':'application/json'},'body':canonical(e['payload'])}
            if c!={'request':envelope,'request_sha256':digest(canonical(envelope).encode()),'timeout_seconds':reg['timeout_seconds']}:raise ValueError('request_changed')
            if result['status'] not in ('complete','timeout','error') or not math.isfinite(result['elapsed_seconds']) or result['elapsed_seconds']<0:raise ValueError('invalid_attempt_status')
            if number<len(group)-1 and result['status']!='timeout':raise ValueError('non_timeout_retry')
            if result['status']=='complete':completed=decode(result['wire'])
        if index>=len(rows):
            if index>len(rows) and group:raise ValueError('unexpected_attempt')
            continue
        row=rows[index];task=lookup[e['task_id']];prepared=gate.prepared_for(task,e['arm'])
        raw,usage,finish=completed if e['route']=='model' else (gate._random_raw(task,prepared) if e['arm']=='random' else 'ABSTAIN',None,None)
        expected=dict(task_id=e['task_id'],arm=e['arm'],stratum=task['stratum'],raw_output=raw,usage=usage,finish_reason=finish,model_calls=int(e['route']=='model'),score=gate.score(raw,task,prepared))
        if row!=expected or row!=read(root/f'row-{index:03d}.json'):raise ValueError('row_changed')
    result=aggregate(rows,report['complete']);logical=sum(r['model_calls'] for r in rows)
    result.update(version=VERSION,kind=reg['kind'],identity=reg['identity'],wall_seconds=report['wall_seconds'],allocated_cost_estimate_usd=report['wall_seconds']*reg['hourly_usd']/3600,cost_method=reg['cost_method'],attempts=attempts,timeouts=timeouts,logical_model_calls=logical,error_type=report['error_type'],registration_sha256=binding,timeout_seconds=reg['timeout_seconds'],dry_admission_passed=reg['kind']=='dry' and result['complete'] and logical==attempts==160 and timeouts==0)
    if save:write(root/'aggregate.json',result)
    elif read(root/'aggregate.json')!=result:raise ValueError('aggregate_changed')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['register','run','verify']);p.add_argument('--directory',type=Path,required=True);p.add_argument('--kind',choices=['dry','slice2']);p.add_argument('--reference',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--dry',type=Path);a=p.parse_args()
    result=register(a.directory,a.kind,a.reference,a.manifest,a.dry) if a.mode=='register' else globals()[a.mode](a.directory)
    print(json.dumps(result,sort_keys=True,indent=2))
if __name__=='__main__':main()
