#!/usr/bin/env python3
"""Private reserve custodian and serial remote-only v4 comparator for v5.

Registration precedes allocation/outcomes. A replay reads journals, never network.
"""
import sys,json,os,fcntl,time,math
from pathlib import Path
from hashlib import sha256
from decimal import Decimal
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from nerve_awim.memory_gateway import scientific_family_b_v5 as v5
from nerve_awim.memory_gateway.retained_promotion_gate import CanonicalProcess
from execute_v5_identity_replay import remote
from run_v5_identity_replay import digest,write
import run_scientific_family_b_v4_sweden as old
BASE=Path('/Users/aliyildirim/nerve-research-runs/v5-gate-v3-20261016')
PRE=Path('/Users/aliyildirim/nerve-research-runs/v5-identity-replay-20261016')
BANK=Path('/Users/aliyildirim/nerve-research-runs/scientific-bank-v4-20261016')
STRATA=('supported-measurement','measurement-decoy','entity-decoy','unit-mismatch','conflict','multi-source-agreement','stale-vs-current','format-variant-agreement','dissenter')
MANIFEST='8ae1b71b421fe8ace9b89dff0bcc359c79b7d535960306e0640da76fdba79aeb'
SEED=2026101804
def read(p):return json.loads(p.read_text())
def replace(p,value):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n');tmp.chmod(0o600);os.replace(tmp,p)
def locked():
    f=(BANK/'v5-study.lock').open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);return f
def sources():
    files=[Path(__file__),ROOT/'scripts/execute_v5_identity_replay.py',ROOT/'scripts/v5_remote_call.py',ROOT/'scripts/run_v5_identity_replay.py']
    files+=list((ROOT/'scripts').glob('*scientific*.py'))+list((ROOT/'src/nerve_awim/memory_gateway').glob('*.py'))
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(set(files))}
def register():
    assert read(PRE/'report.json')['status']=='passed'
    gate=CanonicalProcess(planned_discordant_p=.85)
    assert digest(BANK/'manifest.json')==MANIFEST
    ledger=read(BANK/'consumption-ledger.json');assert not ledger['allocations'] and ledger['consumed_items']==0
    BASE.mkdir(mode=0o700)
    reg=dict(version='v5-signed-gate-v3-study-v1',created_at=datetime.now(timezone.utc).isoformat(),
        user_authorization='Run candidate v5 doc113 vs retained family-B v4 under signed gate v3; controls hard gates; bank v4 reserve; m10,t0,cap500,N40 dissenter; no signing or retention',
        supersedes_evaluation_only='doc113 old bank-v3/inactive-gate evaluation protocol; candidate rule unchanged',
        candidate='family-B-v5',incumbent='retained-family-B-v4-skill-v1',
        doc113_sha256=digest(ROOT/'docs/galahad/evidence/family-b-v5-registration.json'),
        gate_payload_sha256=gate.proof['payload_sha256'],gate_signed_commit='43c3e78',
        preflight_sha256=digest(PRE/'report.json'),identity=read(PRE/'report.json')['identity'],
        bank_manifest_sha256=MANIFEST,seed=SEED,model_seed=20261016,temperature=0,max_tokens=128,
        m=10,t=0,total_cap=500,main_cap=460,primary_cap=100,risk_stratum='dissenter',risk_N=40,
        order='balanced STRATA offset0; per-stratum indices sorted by sha256(seed:stratum:index); no replacement',
        strata=STRATA,planned_discordant_p=.85,
        sources=sources(),concurrency=1,source_hashing='once per study admission; once independently on replay',
        timeout_seconds=3*max(read(PRE/'report.json')['calibration_latencies_seconds']),retries=2,retry_on='timeout only; identical request; journaled',
        wall_budget_seconds=3600,
        controls=['always_abstain','random'],
        acceptance_rule={'gate':'unchanged signed CanonicalProcess; primary100, coverage460, risk40',
            'controls':'At terminal state, candidate >= each control in every observed stratum, strictly greater overall; zero domain violations. Failure prevents promotion; no prefix control veto.',
            'mapping':'gate promote plus controls -> promote_proposal; reject_* or controls fail -> retain_incumbent; gate insufficient_power preserved; infrastructure -> candidate_requires_review',
            'promotion_authorized':False},
        statistical_scope='Fresh sealed synthetic finite-bank stream, no reuse. E-value validity requires conditional-null assumption; not a real-world clinical claim.')
    write(BASE/'registration.json',reg)
    print(json.dumps({'registered':True,'sha256':digest(BASE/'registration.json'),'seed':SEED,'holdout_consumed':0}))
def allocate(reg):
    manifest=read(BANK/'manifest.json');assert digest(BANK/'manifest.json')==reg['bank_manifest_sha256']
    ledger=read(BANK/'consumption-ledger.json');assert not ledger['allocations'] and ledger['consumed_items']==0
    # Claim all potentially needed slots before reading outcomes. Unused allocated slots stay quarantined.
    slots={s:sorted(range(200),key=lambda i:sha256(f'{SEED}:{s}:{i}'.encode()).hexdigest())[:52+(40 if s=='dissenter' else 0)] for s in STRATA}
    allocation=dict(study=str(BASE),registration_sha256=digest(BASE/'registration.json'),slots=slots,state='allocated',consumed=0)
    ledger['allocations'].append(allocation);replace(BANK/'consumption-ledger.json',ledger)
    pool={}
    for s in STRATA:
        name=f'reserve-{s}.json';p=BANK/name
        assert p.stat().st_mode&0o777==0
        try:
            p.chmod(0o400);assert digest(p)==manifest['files'][name]['sha256'];items=read(p)
            assert isinstance(items,list) and len(items)==200
            pool[s]=[items[i] for i in slots[s]]
        finally:p.chmod(0)
    write(BASE/'private-allocation.json',pool)
    write(BASE/'allocation-receipt.json',dict(registration_sha256=digest(BASE/'registration.json'),private_allocation_sha256=digest(BASE/'private-allocation.json'),slots_sha256=sha256(old.canonical(slots).encode()).hexdigest(),allocated=sum(map(len,slots.values()))))
    return pool
def v5score(decoded,task,p):
    expected=task['expected'];answer=decoded['status']=='answer'
    correct=decoded['status']==expected['status']
    if correct and answer:correct=all(decoded[k]==expected[k] for k in ('entity','measurement','unit','source_id')) and Decimal(decoded['value'])==Decimal(expected['value'])
    source=next((r for r in p['records'] if r['source_id']==decoded['source_id']),None) if answer else None
    domain=answer and (source is None or decoded['unit']!=source['unit'] or Decimal(decoded['value'])!=Decimal(source['value']))
    return {'strict_correct':bool(correct),'domain_violation':bool(domain)}
def evaluate(task,raw):
    p=old.prepare(task,'candidate','src/nerve_awim/memory_gateway/scientific_family_b_v4.py')
    decoded=v5.decide(task['query'],task['evidence'])
    scores={'candidate':v5score(decoded,task,p),'incumbent':old.score(raw,task,p)}
    for arm in ('always_abstain','random'):
        cp=old.control_prepared(old.prepare(task,arm),arm)
        scores[arm]=old.score(old.control_raw(task,arm,cp),task,cp)
    return scores,decoded
def aggregate(gate,rows,trajectory):
    table={s:{'n':0,'candidate':0,'incumbent':0,'always_abstain':0,'random':0,'wins':0,'losses':0,'ties':0} for s in STRATA}
    for r in rows:
        t=table[r['stratum']];t['n']+=1
        for arm,score in r['scores'].items():t[arm]+=int(score['strict_correct'])
        c=r['scores']['candidate']['strict_correct'];i=r['scores']['incumbent']['strict_correct'];t['wins' if c>i else 'losses' if c<i else 'ties']+=1
    controls=all(all(t['candidate']>=t[arm] for t in table.values()) and sum(t['candidate'] for t in table.values())>sum(t[arm] for t in table.values()) for arm in ('always_abstain','random'))
    g=gate.report();verdict=g['verdict']
    if verdict.startswith('reject_') or not controls:verdict='retain_incumbent'
    if verdict not in ('promote_proposal','retain_incumbent','candidate_requires_review','insufficient_power'):raise ValueError('nonterminal')
    return dict(verdict=verdict,gate=g,controls_pass=controls,per_stratum=table,trajectory=trajectory,
        registration_sha256=digest(BASE/'registration.json'),item_level_exported=False,promotion_authorized=False)
def update(gate,task,scores):
    return gate.update(item_id=task['task_id'],stratum=task['stratum'],candidate=scores['candidate']['strict_correct'],incumbent=scores['incumbent']['strict_correct'],abstain=scores['always_abstain']['strict_correct'],domain_violation=scores['candidate']['domain_violation'])
def execute(replay=False):
    # One source hash pass before any study calls. No per-item source hashing.
    reg=read(BASE/'registration.json')
    for name,h in reg['sources'].items():assert digest(ROOT/name)==h,'source_changed:'+name
    gate=CanonicalProcess(planned_discordant_p=reg['planned_discordant_p'])
    assert gate.proof['payload_sha256']==reg['gate_payload_sha256']
    if replay:
        # Fail closed if any path attempts network during fresh-process replay.
        import socket
        def denied(*a,**kw):raise RuntimeError('replay_network_forbidden')
        socket.socket=denied
        globals()['remote']=denied
        pool=read(BASE/'private-allocation.json')
    else:
        lock=locked();pool=allocate(reg)
        identity=remote('identity');assert identity==reg['identity'];write(BASE/'identity.json',identity)
    assert digest(BASE/'private-allocation.json')==read(BASE/'allocation-receipt.json')['private_allocation_sha256']
    offsets={s:0 for s in STRATA};rows=[];trajectory=[];start=time.monotonic()
    while gate.next_stratum() is not None:
        index=len(rows);s=gate.next_stratum();task=pool[s][offsets[s]];offsets[s]+=1
        assert task['stratum']==s
        entry=old.schedule([task],['candidate'],'src/nerve_awim/memory_gateway/scientific_family_b_v4.py')[0]
        if replay:
            recorded=read(BASE/f'row-{index:03}.json');raw=recorded['incumbent_raw']
            if entry['payload'] is not None:
                body=old.canonical(entry['payload']);attempts=sorted(BASE.glob(f'attempt-{index:03}-*.json'))
                assert attempts
                for path in attempts:
                    claim=read(BASE/path.name.replace('attempt-','claim-'));assert claim['body_sha256']==sha256(body.encode()).hexdigest()
                    result=read(path)
                assert result['status']=='ok' and old.transport.decode(result['wire'])[0]==raw
        else:
            assert time.monotonic()-start<reg['wall_budget_seconds'],'study_wall_budget'
            write(BASE/f'item-claim-{index:03}.json',dict(item_id=task['task_id'],stratum=s))
            ledger=read(BANK/'consumption-ledger.json');ledger['consumed_items']=index+1;ledger['allocations'][0]['consumed']=index+1;replace(BANK/'consumption-ledger.json',ledger)
            raw='ABSTAIN'
            if entry['payload'] is not None:
                body=old.canonical(entry['payload'])
                for retry in range(3):
                    write(BASE/f'claim-{index:03}-{retry}.json',dict(body_sha256=sha256(body.encode()).hexdigest(),timeout=reg['timeout_seconds']))
                    result=remote('call',dict(body=body,timeout=reg['timeout_seconds']));write(BASE/f'attempt-{index:03}-{retry}.json',result)
                    if result['status']=='ok':break
                assert result['status']=='ok','timeouts_exhausted'
                raw=old.transport.decode(result['wire'])[0]
        scores,decoded=evaluate(task,raw);update(gate,task,scores)
        row=dict(index=index,item_id=task['task_id'],stratum=s,incumbent_raw=raw,candidate_decoded=decoded,scores=scores)
        if replay:assert row==recorded,'row_replay_mismatch'
        else:write(BASE/f'row-{index:03}.json',row)
        rows.append(row)
        g=gate.report();trajectory.append({k:g[k] for k in ('items','main_items','risk_items','log_e','phase','verdict','reason')})
        if not replay and len(rows)%10==0:print(json.dumps(trajectory[-1]),flush=True)
    report=aggregate(gate,rows,trajectory)
    if replay:
        assert old.canonical(report)==old.canonical(read(BASE/'aggregate.json')),'aggregate_replay_mismatch'
        write(BASE/'replay.json',dict(byte_identical_canonical_aggregate=True,rows_verified=len(rows),new_model_calls=0,aggregate_sha256=digest(BASE/'aggregate.json'),registration_sha256=digest(BASE/'registration.json')))
        print(json.dumps(read(BASE/'replay.json')))
    else:
        write(BASE/'aggregate.json',report)
        attempts=[read(p) for p in sorted(BASE.glob('attempt-*.json'))]
        write(BASE/'execution.json',dict(wall_seconds=time.monotonic()-start,model_calls=len(attempts),timeouts=sum(a['status']=='timeout' for a in attempts),total_remote_call_seconds=sum(a['elapsed_seconds'] for a in attempts),concurrency=1))
        ledger=read(BANK/'consumption-ledger.json');ledger['allocations'][0]['state']='complete';ledger['allocations'][0]['aggregate_sha256']=digest(BASE/'aggregate.json');replace(BANK/'consumption-ledger.json',ledger)
        print(json.dumps({k:report[k] for k in ('verdict','controls_pass','per_stratum')}))
if __name__=='__main__':
    if sys.argv[1]=='register':register()
    elif sys.argv[1]=='run':execute()
    elif sys.argv[1]=='replay':execute(True)
    else:raise ValueError('action')
