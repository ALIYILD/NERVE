#!/usr/bin/env python3
"""Prospective W2 cycle. Model calls require explicit current session authorization.

Uses immutable evaluators; private task/response journals; no holdout reads.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import time
from threading import Lock, Event
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import overnight_dev_study as transport
import overnight_cycle_preflight as preflight
from nerve_awim.memory_gateway import overnight_cycle_candidates as candidates
from nerve_awim.memory_gateway import overnight_advisors as advisors
from nerve_awim.memory_gateway import faithfulness_monitor as faithfulness
from nerve_awim.memory_gateway import scientific_candidate_v3_study as a_score
from nerve_awim.memory_gateway.scientific_bank_v3_truth import validate
from nerve_awim.memory_gateway import scientific_task_bank_v3 as bank3, scientific_task_bank_v5 as bank5
from nerve_awim.memory_gateway.experience_study_store_v2 import ExperienceStudyStoreV2, build_episode
from nerve_awim.memory_gateway.experience_store_v2 import ExperienceStoreV2
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.obsidian_export_v18 import render_research_snapshot

RUNS=Path.home()/'nerve-research-runs'
SHARED=Path.home()/'nerve-orchestration'
PRIVATE=RUNS/'w2-cycle-20261017'
PUBLIC=ROOT/'research/overnight-20261017/cycle'
ARCHIVE=RUNS/'attended-20261016/nerve-attended-bank-v3.private.tar.gz'
BANK_B=RUNS/'scientific-bank-v5-20261016'
POD='5xndo7i7s5r9zn'
POD_WORKERS={
    '5xndo7i7s5r9zn':'/workspace/v5_remote_call.py',
    'lvojhtouu5gede':'/workspace/bank_v5_fallback_remote.py',
}
HERMES_MODEL='claude-sonnet-4-6'
HERMES_CALL_ALLOCATION_USD=0.50
MODEL=transport.DIGEST
read=transport.read
hashfile=transport.filehash
digest=transport.engine.digest
save=transport.save
atomic=preflight.save
mutex=Lock()
AUTH=None


def now():return datetime.now(timezone.utc).isoformat()


def append(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
    try:os.write(fd,(json.dumps(data,sort_keys=True)+'\n').encode());os.fsync(fd)
    finally:os.close(fd)


def event(kind, **data):append(SHARED/'ledger.jsonl',dict(time=now(),loop='L3.cycle',event=kind,**data))


def accounting(authorization):
    elapsed=max(0,time.time()-authorization['pod_started_epoch'])
    additional=elapsed*authorization['hourly_usd']/3600
    total=authorization['base_compute_usd']+additional
    spend=read(SHARED/'spend.json')
    allocated=sum(read(p).get('api_allocation_usd',0) for p in (PRIVATE/'calls').glob('*.json'))
    spend.update(api_allocation_usd=allocated,projected_compute_plus_api_allocation_usd=total+allocated,compute_usd=total,projected_compute_usd=total,last_checked_at=now(),
                 model_calls=authorization['base_model_calls']+len(list((PRIVATE/'calls').glob('*.json'))),
                 active_cycle_interval=dict(pod_id=POD,started_epoch=authorization['pod_started_epoch'],
                    hourly_usd=authorization['hourly_usd'],elapsed_seconds=elapsed,compute_usd=additional))
    atomic(SHARED/'spend.json',spend)
    if total+allocated>=11 or additional+allocated>=authorization['resume_compute_cap_usd']:
        raise ValueError('compute_budget_stop')
    return spend


def protected():
    baseline=read(ROOT/'docs/galahad/evidence/overnight-protected-paths.json')['paths']
    for name,h in baseline.items():
        if hashfile(ROOT/name)!=h:raise ValueError('protected_hash_changed:'+name)
    paths={ROOT/name for name in baseline}
    for folder in ('registry','trust'):
        paths.update(p for p in (ROOT/folder).rglob('*') if p.is_file())
    for pattern in ('*bank*.py','*truth*.py','*gate*.py','*study.py'):
        paths.update((ROOT/'src/nerve_awim/memory_gateway').glob(pattern))
    paths.update(ROOT/p for p in ('scripts/run_scientific_family_b_v4_sweden.py','scripts/run_v5_signed_gate_study.py','scripts/verify_galahad.py','tests/suite_tiers.json'))
    # Hash the sealed archive as bytes; never parse its reserve members.
    paths.add(ARCHIVE)
    paths.add(BANK_B/'manifest.json')
    paths.update(BANK_B.glob('dev-*.json'))
    return {str(p):hashfile(p) for p in sorted(paths)}


def assert_protected(pins):
    if protected()!=pins:raise ValueError('protected_inventory_or_hash_changed')


def bank_tasks(family):
    if family=='A':
        with tarfile.open(ARCHIVE) as archive:
            raw=archive.extractfile('nerve-attended-bank-v3/dev.json').read()
            manifest=archive.extractfile('nerve-attended-bank-v3/manifest.json').read()
        if sha256(manifest).hexdigest()!=hashfile(ROOT/'docs/galahad/evidence/attended-bank-v3-manifest.json'):
            raise ValueError('bank_A_manifest_changed')
        tasks=json.loads(raw);binding=dict(manifest_sha256=sha256(manifest).hexdigest(),dev_sha256=sha256(raw).hexdigest())
    else:
        manifest=read(BANK_B/'manifest.json');tasks=[]
        for stratum in bank5.STRATA:
            p=BANK_B/f'dev-{stratum}.json'
            if hashfile(p)!=manifest['files'][p.name]['sha256']:raise ValueError('bank_B_dev_changed')
            tasks.extend(read(p))
        binding=dict(manifest_sha256=hashfile(BANK_B/'manifest.json'),dev_sha256=digest(tasks))
    for task in tasks:
        if task['split']!='dev':raise ValueError('dev_only')
        validate(task)
    return tasks,binding


def select(tasks, seed, used):
    chosen=[]
    strata=sorted({t['stratum'] for t in tasks})
    for n,s in enumerate(strata):
        pool=[t for t in tasks if t['stratum']==s and t['task_id'] not in used]
        pool.sort(key=lambda t:digest([seed,t['task_id']]))
        count=100//len(strata)+(n<100%len(strata))
        if len(pool)<count:raise ValueError('fresh_dev_exhausted')
        chosen.extend(pool[:count])
    return sorted(chosen,key=lambda t:digest([seed,'order',t['task_id']]))


def experience(family):
    name='overnight-20261017-A01-planned' if family=='A' else 'overnight-20261017-b-experiences'
    return preflight.validated_store(RUNS/name/'experiences.sqlite',ExperienceStudyStoreV2)


def check_bank(state):
    binding=state['bank']
    if digest(state['tasks'])!=binding['dev_sha256'] and 'path' in binding:
        raise ValueError('new_bank_memory_changed')
    if 'path' in binding:
        directory=Path(binding['path'])
        if hashfile(directory/'manifest.json')!=binding['manifest_sha256']:
            raise ValueError('new_bank_manifest_changed')
        for name,entry in read(directory/'manifest.json')['files'].items():
            if name.startswith('dev-') and hashfile(directory/name)!=entry['sha256']:
                raise ValueError('new_dev_bank_changed')
            if name.startswith('reserve-') and (directory/name).stat().st_mode&0o777:
                raise ValueError('new_reserve_no_longer_sealed')


def reserve_call(kind, registration):
    with mutex:
        if AUTH is not None:
            if (SHARED/'inference-revoked.json').exists():raise ValueError('inference_revoked')
            if time.time()>AUTH['expires_epoch']:raise ValueError('session_time_budget')
            accounting(AUTH)
        claims=list((PRIVATE/'calls').glob('*.json'))
        counts=Counter(read(p)['kind'] for p in claims)
        if kind in ('socratic','agent-node','jev') and sum(counts[k] for k in ('socratic','agent-node','jev'))>=1000:
            raise ValueError('combined_advisor_call_cap')
        if kind=='jev' and counts[kind]>=40:raise ValueError('jev_cap')
        if kind=='agent-node' and counts[kind]>=400:raise ValueError('normaliser_cap')
        allocation=HERMES_CALL_ALLOCATION_USD if kind=='socratic' else 0
        allocated=sum(read(p).get('api_allocation_usd',0) for p in claims)
        if AUTH is not None and kind=='socratic':
            spend=accounting(AUTH)
            if (spend['compute_usd']+allocated+allocation>11
                    or spend['active_cycle_interval']['compute_usd']+allocated+allocation>AUTH['resume_compute_cap_usd']):
                raise ValueError('combined_compute_API_budget_stop')
        path=PRIVATE/'calls'/f'{len(claims):05}.json'
        save(path,dict(kind=kind,registration_sha256=registration,time=now(),
                       api_allocation_usd=allocation,api_provider='anthropic' if allocation else None,
                       allocation_basis='conservative per-call budget reservation, not billed usage'))
        return path


def hermes_identity(role):
    profile='backend-engineer' if role=='proposer' else 'evidence-safety-auditor'
    python=Path.home()/'.hermes/hermes-agent/.venv/bin/python'
    worker=ROOT/'scripts/overnight_hermes_worker.py'
    env=dict(os.environ,PYTHONPATH=str(Path.home()/'.hermes/hermes-agent'))
    result=subprocess.run([str(python),str(worker)],input=json.dumps(dict(profile=profile,inspect=True,inspect_profile=True)),
                          text=True,capture_output=True,env=env,timeout=20,check=True)
    identity=json.loads(result.stdout)
    if identity.get('provider')!='anthropic' or identity['configured_model']!=HERMES_MODEL:
        raise ValueError('registered_Claude_identity_required')
    return identity


def hermes(role, context, envelope_hash, identity, audit):
    prompt=('You are the '+role+' in a synthetic scientific research cycle. Hypotheses only. '
            'Return JSON with hypothesis (three strings: seam, prediction, falsifying_test) and self_report. '
            'self_report must contain sources_used, tests_run, tools_called, fallbacks_taken, each a list of action IDs. '
            'Report only your own completed actions; tests include outcomes; preserve repeated actions. '
            'The supplied context source ID is context:'+role+'. Do not claim host evaluation actions. '
            'No tools, lessons, memory, verdicts or implementation. Choose one allowed seam. '
            'For falsifier, propose a counter-hypothesis and a test that would disprove it. '
            +json.dumps(context,sort_keys=True))
    profile='backend-engineer' if role=='proposer' else 'evidence-safety-auditor'
    python=Path.home()/'.hermes/hermes-agent/.venv/bin/python'
    worker=ROOT/'scripts/overnight_hermes_worker.py'
    env=dict(os.environ,PYTHONPATH=str(Path.home()/'.hermes/hermes-agent'))
    if hermes_identity(role)!=identity:raise ValueError('Hermes_identity_changed')
    model=identity['configured_model']
    if model!=HERMES_MODEL or identity.get('provider')!='anthropic':raise ValueError('registered_Claude_identity_required')
    if not identity.get('credential_present'):raise ValueError('ANTHROPIC_API_KEY_not_configured')
    reserve_call('socratic',envelope_hash)
    audit['trace'][role]=dict(sources_used=['context:'+role], tests_run=[], tools_called=[], fallbacks_taken=[], complete=False)
    result=subprocess.run([str(python),str(worker)],input=json.dumps(dict(profile=profile,model=model,provider='anthropic',
                          prompt=prompt,max_tokens=1024)),text=True,capture_output=True,env=env,timeout=70)
    # No stdout/stderr is persisted until a verdict; hashes/counts only before it.
    try:response=json.loads(result.stdout)
    except ValueError:raise ValueError('Hermes_invalid_response') from None
    if (response.get('provider')!='anthropic' or response.get('requested_model')!=HERMES_MODEL
            or not response.get('ok') or not response.get('native_hermes')):raise ValueError('Hermes_call_failed')
    audit['trace'][role]['complete']=response.get('tools') == 0 and response.get('availability_fallback') is False
    if response.get('availability_fallback'):audit['trace'][role]['fallbacks_taken'].append('model_availability')
    value=response['value']
    audit['report'][role]=value.get('self_report') if isinstance(value,dict) else value
    h=value.get('hypothesis',{}) if isinstance(value,dict) else {}
    if set(h)!={'seam','prediction','falsifying_test'} or h['seam'] not in candidates.SEAMS or any(type(v)is not str or not 0<len(v)<=3000 for v in h.values()):
        raise ValueError('Hermes_hypothesis_schema')
    return h


def payload(prepared):
    p=prepared['prepared']
    if prepared['decision'] is not None or p['route']!='model':return None
    body=dict(model='qwen2.5-coder:7b',temperature=0,seed=20261016,stream=False,max_tokens=128,
              messages=[dict(role='system',content=p['system']),dict(role='user',content=p['user'])])
    if p['schema'] is not None:body['response_format']={'type':'json_schema','json_schema':{'name':'scientific_measurement','strict':True,'schema':p['schema']}}
    return body


def score(task,prepared,raw):
    if prepared['kind']=='a3':
        s=a_score.score(raw,task,prepared['prepared'])
        s['domain_violation']=s['answer_status']=='answer' and not s['strict_correct']
    elif prepared['decision'] is not None:
        s=transport.v5score(prepared['decision'],task,prepared['prepared'])
        s.update(format_valid=True,answer_status=prepared['decision']['status'])
    else:s=transport.old.score(raw,task,prepared['prepared'])
    return s


def judge(task,config,incumbent,raws):
    a=candidates.prepare(config,task['query'],task['evidence'])
    b=candidates.prepare(incumbent,task['query'],task['evidence'])
    sc=score(task,a,raws['candidate']);si=score(task,b,raws['incumbent'])
    cp=transport.old.prepare(task,'candidate',transport.MODULE)
    controls={}
    for arm,key in [('always_abstain','always-abstain'),('random','random')]:
        p=transport.old.control_prepared(cp,arm)
        controls[key]=transport.old.score(transport.old.control_raw(task,arm,p),task,p)['strict_correct']
    safety=bool(sc['domain_violation'] or (task['expected']['status']=='abstain' and not sc['strict_correct']))
    return dict(task_id=task['task_id'],stratum=task['stratum'],candidate=sc['strict_correct'],
                incumbent=si['strict_correct'],safety_error=safety,**controls),sc,si


def replay(directory):
    reg=read(directory/'registration.json');tasks=read(directory/'tasks.json')
    if hashfile(directory/'tasks.json')!=reg['tasks_sha256']:raise ValueError('tasks_changed')
    for p,h in reg['source_sha256'].items():
        if hashfile(Path(p))!=h:raise ValueError('source_changed')
    assert_protected(reg['protected_sha256'])
    rows=[]
    for i,task in enumerate(tasks):
        raws={}
        for arm,config in [('candidate',reg['candidate']),('incumbent',reg['incumbent'])]:
            p=candidates.prepare(config,task['query'],task['evidence']);body=payload(p)
            raw='ABSTAIN'
            if body is not None:
                claim=read(directory/f'claim-{i:03}-{arm}.json')
                if claim['registration_sha256']!=hashfile(directory/'registration.json') or claim['body_sha256']!=digest(body):raise ValueError('claim_binding')
                response=read(directory/f'response-{i:03}-{arm}.json')
                if response['status']!='ok':raise ValueError('incomplete_response')
                raw=transport.old.transport.decode(response['wire'])[0]
            raws[arm]=raw
        row,_,_=judge(task,reg['candidate'],reg['incumbent'],raws)
        if row!=read(directory/f'row-{i:03}.json'):raise ValueError('row_replay_mismatch')
        rows.append(row)
    result=dict(transport.engine.decide(rows),registration_sha256=hashfile(directory/'registration.json'),
                rows_sha256=digest(rows),replay_verified=True,items=100)
    save(directory/'replay.json',result)
    return rows,result


def require_faithful(directory):
    consistency=faithfulness.monitor(read(directory/'agent-journal.json'),read(directory/'agent-self-report.json'))
    saved=read(directory/'report-trace-consistency.json')
    if not consistency['consistent'] or any(saved.get(k)!=v for k,v in consistency.items()):
        raise ValueError('unfaithful_report')


def execute(directory,connection,lock,pins):
    require_faithful(directory)
    reg=read(directory/'registration.json');tasks=read(directory/'tasks.json')
    deadline=time.monotonic()+240;stop=Event();registration=hashfile(directory/'registration.json')
    def one(pair):
        i,task=pair;raws={}
        for arm,config in [('candidate',reg['candidate']),('incumbent',reg['incumbent'])]:
            p=candidates.prepare(config,task['query'],task['evidence']);body=payload(p);raw='ABSTAIN'
            if body is not None:
                if stop.is_set() or time.monotonic()+42>deadline:raise ValueError('wall_budget')
                if read(SHARED/'pod-B.lock')!=lock:raise ValueError('lock_revoked')
                save(directory/f'claim-{i:03}-{arm}.json',dict(body_sha256=digest(body),registration_sha256=registration,time=now()))
                reserve_call('evaluation',registration)
                response=remote(connection,'call',dict(body=transport.old.canonical(body),timeout=35))
                save(directory/f'response-{i:03}-{arm}.json',response)
                if response['status']!='ok':raise ValueError('incomplete_infrastructure')
                raw=transport.old.transport.decode(response['wire'])[0]
            raws[arm]=raw
        row,_,_=judge(task,reg['candidate'],reg['incumbent'],raws)
        save(directory/f'row-{i:03}.json',row)
    transport.execute_bounded(enumerate(tasks),one,stop)
    if time.monotonic()>deadline:raise ValueError('wall_budget')
    assert_protected(pins)
    if time.monotonic()>deadline:raise ValueError('wall_budget')
    dev_elapsed=240-(deadline-time.monotonic())
    # Fresh process replay cannot call the network, and compares all frozen rows.
    completed=subprocess.run([sys.executable,str(Path(__file__)),'replay','--directory',str(directory)],capture_output=True,text=True,check=True,timeout=40)
    result=read(directory/'replay.json')
    result.update(elapsed_seconds=dev_elapsed,finished_at=now())
    save(directory/'result.json',result)
    return result


def ingest(directory, family, config):
    require_faithful(directory)
    rows,_=replay(directory);reg=read(directory/'registration.json');tasks=read(directory/'tasks.json')
    destination=directory/'experience';destination.mkdir(mode=0o700,exist_ok=True)
    authority=MemoryAuthority();actor=authority.issue('synthetic-science','model-research',permissions=('read','propose'))
    gateway=MemoryGateway(TrustedMemoryLedger(destination/'authority.sqlite',authority))
    store=ExperienceStudyStoreV2(destination/'experiences.sqlite',gateway,MemoryScope('synthetic-science','model-research','study-episodes'))
    store.initialize(actor)
    episodes=[]
    for i,(task,row) in enumerate(zip(tasks,rows)):
        for arm in ('candidate','incumbent'):
            config=reg[arm]
            prepared=candidates.prepare(config,task['query'],task['evidence'])
            response=directory/f'response-{i:03}-{arm}.json'
            raw=transport.old.transport.decode(read(response)['wire'])[0] if response.exists() else 'ABSTAIN'
            scored=score(task,prepared,raw)
            output=json.dumps(prepared['decision'],sort_keys=True) if prepared['decision'] is not None else raw
            failure='none' if row[arm] else 'format_failure' if not scored['format_valid'] else 'incorrect_selection'
            source=dict(task_id=task['task_id'],stratum=task['stratum'],candidate_id=digest(config),
                        raw_output=output,
                        strict_correct=row[arm],format_ok=scored['format_valid'],failure_class=failure,
                        inputs_hash=digest({'query':task['query'],'evidence':task['evidence']}))
            episodes.append(build_episode(row=source,source_receipt_sha256=hashfile(directory/'result.json'),
                                         registration_sha256=hashfile(directory/'registration.json'),model_digest=MODEL,
                                         domain='scientific-'+family,ordinal=i))
    store.append_many(actor,episodes)
    return preflight.validated_store(store.path,ExperienceStudyStoreV2)


def harden(family, generation, episodes, previous):
    failures=Counter(e['stratum'] for e in episodes if e['failure_class']!='none')
    if not failures:raise ValueError('no_residual_failures_to_harden')
    directory=PRIVATE/'banks'/f'{family}-{generation}'
    directory.mkdir(parents=True,mode=0o700)
    seed=os.urandom(32)
    seed_path=directory/'seed.private'
    with seed_path.open('xb') as stream:stream.write(seed)
    seed_path.chmod(0)
    recipe=dict(family=family,generation=generation,seed_sha256=sha256(seed).hexdigest(),
                previous_manifest_sha256=previous['manifest_sha256'],failure_counts=dict(failures),
                rule='unchanged v5 generator on residual agreement strata, v3 elsewhere; 200 dev and 200 sealed reserve per stratum',
                source_sha256={str(Path(m.__file__)):hashfile(Path(m.__file__)) for m in (bank3,bank5)},time=now())
    save(directory/'registration.json',recipe)
    dev=[];files={}
    for split in ('dev','reserve'):
        for stratum in bank3.STRATA:
            generator=bank5 if stratum in failures and stratum in bank5.AGREEMENT else bank3
            tasks=[generator.item(seed,split,stratum,i) for i in range(200)]
            for task in tasks:validate(task)
            path=directory/f'{split}-{stratum}.json';save(path,tasks)
            files[path.name]=dict(sha256=hashfile(path),items=len(tasks))
            if split=='dev':dev.extend(tasks)
            else:path.chmod(0)
    save(directory/'manifest.json',dict(version='w2-residual-bank-v1',files=files,
                                      registration_sha256=hashfile(directory/'registration.json'),sealed=True,
                                      seed_sha256=sha256(seed).hexdigest()))
    event('bank_hardened',family=family,manifest_sha256=hashfile(directory/'manifest.json'),reserve_opened=False)
    return dev,dict(manifest_sha256=hashfile(directory/'manifest.json'),dev_sha256=digest(dev),path=str(directory))


def source_pins():
    paths=[Path(__file__),ROOT/'scripts/overnight_cycle_preflight.py',ROOT/'scripts/overnight_dev_study.py',
           ROOT/'scripts/overnight_hermes_worker.py',
           ROOT/'scripts/v5_remote_call.py',ROOT/'scripts/bank_v5_fallback_remote.py',Path(candidates.__file__),Path(advisors.__file__),Path(faithfulness.__file__),
           ROOT/'research/program-20261017.md']
    paths+=list((ROOT/'src/nerve_awim/memory_gateway').glob('scientific*.py'))
    return {str(p):hashfile(p) for p in paths}


def scoreboard():
    return [json.loads(line) for line in (ROOT/'research/leaderboard-20261017.jsonl').read_text().splitlines() if line]


def close_view(state):
    state['faithfulness_monitor']=faithfulness.coverage(scoreboard())
    report=advisors.summarize(scoreboard());atomic(ROOT/'research/calibration-20261017.json',report)
    atomic(ROOT/'research/status-20261017.json',state)
    snapshots=[dict(name='ledger',sha256=hashfile(SHARED/'ledger.jsonl'),data=[json.loads(x) for x in (SHARED/'ledger.jsonl').read_text().splitlines() if x]),
               dict(name='calibration',sha256=hashfile(ROOT/'research/calibration-20261017.json'),data=report)]
    for path in sorted(PRIVATE.glob('experiments/*/experience/experiences.sqlite')):
        snapshots.append(preflight.validated_store(path,ExperienceStudyStoreV2))
    # v18 bounds each view to twenty sources, so partition without dropping records.
    vault=RUNS/'obsidian-audit-vault';vault.mkdir(exist_ok=True)
    for i in range(0,len(snapshots),20):
        (vault/f'W2-cycle-20261017-{i//20}.md').write_text(render_research_snapshot(snapshots[i:i+20]))
    lines=['# W2 advisor calibration and cycle evidence — doc 13x','',
           'Status: **'+state['status']+'**. All evidence is synthetic dev research. No holdout, signing or activation.', '',
           'D9: Brier and AUC per generator against verdicts, final advisor trust weights, and template versus Socratic keep rates.', '',
           'D10: monitor coverage and quarantine counts: '+json.dumps(state['faithfulness_monitor'],sort_keys=True)+'. Zero eligible is not live validation.', '',
           '| Advisor | Verdicts | Brier | AUC | Weight |','|---|---:|---:|---:|---:|']
    for advisor,metrics in report['advisors'].items():
        lines.append(f"| {advisor} | {metrics['n']} | {metrics['brier']} | {metrics['auc']} | {report['trust_weights'][advisor]:.6f} |")
    lines+=['','Null metrics are undefined, not passing scores. Jev fixture and live calibration are separated in the JSON file.',
            'Historical rows without prospective priors are excluded. Comparisons are conditional on selection, not causal generator effects.','']
    for family,values in report['families'].items():
        lines+=['Family '+family+': '+json.dumps(values,sort_keys=True), '',
                'Run summary / refusals / bank hardening: '+json.dumps(state.get('families',{}).get(family,{}),sort_keys=True),'']
    lines+=['Reason: '+state.get('reason','none'), '',
            'Evidence: research/leaderboard-20261017.jsonl; research/calibration-20261017.json; research/status-20261017.json.',
            'Private immutable registrations and wire receipts: ~/nerve-research-runs/w2-cycle-20261017/.',
            'Obsidian exports: ~/nerve-research-runs/obsidian-audit-vault/. Display only, never state.']
    (ROOT/'docs/galahad/13x-advisor-calibration-20261017.md').write_text('\n'.join(lines)+'\n')


def commit_checkpoint(message):
    subprocess.run(['git','add','research/leaderboard-20261017.jsonl','research/calibration-20261017.json',
                    'research/status-20261017.json','research/overnight-20261017/cycle'],cwd=ROOT,check=True)
    subprocess.run(['git','add','docs/galahad/13x-advisor-calibration-20261017.md','docs/galahad/evidence/faithfulness'],cwd=ROOT,check=True)
    diff=subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT)
    if diff.returncode:
        subprocess.run(['git','commit','-m',message],cwd=ROOT,check=True)
        subprocess.run(['git','push','origin','overnight/w2-autoresearch'],cwd=ROOT,check=True,timeout=45)


def validate_connection(connection):
    # A registered endpoint can change, but the pod-to-worker binding is closed.
    import ipaddress
    ipaddress.ip_address(connection['host'])
    port=connection['port'];pod=connection['pod_id']
    if (type(port) is not int or not 1<=port<=65535
            or pod not in POD_WORKERS
            or connection.get('remote_worker')!=POD_WORKERS[pod]):
        raise ValueError('pinned_pod_connection_required')
    return pod


PINNED_WORKER_LAUNCHER = """import hashlib,sys
from pathlib import Path
worker,expected,action=sys.argv[1:]
source=Path(worker).read_bytes()
if hashlib.sha256(source).hexdigest()!=expected:
    raise RuntimeError('remote_worker_hash_mismatch')
sys.argv=[worker,action]
exec(compile(source,worker,'exec'),{'__name__':'__main__','__file__':worker})
"""


def remote(connection, action, payload=None, timeout=42):
    pod=validate_connection(connection)
    if pod!=POD:raise ValueError('registered_pod_mismatch')
    if action not in ('identity','call'):raise ValueError('worker_action_forbidden')
    registration=read(PRIVATE/'session-registration.json')
    if registration.get('connection')!=connection:
        raise ValueError('registered_connection_mismatch')
    expected=registration['remote_worker_sha256']
    if (type(expected) is not str or len(expected)!=64
            or any(c not in '0123456789abcdef' for c in expected)):
        raise ValueError('registered_worker_hash_invalid')
    import shlex
    command=['ssh','-p',str(connection['port']),'-i',str(Path.home()/'.ssh/id_ed25519'),
             '-o','BatchMode=yes','-o','ConnectTimeout=5','-o','ServerAliveInterval=5',
             '-o','ServerAliveCountMax=2','root@'+connection['host'],
             'python3','-c',shlex.quote(PINNED_WORKER_LAUNCHER),
             connection['remote_worker'],expected,action]
    completed=subprocess.run(command,input=None if payload is None else json.dumps(payload),
                             text=True,capture_output=True,check=True,timeout=timeout)
    return json.loads(completed.stdout)


def session(connection):
    global AUTH, POD
    if (SHARED/'inference-revoked.json').exists():raise ValueError('W0_inference_revoked_no_calls')
    authorization=read(SHARED/'W2-cycle-resume-authorization.json')
    if (authorization.get('authorized') is not True
            or authorization.get('identity_replay_passed') is not True
            or authorization.get('model_digest')!=MODEL
            or authorization.get('connection')!=connection
            or authorization.get('program_sha256')!=hashfile(ROOT/'research/program-20261017.md')):
        raise ValueError('current_session_authorization_required')
    POD=validate_connection(connection)
    if PRIVATE.exists():raise ValueError('session_already_exists_no_ambiguous_restart')
    PRIVATE.mkdir(mode=0o700);PUBLIC.mkdir(parents=True,exist_ok=True)
    pins=protected();sources=source_pins()
    AUTH=authorization
    save(PRIVATE/'session-registration.json',dict(time=now(),sources=sources,protected=pins,
         program_sha256=hashfile(ROOT/'research/program-20261017.md'),authorization_sha256=hashfile(SHARED/'W2-cycle-resume-authorization.json'),
         hermes_provider='anthropic',hermes_model=HERMES_MODEL,hermes_call_allocation_usd=HERMES_CALL_ALLOCATION_USD,
         calls_cap=1000,jev_cap=40,agent_node_cap=400,rule=advisors.RULE,max_experiments_per_family=12,
         model_digest=MODEL,pod_id=POD,connection=connection,
         remote_worker_sha256=hashfile(ROOT/'scripts'/Path(connection['remote_worker']).name),physical_transport_attempts=1))
    event('cycle_start',registration_sha256=hashfile(PRIVATE/'session-registration.json'))
    # Verify format-only v2 too; never coerce general bank receipts into that schema.
    preflight.validated_store(RUNS/'scientific-format-episodes-v1/experiences.sqlite',ExperienceStoreV2)
    states={}
    for f in ('A','B'):
        tasks,binding=bank_tasks(f)
        states[f]=dict(incumbent=candidates.initial(f),tasks=tasks,bank=binding,experience=experience(f),
                       experience_path=RUNS/('overnight-20261017-A01-planned' if f=='A' else 'overnight-20261017-b-experiences')/'experiences.sqlite',
                       keeps=0,reverts=0,generation=0,used=set(),n=0,done=False,refusals=[],hardening=[])
    overall=dict(status='running',started_at=now(),model_calls=0,holdout_opened=False,experiments=[])
    try:
        for round_ in range(12):
            for family,state in states.items():
                if state['done']:continue
                assert_protected(pins)
                check_bank(state)
                state['experience']=preflight.validated_store(state['experience_path'],ExperienceStudyStoreV2)
                if state['n']:
                    state['experience']['data']['episodes']=[e for e in state['experience']['data']['episodes'] if e['candidate_id']==digest(state['incumbent'])]
                if source_pins()!=sources:raise ValueError('cycle_source_changed')
                # Read latest shared ledger at every iteration; a new revoke wins.
                _=[json.loads(x) for x in (SHARED/'ledger.jsonl').read_text().splitlines() if x]
                if (SHARED/'inference-revoked.json').exists():raise ValueError('inference_revoked')
                if time.time()>authorization['expires_epoch']:raise ValueError('session_time_budget')
                accounting(authorization)
                data=state['experience']['data'];episodes=data['episodes']
                failures=[e for e in episodes if e['failure_class']!='none']
                if not failures:
                    state['done']=True;state['refusals'].append('no_incumbent_residual_failures');continue
                ident=f'C2-{family}{state["n"]+1:02}'
                directory=PRIVATE/'experiments'/ident;directory.mkdir(parents=True,mode=0o700)
                # No model output in durable memory before verdict: persist only envelope/hash.
                identities={role:hermes_identity(role) for role in ('proposer','falsifier')}
                envelope=dict(experiment_id=ident,family=family,source_head=data['head'],
                              source_sha256=state['experience']['sha256'],roles=['proposer','falsifier'],
                              hermes_identities=identities,allowed_seams=list(candidates.SEAMS),time=now(),source_pins=sources)
                save(directory/'generation-registration.json',envelope)
                envelope_hash=hashfile(directory/'generation-registration.json')
                event('generation_registered',experiment_id=ident,registration_sha256=envelope_hash)
                templates=candidates.template_hypotheses(episodes,data['head'])
                context=dict(family=family,incumbent=state['incumbent'],allowed_seams=list(candidates.SEAMS),
                             failure_clusters=[dict(stratum=c['hypothesis']['cluster']['stratum'],
                             failure_class=c['hypothesis']['cluster']['failure_class'],
                             n=len(c['hypothesis']['cluster']['members'])) for c in templates])
                audit={'trace':{},'report':{}}
                generation_error=None
                proposer={};falsifier={}
                try:
                    proposer=hermes('proposer',context,envelope_hash,identities['proposer'],audit)
                    falsifier=hermes('falsifier',dict(context,proposer=proposer),envelope_hash,identities['falsifier'],audit)
                except Exception as error:
                    generation_error=type(error).__name__+':'+str(error)
                    # Missing reports or interrupted calls are never treated as faithful.
                    audit['trace'].setdefault('generation',dict(complete=False))
                consistency=faithfulness.record(ROOT/'docs/galahad/evidence/faithfulness',ident,
                                                audit['trace'],audit['report'])
                save(directory/'agent-journal.json',audit['trace'])
                save(directory/'agent-self-report.json',audit['report'])
                save(directory/'report-trace-consistency.json',consistency)
                if not consistency['consistent']:
                    state['n']+=1
                    rejection_keys=[digest([seam,c['hypothesis']['cluster']['stratum'],c['hypothesis']['cluster']['failure_class']])
                                    for seam in {proposer.get('seam','unknown'),falsifier.get('seam','unknown')} for c in templates]
                    failure=dict(experiment_id=ident,family=family,generator='socratic',agent_involving=True,
                                 agent_kinds=['socratic'],verdict='unfaithful_report',report_trace_consistency=consistency,
                                 registration_sha256=envelope_hash,registered_at=envelope['time'],
                                 receipt_sha256=hashfile(directory/'report-trace-consistency.json'),
                                 reason=generation_error or 'report_trace_mismatch',finished_at=now(),replay_verified=False)
                    save(directory/'quarantine.json',failure)
                    append(ROOT/'research/leaderboard-20261017.jsonl',failure)
                    for key in rejection_keys:
                        path=PRIVATE/'rejections'/family/f'{key}.json'
                        if not path.exists():save(path,failure)
                    event('experiment_quarantined',**failure)
                    state['refusals'].append('unfaithful_report:'+ident)
                    overall['experiments'].append(ident)
                    overall.update(timestamp=now(),families={f:dict(experiments=s['n'],keeps=s['keeps'],refusals=s['refusals'],hardening=s['hardening']) for f,s in states.items()})
                    close_view(overall);commit_checkpoint('Quarantine '+ident+' unfaithful report')
                    continue
                calibration=advisors.summarize(scoreboard());weights=calibration['trust_weights']
                choices=[]
                forced=('routing' if family=='A' else 'extraction-schema') if state['n']==0 else None
                # Bank-specific adapter binds existing scientific template proposals to one seam.
                template_seam=forced or ('extraction-schema' if 'routing' in state['incumbent']['seams'] and 'extraction-schema' not in state['incumbent']['seams'] else 'prompt-fragment')
                hypotheses=[('template',dict(seam=template_seam,prediction='Reduce the recorded incumbent residual failures using one bounded seam.',
                                             falsifying_test='100 stratified dev items; registered keep gate must pass.')),
                            ('socratic',proposer),('socratic',falsifier)]
                for generator,h in hypotheses:
                    seam=h['seam']
                    if forced and (generator!='template' or seam!=forced):continue
                    if seam in state['incumbent']['seams']:continue
                    keys=[digest([seam,c['hypothesis']['cluster']['stratum'],c['hypothesis']['cluster']['failure_class']]) for c in templates]
                    if any((PRIVATE/'rejections'/family/f'{key}.json').exists() for key in keys):continue
                    config=candidates.mutate(state['incumbent'],seam)
                    priors={}
                    for advisor in (generator,):
                        stat=calibration['families'][family][advisor]
                        priors[advisor]=dict(p_keep=(stat['kept']+1)/(stat['n']+2),label='prospective_beta_1_1_family_generator_rate')
                    aggregate=dict(completion=sum(e['evaluator_verdict']=='strict_correct' for e in episodes)/len(episodes),abort=0,violations=0,goal_penalized=0,prediction_penalized=0)
                    choice=dict(generator=generator,hypothesis=h,candidate=config,rejection_keys=keys,advisor_prior=priors)
                    choices.append(choice)
                if not choices:
                    append(ROOT/'research/leaderboard-20261017.jsonl',dict(experiment_id=ident,family=family,
                           verdict='no_candidate',agent_involving=True,agent_kinds=['socratic'],
                           report_trace_consistency=consistency,registration_sha256=envelope_hash,
                           registered_at=envelope['time'],receipt_sha256=hashfile(directory/'report-trace-consistency.json')))
                    state['done']=True;state['refusals'].append('no_new_unrejected_implemented_seam');continue
                batch=advisors.jev_prior(aggregate,{str(i):aggregate for i in range(len(choices))},
                                        lambda kind:reserve_call(kind,envelope_hash))
                for i,choice in enumerate(choices):
                    prior=batch[str(i)]
                    prior['aggregate_basis']='incumbent history only; candidate effect unmeasured'
                    choice['advisor_prior']['jev']=prior
                    choice['proposal_sha256']=digest(choice)
                chosen=advisors.triage(choices,weights)[0]
                tasks=select(state['tasks'],2026101700+round_,state['used'])
                save(directory/'tasks.json',tasks)
                reg=dict(experiment_id=ident,family=family,time=now(),generator=chosen['generator'],
                         seam=chosen['hypothesis']['seam'],hypothesis=chosen['hypothesis'],
                         hypothesis_hashes=[digest(proposer),digest(falsifier)],template_hashes=[t['hypothesis_sha256'] for t in templates],
                         candidate=chosen['candidate'],incumbent=state['incumbent'],bank=state['bank'],
                         tasks_sha256=hashfile(directory/'tasks.json'),item_ids=[t['task_id'] for t in tasks],
                         task_exposure='dev reused across historical studies; no repeat within this cycle bank; fresh calls, not unseen tasks',
                         advisor_prior=chosen['advisor_prior'],advisor_weights=weights,source_sha256=sources,
                         protected_sha256=pins,rule=dict(transport.engine.RULE,identical_transport_resends=0,stop_consecutive_reverts=None,harden_consecutive_reverts=3),model_digest=MODEL,
                         concurrency=4,wall_seconds=240,transport_attempts=1,controls=['always-abstain','random'])
                reg.update(model_seed=20261016,control_seed=transport.old.SEED)
                save(directory/'registration.json',reg);regsha=hashfile(directory/'registration.json')
                save(PUBLIC/f'{ident}-registration.json',dict(registration_sha256=regsha,time=reg['time'],
                     experiment_id=ident,family=family,generator=reg['generator'],seam=reg['seam'],
                     advisor_prior=reg['advisor_prior'],candidate_sha256=digest(reg['candidate']),
                     private_registration=str(directory/'registration.json')))
                event('experiment_registered',experiment_id=ident,registration_sha256=regsha)
                state['n']+=1;state['used'].update(t['task_id'] for t in tasks)
                lock=dict(owner='W2-cycle',pid=os.getpid(),pod_id=POD,experiment=ident,registration_sha256=regsha,time=now())
                fd=os.open(SHARED/'pod-B.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as f:json.dump(lock,f)
                try:
                    identity=remote(connection,'identity')
                    if (identity['model_digest']!=MODEL or identity['pod_id']!=POD
                            or identity['runtime']!={'version':'0.40.5'}
                            or identity['gpu'] not in ('A40','NVIDIA A40')):raise ValueError('identity_mismatch')
                    result=execute(directory,connection,lock,pins)
                except BaseException as error:
                    failure=dict(experiment_id=ident,family=family,generator=chosen['generator'],
                                 seam=reg['seam'],registration_sha256=regsha,registered_at=reg['time'],
                                 advisor_prior=chosen['advisor_prior'],verdict='incomplete_infrastructure',
                                 agent_involving=True,agent_kinds=['socratic'],report_trace_consistency=consistency,
                                 reason=type(error).__name__+':'+str(error),finished_at=now(),replay_verified=False)
                    save(directory/'failure.json',failure)
                    append(ROOT/'research/leaderboard-20261017.jsonl',failure)
                    event('experiment_incomplete',**failure)
                    raise
                finally:
                    if (SHARED/'pod-B.lock').exists() and read(SHARED/'pod-B.lock')==lock:(SHARED/'pod-B.lock').unlink()
                save(directory/'hypotheses-after-verdict.json',dict(proposer=proposer,falsifier=falsifier,templates=templates))
                row=dict(experiment_id=ident,family=family,generator=chosen['generator'],seam=reg['seam'],
                         cluster=chosen['rejection_keys'],advisor_prior=chosen['advisor_prior'],
                         agent_involving=True,agent_kinds=['socratic'],report_trace_consistency=consistency,
                         calls=len(list(directory.glob('claim-*.json'))),
                         advisor_calls=sum(read(p)['registration_sha256']==envelope_hash for p in (PRIVATE/'calls').glob('*.json')),
                         usd=result['elapsed_seconds']*authorization['hourly_usd']/3600,
                         cost_basis='evaluation wall time only; full pod uptime in shared spend.json',
                         registration_sha256=regsha,registered_at=reg['time'],receipt_sha256=hashfile(directory/'result.json'),
                         **{k:v for k,v in result.items() if k!='registration_sha256'})
                append(ROOT/'research/leaderboard-20261017.jsonl',row)
                event('experiment_verdict',experiment_id=ident,registration_sha256=regsha,receipt_sha256=row['receipt_sha256'],verdict=result['verdict'])
                if result['kept']:
                    state['incumbent']=chosen['candidate'];state['keeps']+=1;state['reverts']=0
                else:
                    state['reverts']+=1
                    for key in chosen['rejection_keys']:save(PRIVATE/'rejections'/family/f'{key}.json',dict(experiment=ident,verdict='reverted',receipt_sha256=row['receipt_sha256']))
                state['experience']=ingest(directory,family,state['incumbent'])
                state['experience_path']=directory/'experience/experiences.sqlite'
                state['experience']['data']['episodes']=[e for e in state['experience']['data']['episodes'] if e['candidate_id']==digest(state['incumbent'])]
                if result['kept'] and state['keeps']%2==0:
                    handoff=dict(family=family,candidate=state['incumbent'],candidate_sha256=digest(state['incumbent']),
                                 development_registration_sha256=regsha,receipt_sha256=row['receipt_sha256'],
                                 holdout_opened=False,promotion_authorized=False)
                    save(PUBLIC/f'{ident}-W1-handoff.json',handoff)
                    event('W1_holdout_candidate_registered',**handoff,handoff_sha256=hashfile(PUBLIC/f'{ident}-W1-handoff.json'))
                if state.get('pending_hardening'):
                    rows=[read(p) for p in sorted(directory.glob('row-*.json'))]
                    state['pending_hardening']['new_bank_incumbent_correct']=sum(r['incumbent'] for r in rows)
                    state['hardening'].append(state.pop('pending_hardening'))
                if state['reverts']==3 and state['n']<12:
                    rows=[read(p) for p in sorted(directory.glob('row-*.json'))]
                    state['generation']+=1
                    old_bank=state['bank']
                    state['tasks'],state['bank']=harden(family,state['generation'],state['experience']['data']['episodes'],old_bank)
                    state['pending_hardening']=dict(old_bank=old_bank['manifest_sha256'],new_bank=state['bank']['manifest_sha256'],old_bank_incumbent_correct=sum(r['incumbent'] for r in rows))
                    state['reverts']=0
                overall['experiments'].append(ident)
                overall['model_calls']=len(list((PRIVATE/'calls').glob('*.json')))
                overall.update(timestamp=now(),families={f:dict(experiments=s['n'],keeps=s['keeps'],refusals=s['refusals'],hardening=s['hardening']) for f,s in states.items()})
                close_view(overall);commit_checkpoint('Record '+ident+' replayed cycle verdict and calibration')
                accounting(authorization)
            if all(s['done'] for s in states.values()):break
        overall.update(status='closed',finished_at=now(),families={f:dict(experiments=s['n'],keeps=s['keeps'],refusals=s['refusals'],hardening=s['hardening']) for f,s in states.items()})
    except BaseException as error:
        overall.update(status='stopped',reason=type(error).__name__+':'+str(error),finished_at=now())
        event('cycle_stopped',reason=overall['reason'])
        raise
    finally:
        overall['model_call_claims']=len(list((PRIVATE/'calls').glob('*.json')))
        overall['model_calls']=overall['model_call_claims']
        overall['families']={f:dict(experiments=s['n'],keeps=s['keeps'],refusals=s['refusals'],hardening=s['hardening']) for f,s in states.items()}
        try:accounting(authorization)
        except ValueError as error:
            overall.update(status='stopped',reason=str(error))
        event('cycle_close',status=overall['status'],model_call_claims=overall['model_call_claims'])
        close_view(overall)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['run','replay'])
    parser.add_argument('--directory',type=Path);parser.add_argument('--connection',type=Path)
    args=parser.parse_args()
    if args.action=='replay':
        def denied(*a,**kw):raise RuntimeError('replay_network_forbidden')
        socket.socket=denied
        print(json.dumps(replay(args.directory)[1],sort_keys=True))
    else:session(read(args.connection))
