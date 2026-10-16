#!/usr/bin/env python3
"""Registered fresh B-v5 dev study: SSH-only inference, immutable receipts/replay.

Run requires W0's explicit preflight binding and a W2-owned shared pod-B lock.
Never opens reserve, edits consumption ledgers, starts pods or signs anything.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from nerve_awim.memory_gateway import overnight_autoresearch as engine
from nerve_awim.memory_gateway import scientific_family_b_v5 as v5
from run_v5_signed_gate_study import v5score
import run_scientific_family_b_v4_sweden as old
from run_bank_v5_dev_discrimination import remote

DIGEST='dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364'
MODULE='src/nerve_awim/memory_gateway/scientific_family_b_v4.py'
STRATA=('multi-source-agreement','format-variant-agreement')

def read(p):return json.loads(Path(p).read_text())
def filehash(p):return sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):engine.write_once(p,v)

def pins():
    paths=[Path(__file__),ROOT/'scripts/v5_remote_call.py',ROOT/'scripts/run_bank_v5_dev_discrimination.py',ROOT/'scripts/run_scientific_family_b_v4_sweden.py',ROOT/'scripts/run_v5_signed_gate_study.py']
    paths+=sorted((ROOT/'src/nerve_awim/memory_gateway').glob('scientific*.py'))
    paths += [ROOT/'src/nerve_awim/memory_gateway/overnight_autoresearch.py']
    return {str(p.relative_to(ROOT)):filehash(p) for p in paths}

def register(root,bank,previous):
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if list(root.iterdir()):raise ValueError('empty_study_directory_required')
    manifest=read(bank/'manifest.json')
    used={r['task_id'] for r in read(previous/'private-tasks.json')}
    tasks=[]
    for s in STRATA:
        path=bank/f'dev-{s}.json';mode=path.stat().st_mode&0o777
        try:
            path.chmod(0o400)
            if filehash(path)!=manifest['files'][path.name]['sha256']:raise ValueError('dev_bank_hash_changed')
            pool=read(path)
        finally:path.chmod(mode)
        fresh=[t for t in pool if t['task_id'] not in used]
        fresh.sort(key=lambda t:sha256(('2026101701:'+t['task_id']).encode()).hexdigest())
        if len(fresh)<50:raise ValueError('insufficient_fresh_dev_items')
        tasks.extend(fresh[:50])
    tasks.sort(key=lambda t:sha256(('2026101702:'+t['task_id']).encode()).hexdigest())
    if any(t['split']!='dev' for t in tasks):raise ValueError('dev_only')
    save(root/'tasks.json',tasks)
    protected=read(ROOT/'docs/galahad/evidence/overnight-protected-paths.json')['paths']
    for p,h in protected.items():
        if filehash(ROOT/p)!=h:raise ValueError('degraded_integrity')
    reg=dict(version='overnight-fresh-family-b-v5-v1',experiment_id='B-01',family='B',
        candidate='family-b-v5',incumbent='family-b-v4',seam='extraction-schema',
        hypothesis='Numeric-equivalence decision reduces observed agreement-stratum errors',
        failure_source_sha256=filehash(previous/'result.json'),
        fresh_relative_to= str(previous), prior_task_ids_sha256=engine.digest(sorted(used)),
        tasks_sha256=filehash(root/'tasks.json'),bank_manifest_sha256=filehash(bank/'manifest.json'),
        protected_sha256=protected,source_sha256=pins(),rule=engine.RULE,
        seed=20261016,control_seed=old.SEED,model='qwen2.5-coder:7b',model_digest=DIGEST,
        pod_id='5xndo7i7s5r9zn',runtime='0.40.5',gpu='NVIDIA A40',timeout_seconds=35,
        transport_retry='timeout_only_two_identical_resends',hourly_usd=.59,
        stratum_scope=list(STRATA),safety_scope='domain violations and abstention on these answerable agreement strata only',
        limitations='No negative safety strata; cannot establish general safety or D2 across entire family.',
        signed_gate=False,holdout_opened=False,promotion_authorized=False)
    save(root/'registration.json',reg)
    return dict(registration_sha256=filehash(root/'registration.json'),items=100)

def check(root):
    reg=read(root/'registration.json')
    if reg['rule']!=engine.RULE or reg['source_sha256']!=pins():raise ValueError('registered_source_changed')
    if filehash(root/'tasks.json')!=reg['tasks_sha256']:raise ValueError('task_schedule_changed')
    for p,h in reg['protected_sha256'].items():
        if filehash(ROOT/p)!=h:raise ValueError('degraded_integrity')
    return reg,read(root/'tasks.json')

def payload(t):return old.schedule([t],['candidate'],MODULE)[0]['payload']

def judgment(t,result):
    p=old.prepare(t,'candidate',MODULE)
    raw=old.transport.decode(result['wire'])[0]
    a=old.score(raw,t,p);b=v5score(v5.decide(t['query'],t['evidence']),t,p)
    controls={}
    for arm,key in [('always_abstain','always-abstain'),('random','random')]:
        c=old.control_prepared(p,arm)
        controls[key]=old.score(old.control_raw(t,arm,c),t,c)['strict_correct']
    return dict(task_id=t['task_id'],candidate=b['strict_correct'],incumbent=a['strict_correct'],
                safety_error=b['domain_violation'],**controls)

def replay(root):
    reg,tasks=check(root);rows=[]
    for i,t in enumerate(tasks):
        body=old.canonical(payload(t));files=sorted(root.glob(f'attempt-{i:03}-*.json'))
        if not 1<=len(files)<=3:raise ValueError('attempt_count')
        result=None
        for n,f in enumerate(files):
            if f.name!=f'attempt-{i:03}-{n}.json':raise ValueError('attempt_sequence')
            claim=read(root/f'claim-{i:03}-{n}.json')
            if claim!={'body_sha256':sha256(body.encode()).hexdigest(),'registration_sha256':filehash(root/'registration.json')}:raise ValueError('claim_changed')
            result=read(f)
            if n<len(files)-1 and result['status']!='timeout':raise ValueError('unregistered_retry')
        if result['status']!='ok':raise ValueError('incomplete_infrastructure')
        row=judgment(t,result)
        if row!=read(root/f'row-{i:03}.json'):raise ValueError('replay_mismatch')
        rows.append(row)
    result=dict(engine.decide(rows),registration_sha256=filehash(root/'registration.json'),
                rows_sha256=engine.digest(rows),new_model_calls=0,replay_verified=True)
    save(root/'replay.json',result)
    return result

def run(root,authorization,shared):
    reg,tasks=check(root);auth=read(authorization)
    if not(auth['authorized'] is True and auth['registration_sha256']==filehash(root/'registration.json')
           and auth['identity_replay_passed'] is True and auth['model_digest']==DIGEST):raise ValueError('W0_preflight_authorization_required')
    lock=read(shared/'pod-B.lock')
    if lock['owner']!='W2' or lock['pod_id']!=reg['pod_id']:raise ValueError('W2_pod_lock_required')
    connection=auth['connection'];identity=remote(connection,'identity')
    if identity['model_digest']!=DIGEST or identity['runtime']!={'version':'0.40.5'}:raise ValueError('pod_identity_changed')
    if identity['gpu'] not in ('A40','NVIDIA A40') or identity['pod_id']!=reg['pod_id']:raise ValueError('gpu_changed')
    save(root/'identity.json',identity);save(root/'run-start.json',{'authorization_sha256':filehash(authorization),'epoch':time.time()})
    deadline=time.monotonic()+240
    def one(pair):
        i,t=pair;body=old.canonical(payload(t))
        for attempt in range(3):
            if time.monotonic()+reg['timeout_seconds']>deadline:raise ValueError('wall_budget_exceeded')
            if read(shared/'pod-B.lock')!=lock:raise ValueError('pod_lock_revoked')
            # Exclusive claim prevents restarting an ambiguous network call.
            claim=root/f'claim-{i:03}-{attempt}.json'
            if claim.exists():raise ValueError('ambiguous_or_repeated_call_forbidden')
            save(claim,{'body_sha256':sha256(body.encode()).hexdigest(),'registration_sha256':filehash(root/'registration.json')})
            result=remote(connection,'call',{'body':body,'timeout':reg['timeout_seconds']})
            save(root/f'attempt-{i:03}-{attempt}.json',result)
            if result['status']=='ok':break
            if result['status']!='timeout':raise ValueError('incomplete_infrastructure')
        if result['status']!='ok':raise ValueError('incomplete_infrastructure')
        save(root/f'row-{i:03}.json',judgment(t,result))
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:list(executor.map(one,enumerate(tasks)))
        result=replay(root)
        save(root/'result.json',dict(result,model_calls=len(list(root.glob('attempt-*.json'))),elapsed_seconds=240-(deadline-time.monotonic())))
        return result
    except BaseException as error:
        save(root/'failure.json',dict(verdict='incomplete_infrastructure',reason=type(error).__name__+':'+str(error),model_calls=len(list(root.glob('claim-*.json')))))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','run','replay']);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--bank',type=Path);p.add_argument('--previous',type=Path);p.add_argument('--authorization',type=Path);p.add_argument('--shared',type=Path,default=Path.home()/'nerve-orchestration');a=p.parse_args()
    print(json.dumps(register(a.directory,a.bank,a.previous) if a.action=='register' else run(a.directory,a.authorization,a.shared) if a.action=='run' else replay(a.directory),sort_keys=True))
