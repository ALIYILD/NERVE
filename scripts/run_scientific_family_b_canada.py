#!/usr/bin/env python3
"""Registered Runpod-only adapted-pipeline study; private journals, aggregate output."""
import argparse
from collections import Counter
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import socket
import statistics
import time
import urllib.error
import scientific_attended_canada_transport as transport
import run_scientific_family_b_study as previous
from nerve_awim.memory_gateway import scientific_family_b_adapter as adapter
from nerve_awim.memory_gateway import scientific_task_bank_v3 as bank
from nerve_awim.memory_gateway.scientific_task_bank import RULES
from nerve_awim.memory_gateway.scientific_candidate_execution import ABSTAIN

ROOT=Path(__file__).resolve().parents[1]
VERSION='registered-family-b-canada-v1'
WRAPUP=datetime.fromisoformat('2026-10-16T10:15:00+00:00')
SEED=20261016
SOURCES=['docs/galahad/evidence/family-b-attended-protocol-v3.json','docs/galahad/evidence/overnight-protected-paths.json','scripts/run_scientific_family_b_study.py','scripts/run_scientific_family_b_extended_window.py','scripts/run_scientific_family_b_canada.py','scripts/scientific_attended_canada_transport.py','scripts/attended_canada_stage.sh','scripts/bootstrap_attended_canada.sh','docs/galahad/evidence/attended-canada-amendment.json','scripts/run_scientific_runpod_gate.py','scripts/scientific_attended_replacement_transport.py',
         'src/nerve_awim/memory_gateway/scientific_family_b_adapter.py','src/nerve_awim/memory_gateway/scientific_task_bank_v3.py',
         'src/nerve_awim/memory_gateway/scientific_task_bank.py','src/nerve_awim/memory_gateway/scientific_structured_tasks.py',
         'src/nerve_awim/memory_gateway/scientific_candidate_v3.py','src/nerve_awim/memory_gateway/scientific_candidate_execution.py',
         'src/nerve_awim/memory_gateway/scientific_compact_dev_transport.py']
canonical=transport.canonical
read=transport.read
write=transport.write
hashbytes=transport.digest


def pins(extra=None,names=None):
    protected=read(ROOT/'docs/galahad/evidence/overnight-protected-paths.json')['paths']
    if any(hashbytes((ROOT/p).read_bytes())!=h for p,h in protected.items()):raise ValueError('degraded_integrity')
    if names is None:names=list(dict.fromkeys(SOURCES+list(protected)+[str(p.relative_to(ROOT)) for p in sorted((ROOT/'src').rglob('*.py'))]+([extra] if extra else [])))
    return {p:hashbytes((ROOT/p).read_bytes()) for p in names}


def custom_module(path):
    spec=importlib.util.spec_from_file_location('registered_family_b_candidate',ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def prepare(task,arm,extra=None):
    if arm=='candidate':return custom_module(extra).prepare(task['query'],task['evidence'])
    return adapter.prepare(task['query'],task['evidence'],'adapted_bootstrap' if arm=='adapted_bootstrap' else 'adapted_v1')


def schedule(tasks,arms,extra=None,kind=None):
    result=[]
    for task in tasks:
        for arm in arms:
            p=prepare(task,arm,extra);payload=None
            if arm not in ('always_abstain','random') and p['route']=='model':
                payload={'model':transport.MODEL,'temperature':0,'seed':SEED,'stream':False,'max_tokens':128,
                         'messages':[{'role':'system','content':p['system']},{'role':'user','content':p['user']}]}
                if len(p['user'].encode())>32768:raise ValueError('prompt_byte_cap')
                if p['schema'] is not None:payload['response_format']={'type':'json_schema','json_schema':{'name':'scientific_measurement','strict':True,'schema':p['schema']}}
            result.append({'task_id':task['task_id'],'arm':arm,'payload':payload,'prepared_sha256':hashbytes(canonical(p).encode())})
    if kind=='calibration':return sorted(result,key=lambda row:(-len(canonical(row['payload']).encode()),row['task_id']))
    return sorted(result,key=lambda row:sha256(f"{SEED}:{row['task_id']}:{row['arm']}".encode()).hexdigest())


def score(raw,task,p):
    try:
        decoded=dict(ABSTAIN) if raw=='ABSTAIN' and p.get('_control') else adapter.decode(raw,p);valid=True
    except (ValueError,TypeError,KeyError,OverflowError):decoded=dict(ABSTAIN);valid=False
    expected=task['expected'];answer=valid and decoded['status']=='answer';abstain=valid and decoded['status']=='abstain'
    strict=valid and decoded['status']==expected['status']
    if strict and answer:
        strict=all(decoded[k]==expected[k] for k in ('entity','measurement','unit','source_id')) and Decimal(decoded['value'])==Decimal(expected['value'])
    domain=False
    if answer:
        source=next((r for r in p['records'] if r['source_id']==decoded['source_id']),None)
        domain=source is None or decoded['unit']!=source['unit'] or Decimal(decoded['value'])!=Decimal(source['value'])
    label=None
    if not strict:
        if not valid:label='format_invalid'
        elif abstain:label='abstained_when_answerable'
        elif answer and source is not None and not source['current']:label='stale_selected'
        elif expected['status']=='abstain':label='conflict_not_detected' if p['gate_reason']=='conflict' else 'answered_when_should_abstain'
        elif decoded['entity']!=expected['entity'] or decoded['measurement']!=expected['measurement']:label='decoy_selected'
        elif decoded['unit']!=expected['unit']:label='wrong_unit'
        elif Decimal(decoded['value'])!=Decimal(expected['value']):label='wrong_value'
        elif decoded['source_id']!=expected['source_id']:label='wrong_provenance'
    return {'strict_correct':bool(strict),'format_valid':valid,'answer_status':decoded['status'] if valid else 'invalid',
            'wrong_answer':bool(answer and not strict),'false_abstention':bool(abstain and expected['status']=='answer'),
            'domain_violation':bool(domain),'diagnosis':label}


def control_raw(task,arm,p):
    if arm=='always_abstain' or arm not in ('random',) and p['route']=='deterministic_abstention':return 'ABSTAIN'
    value=int(sha256((task['task_id']+':random:'+str(SEED)).encode()).hexdigest(),16)
    if value%4==0:return 'ABSTAIN'
    record=p['records'][value%len(p['records'])]
    return canonical({'value':float(Decimal(record['value'])),'unit':record['unit'],'source_id':record['source_id']})


def control_prepared(p,arm):
    if arm in ('always_abstain','random'):return dict(p,arm='adapted_bootstrap' if arm=='always_abstain' else 'adapted_v1',route='model',_control=arm)
    return p


def require_shared_budget(budget,calreg,protocolsha):
    if str(budget.resolve())!=calreg['budget_directory']:raise ValueError('shared_physical_budget_required')
    if calreg['protocol_sha256']!=protocolsha:raise ValueError('calibration_protocol_changed')


def require_exact_development_candidate(priorreg,extra,protocolsha):
    if not extra or priorreg['kind']!='dev' or priorreg['candidate_module']!=extra or priorreg['sources'].get(extra)!=hashbytes((ROOT/extra).read_bytes()) or priorreg['protocol_sha256']!=protocolsha:raise ValueError('exact_dev_candidate_required')


def study_wall_budget(kind,extra,parent=None):
    if kind=='calibration':return 1800
    if kind=='holdout':
        used=parent['wall_seconds']
        if not isinstance(used,(int,float)) or not 0<=used<3600:raise ValueError('L6_wall_budget_exhausted')
        return 3600-used
    return 3600


def register(root,kind,bankroot,protocol,calibration,budget,extra=None,prior=None,running_start=None,prior_running_seconds=None):
    amendment=read(ROOT/'docs/galahad/evidence/attended-canada-amendment.json')
    if amendment.get('authorized') is not True:raise ValueError('duration_amendment_requires_user_authorization')
    if str(budget.resolve())!='/root/nerve-attended-budget':raise ValueError('shared_physical_budget_required')
    for name,digest in amendment['prior_claim_sha256'].items():
        if hashbytes((budget/name).read_bytes())!=digest:raise ValueError('prior_physical_claim_changed')
    if prior_running_seconds!=amendment['prior_running_seconds']:raise ValueError('prior_running_budget_changed')
    if kind=='calibration' and len(list(budget.glob('call-*.json')))!=5:raise ValueError('fresh_calibration_once_only')
    if root.exists():raise ValueError('study_directory_exists')
    if extra and (Path(extra).is_absolute() or '..' in Path(extra).parts or not extra.startswith('src/nerve_awim/memory_gateway/')):raise ValueError('registered_candidate_module_path_required')
    if running_start is None or type(prior_running_seconds) not in (int,float) or not 0<=prior_running_seconds<21600:raise ValueError('verified_running_budget_required')
    started=datetime.fromisoformat(running_start.replace('Z','+00:00'));now=datetime.now(timezone.utc)
    if started.tzinfo is None or started>now+timedelta(seconds=5):raise ValueError('provider_start_required')
    deadline=min(started+timedelta(seconds=21600-prior_running_seconds),WRAPUP)
    if now>=deadline:raise ValueError('running_budget_exhausted')
    identity=transport.identity();protocolsha=hashbytes(protocol.read_bytes());manifest=None;parent=None
    if kind=='calibration':
        if extra:raise ValueError('calibration_no_candidate')
        pool=[bank.item(bytes(32),'dev','multi-source-agreement',1000+i) for i in range(100)]
        tasks=sorted(pool,key=lambda task:(-len(adapter.prepare(task['query'],task['evidence'],'adapted_v1')['user'].encode()),task['task_id']))[:5];arms=['adapted_v1'];timeout=120.0
    else:
        manifest=read(bankroot/'manifest.json');seal=read(bankroot/'sealing-receipt.json')
        if seal['manifest_sha256']!=hashbytes((bankroot/'manifest.json').read_bytes()) or not seal['sealed']:raise ValueError('sealed_bank_required')
        if manifest['protocol_sha256']!=protocolsha:raise ValueError('bank_protocol_changed')
        if amendment['sealed_bank_manifest_sha256']!=seal['manifest_sha256']:raise ValueError('amendment_bank_binding_changed')
        cal=verify(calibration)
        if not cal['complete'] or cal['attempts']!=5 or cal['timeouts']!=0:raise ValueError('calibration_incomplete')
        calreg=read(calibration/'registration.json')
        require_shared_budget(budget,calreg,protocolsha)
        timeout=3*max(cal['attempt_latencies_seconds'])
        arms=['candidate','adapted_v1','always_abstain','random'] if extra else ['adapted_v1','adapted_bootstrap','always_abstain','random']
        if extra:
            parent=verify(prior)
            if parent['bank_manifest_sha256']!=seal['manifest_sha256'] or not parent['complete']:raise ValueError('verified_same_bank_parent_required')
        if extra and kind=='dev' and parent['verdict']!='exploratory_failures':raise ValueError('failure_supported_design_required')
        if kind=='holdout':
            priorreg=read(prior/'registration.json')
            require_exact_development_candidate(priorreg,extra,protocolsha)
            if not extra or parent['verdict']!='holdout_eligible':raise ValueError('eligible_development_required')
            if study_wall_budget(kind,extra,parent)<=3*timeout:raise ValueError('L6_wall_budget_exhausted')
            write(bankroot/'slice1-consumed.json',{'consumed_at_utc':datetime.now(timezone.utc).isoformat(),'candidate_sha256':hashbytes((ROOT/extra).read_bytes()),'dev_aggregate_sha256':hashbytes((prior/'aggregate.json').read_bytes())})
            path=bankroot/'slice1.json';path.chmod(0o400)
            try:raw=path.read_bytes()
            finally:path.chmod(0)
            if hashbytes(raw)!=manifest['slices'][0]['sha256']:raise ValueError('sealed_slice_changed')
        else:
            raw=(bankroot/'dev.json').read_bytes()
            if hashbytes(raw)!=manifest['files']['dev']:raise ValueError('dev_changed')
        tasks=json.loads(raw)
    if kind=='dev' and (len(tasks)!=900 or Counter(t['stratum'] for t in tasks)!=Counter({s:100 for s in bank.STRATA})):raise ValueError('dev900_required')
    if kind=='holdout' and len(tasks)!=100:raise ValueError('slice100_required')
    root.mkdir(mode=0o700);budget.mkdir(mode=0o700,exist_ok=True)
    write(root/'private-input.json',tasks);inputsha=hashbytes((root/'private-input.json').read_bytes());entries=schedule(tasks,arms,extra,kind)
    reg={'version':VERSION,'kind':kind,'created_at_utc':datetime.now(timezone.utc).isoformat(),'identity':identity,'protocol_sha256':protocolsha,
         'sources':pins(extra),'duration_amendment_sha256':hashbytes((ROOT/'docs/galahad/evidence/attended-canada-amendment.json').read_bytes()),'candidate_module':extra,'input_sha256':inputsha,'arms':arms,'task_count':len(tasks),'rows':len(entries),
         'schedule_sha256':hashbytes(canonical(entries).encode()),'seed':SEED,'timeout_seconds':timeout,'retry_limit':2,'retry_on':'timeout_only_identical_request',
         'budget_directory':str(budget.resolve()),'physical_attempt_cap':6000,'absolute_deadline_utc':deadline.isoformat(),'provider_running_start_utc':running_start,'prior_running_seconds':prior_running_seconds,'max_study_wall_seconds':study_wall_budget(kind,extra,parent),'L6_prior_study_wall_seconds':parent['wall_seconds'] if kind=='holdout' else 0,
         'bank_manifest_sha256':hashbytes((bankroot/'manifest.json').read_bytes()) if manifest else None,'calibration_registration_sha256':hashbytes((calibration/'registration.json').read_bytes()) if kind!='calibration' else None,
         'prior_aggregate_sha256':hashbytes((prior/'aggregate.json').read_bytes()) if prior else None,'hourly_usd':0.59,'promotion_authorized':False,'holdout_item_exports':False,
         'max_logical_calls':sum(e['payload'] is not None for e in entries),'prompt_token_cap':4096,'max_output_tokens':128,
         'inference_substrate':'Runpod Linux identity enforced; no laptop inference','acceptance':'exploratory L4; candidate dev nonregression everystratum+strictgain+zero domainviolations; holdout strictgain vs all3controls+nonregression vs adapted_v1+zero domainviolations'}
    write(root/'registration.json',reg)
    return {'registered':True,'registration_sha256':hashbytes((root/'registration.json').read_bytes()),'kind':kind,'rows':len(entries),'max_logical_calls':reg['max_logical_calls'],'timeout_seconds':timeout,'bank_manifest_sha256':reg['bank_manifest_sha256']}


def attempt(root,index,entry,reg):
    body=canonical(entry['payload']).encode();envelope={'url':transport.ORIGIN+'/v1/chat/completions','method':'POST','headers':{'Content-Type':'application/json'},'body':body.decode()}
    for n in range(3):
        if pins(names=reg['sources'])!=reg['sources']:raise ValueError('source_changed_before_attempt')
        if datetime.now(timezone.utc).timestamp()+3*reg['timeout_seconds']>=datetime.fromisoformat(reg['absolute_deadline_utc']).timestamp():raise TimeoutError('absolute_budget')
        budget=Path(reg['budget_directory']);count=len(list(budget.glob('call-*.json')))
        if count>=reg['physical_attempt_cap']:raise RuntimeError('physical_call_budget')
        claim={'registration_sha256':hashbytes((root/'registration.json').read_bytes()),'entry_index':index,'attempt':n,'request_sha256':hashbytes(canonical(envelope).encode())}
        write(budget/f'call-{count:05d}.json',claim)
        name=f'attempt-{index:04d}-{n}';write(root/(name+'-claim.json'),dict(claim,request=envelope,timeout_seconds=reg['timeout_seconds']))
        start=time.monotonic()
        try:wire=transport.network('/v1/chat/completions',body,reg['timeout_seconds'])
        except Exception as error:
            timeout=isinstance(error,(TimeoutError,socket.timeout)) or isinstance(error,urllib.error.URLError) and isinstance(error.reason,(TimeoutError,socket.timeout))
            write(root/(name+'-result.json'),{'status':'timeout' if timeout else 'error','elapsed_seconds':time.monotonic()-start,'error_type':type(error).__name__})
            if not timeout or n==2:raise
        else:
            write(root/(name+'-result.json'),{'status':'complete','elapsed_seconds':time.monotonic()-start,'wire':wire.decode()})
            raw,usage,finish=transport.decode(wire)
            if usage['prompt_tokens']>reg['prompt_token_cap']:raise ValueError('observed_prompt_token_cap')
            return raw,usage,finish


def run(root):
    reg=read(root/'registration.json')
    if pins(names=reg['sources'])!=reg['sources'] or transport.identity()!=reg['identity']:raise ValueError('registered_identity_changed')
    tasks=read(root/'private-input.json');entries=schedule(tasks,reg['arms'],reg['candidate_module'],reg['kind']);lookup={t['task_id']:t for t in tasks}
    if hashbytes((root/'private-input.json').read_bytes())!=reg['input_sha256'] or hashbytes(canonical(entries).encode())!=reg['schedule_sha256']:raise ValueError('schedule_changed')
    write(root/'consumed.json',{'registration_sha256':hashbytes((root/'registration.json').read_bytes())});start=time.monotonic();rows=[];error=None
    try:
        for index,entry in enumerate(entries):
            if time.monotonic()-start+3*reg['timeout_seconds']>reg['max_study_wall_seconds']:raise TimeoutError('study_wall_budget')
            task=lookup[entry['task_id']];p=control_prepared(prepare(task,entry['arm'],reg['candidate_module']),entry['arm']);usage=None;finish=None
            if entry['payload'] is not None:raw,usage,finish=attempt(root,index,entry,reg)
            else:raw=control_raw(task,entry['arm'],p)
            row={'task_id':entry['task_id'],'arm':entry['arm'],'stratum':task['stratum'],'raw_output':raw,'usage':usage,'finish_reason':finish,'score':score(raw,task,p),'model_calls':int(entry['payload'] is not None)}
            write(root/f'row-{index:04d}.json',row);rows.append(row)
        if transport.identity()!=reg['identity'] or pins(names=reg['sources'])!=reg['sources']:raise ValueError('end_identity_changed')
    except Exception as exc:error=type(exc).__name__+':'+str(exc)
    write(root/'private-report.json',{'registration_sha256':hashbytes((root/'registration.json').read_bytes()),'rows':rows,'complete':error is None,'error':error,'wall_seconds':time.monotonic()-start})
    result=verify(root,save=True);return result


def aggregate(reg,rows,report,latencies,timeouts,attempts):
    tables={}
    for arm in reg['arms']:
        tables[arm]={}
        for st in bank.STRATA:
            chosen=[r for r in rows if r['arm']==arm and r['stratum']==st];k=sum(r['score']['strict_correct'] for r in chosen)
            tables[arm][st]={'n':len(chosen),'correct':k,'ci95':transport.wilson(k,len(chosen)),
                'wrong_answers':sum(r['score']['wrong_answer'] for r in chosen),'false_abstentions':sum(r['score']['false_abstention'] for r in chosen),
                'domain_violations':sum(r['score']['domain_violation'] for r in chosen),'format_invalid':sum(not r['score']['format_valid'] for r in chosen),
                'diagnoses':dict(Counter(r['score']['diagnosis'] for r in chosen if r['score']['diagnosis']))}
    complete=report['complete'] and len(rows)==reg['rows'];totals={arm:sum(t['correct'] for t in strata.values()) for arm,strata in tables.items()}
    verdict='incomplete_infrastructure'
    if complete:
        if reg['kind']=='calibration':verdict='exploratory_latency_calibration_complete'
        elif not reg['candidate_module']:verdict='bank_v3_saturated' if totals['adapted_v1']==reg['task_count'] else 'exploratory_failures'
        else:
            nonregression=all(tables['candidate'][s]['correct']>=tables['adapted_v1'][s]['correct'] for s in bank.STRATA)
            domain=sum(t['domain_violations'] for t in tables['candidate'].values())==0
            passes=nonregression and domain and totals['candidate']>totals['adapted_v1']
            if reg['kind']=='holdout':passes=passes and all(totals['candidate']>totals[a] for a in ('always_abstain','random'))
            verdict=('promote_proposal' if reg['kind']=='holdout' else 'holdout_eligible') if passes else 'retain_incumbent'
    return {'version':VERSION,'kind':reg['kind'],'complete':complete,'verdict':verdict,'registration_sha256':report['registration_sha256'],
            'bank_manifest_sha256':reg['bank_manifest_sha256'],'identity':reg['identity'],'tables':tables,'totals':totals,'attempts':attempts,'timeouts':timeouts,
            'logical_model_calls':sum(r['model_calls'] for r in rows),'tokens':{k:sum(r['usage'][k] for r in rows if r['usage']) for k in ('prompt_tokens','completion_tokens','total_tokens')},'attempt_latencies_seconds':latencies if reg['kind']=='calibration' else None,'latency_summary_seconds':{'n':len(latencies),'median':statistics.median(latencies) if latencies else None,'max':max(latencies) if latencies else None},'wall_seconds':report['wall_seconds'],
            'allocated_compute_estimate_usd':report['wall_seconds']*.59/3600,'cost_note':'Study allocation only; total running/idle recorded separately; not invoice.',
            'error':report['error'],'promotion_authorized':False,'item_level_exported':False,'model_weights_changed':False,
            'robustness':'n/a single seed','UX':'n/a','comparison':'adapted pipelines, not unchanged retained skill v1'}


def verify(root,save=False):
    reg=read(root/'registration.json');report=read(root/'private-report.json');tasks=read(root/'private-input.json');entries=schedule(tasks,reg['arms'],reg['candidate_module'],reg['kind']);lookup={t['task_id']:t for t in tasks}
    binding=hashbytes((root/'registration.json').read_bytes())
    if pins(names=reg['sources'])!=reg['sources'] or report['registration_sha256']!=binding or read(root/'consumed.json')['registration_sha256']!=binding or hashbytes((root/'private-input.json').read_bytes())!=reg['input_sha256'] or hashbytes(canonical(entries).encode())!=reg['schedule_sha256']:raise ValueError('replay_binding_changed')
    rows=report['rows'];latencies=[];timeouts=0;attempts=0
    if not isinstance(report['wall_seconds'],(int,float)) or not 0<=report['wall_seconds']<=reg['max_study_wall_seconds']:raise ValueError('invalid_wall_seconds')
    if len(rows)>len(entries) or report['complete'] and len(rows)!=len(entries):raise ValueError('invalid_row_count')
    for index,entry in enumerate(entries):
        claims=sorted(root.glob(f'attempt-{index:04d}-*-claim.json'));completed=None
        if len(claims)>3 or claims and entry['payload'] is None or claims and index>len(rows):raise ValueError('invalid_attempt_sequence')
        for n,path in enumerate(claims):
            if path.name!=f'attempt-{index:04d}-{n}-claim.json':raise ValueError('attempt_gap')
            claim=read(path);envelope={'url':transport.ORIGIN+'/v1/chat/completions','method':'POST','headers':{'Content-Type':'application/json'},'body':canonical(entry['payload'])}
            if claim['request']!=envelope or claim['request_sha256']!=hashbytes(canonical(envelope).encode()) or claim['registration_sha256']!=binding or claim['timeout_seconds']!=reg['timeout_seconds']:raise ValueError('request_changed')
            result=read(root/f'attempt-{index:04d}-{n}-result.json');attempts+=1;timeouts+=int(result['status']=='timeout');latencies.append(result['elapsed_seconds'])
            if result['status'] not in ('complete','timeout','error') or not isinstance(result['elapsed_seconds'],(int,float)) or not 0<=result['elapsed_seconds']<7200:raise ValueError('invalid_attempt_result')
            if n<len(claims)-1 and result['status']!='timeout':raise ValueError('non_timeout_retry')
            if result['status']=='complete':completed=transport.decode(result['wire'])
        if index>=len(rows):continue
        task=lookup[entry['task_id']];p=control_prepared(prepare(task,entry['arm'],reg['candidate_module']),entry['arm'])
        raw,usage,finish=completed if entry['payload'] is not None else (control_raw(task,entry['arm'],p),None,None)
        expected={'task_id':entry['task_id'],'arm':entry['arm'],'stratum':task['stratum'],'raw_output':raw,'usage':usage,'finish_reason':finish,'score':score(raw,task,p),'model_calls':int(entry['payload'] is not None)}
        if expected!=rows[index] or expected!=read(root/f'row-{index:04d}.json'):raise ValueError('row_changed')
    result=aggregate(reg,rows,report,latencies,timeouts,attempts)
    if save:write(root/'aggregate.json',result)
    elif result!=read(root/'aggregate.json'):raise ValueError('aggregate_changed')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('register','run','verify'));parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--kind',choices=('calibration','dev','holdout'));parser.add_argument('--bank',type=Path);parser.add_argument('--protocol',type=Path);parser.add_argument('--calibration',type=Path);parser.add_argument('--budget',type=Path);parser.add_argument('--candidate-module');parser.add_argument('--prior',type=Path);parser.add_argument('--running-start-utc');parser.add_argument('--prior-running-seconds',type=float);args=parser.parse_args()
    result=register(args.directory,args.kind,args.bank,args.protocol,args.calibration,args.budget,args.candidate_module,args.prior,args.running_start_utc,args.prior_running_seconds) if args.mode=='register' else globals()[args.mode](args.directory)
    print(json.dumps(result,sort_keys=True,indent=2))
