#!/usr/bin/env python3
"""Offline replay/import of historical bank-v5 dev outputs; never a fresh study."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from nerve_awim.memory_gateway import overnight_autoresearch as engine
from nerve_awim.memory_gateway.experience_study_store_v2 import ExperienceStudyStoreV2,build_episode
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger
import run_scientific_family_b_v4_sweden as old
from nerve_awim.memory_gateway import scientific_family_b_v5 as v5
from run_v5_signed_gate_study import v5score

def read(p):return json.loads(p.read_text())
def filehash(p):return sha256(p.read_bytes()).hexdigest()
def run(source,directory):
    registration=read(source/'registration.json');tasks=read(source/'private-tasks.json')
    if not registration['dev_only'] or len(tasks)!=100 or any(t['split']!='dev' for t in tasks):raise ValueError('complete_dev_only_source_required')
    if len({t['task_id'] for t in tasks})!=100:raise ValueError('unique_tasks_required')
    regsha=filehash(source/'registration.json');receipt=filehash(source/'result.json');episodes=[];rows=[]
    for i,t in enumerate(tasks):
        p=old.prepare(t,'candidate','src/nerve_awim/memory_gateway/scientific_family_b_v4.py')
        payload=old.schedule([t],['candidate'],'src/nerve_awim/memory_gateway/scientific_family_b_v4.py')[0]['payload']
        body=old.canonical(payload);attempts=sorted(source.glob(f'attempt-{i:03}-*.json'))
        if not 1<=len(attempts)<=3:raise ValueError('bounded_attempts_required')
        for n,path in enumerate(attempts):
            if path.name!=f'attempt-{i:03}-{n}.json':raise ValueError('attempt_sequence_changed')
            if read(source/f'claim-{i:03}-{n}.json')['body_sha256']!=sha256(body.encode()).hexdigest():raise ValueError('request_binding_changed')
            response=read(path)
            if n<len(attempts)-1 and response['status']!='timeout':raise ValueError('outcome_retry_forbidden')
        if response['status']!='ok':raise ValueError('complete_response_required')
        raw=old.transport.decode(response['wire'])[0];a=old.adapter.decode(raw,p);b=v5.decide(t['query'],t['evidence'])
        scores={'v4':old.score(raw,t,p),'v5':v5score(b,t,p)}
        row=dict(task_id=t['task_id'],stratum=t['stratum'],v4_decoded=a,v5_decoded=b,scores=scores,byte_identical=old.canonical(a)==old.canonical(b))
        if row!=read(source/f'row-{i:03}.json'):raise ValueError('historical_row_replay_mismatch')
        rows.append(row);score=scores['v4']
        failure=('none' if score['strict_correct'] else 'format_failure' if not score['format_valid'] else
                 'supported_abstention' if score['false_abstention'] else 'incorrect_selection')
        episode_row=dict(task_id=t['task_id'],stratum=t['stratum'],candidate_id='family-b-v4',raw_output=raw,
                         strict_correct=score['strict_correct'],format_ok=score['format_valid'],failure_class=failure,
                         inputs_hash=engine.digest({'query':t['query'],'evidence':t['evidence']}))
        episodes.append(build_episode(row=episode_row,source_receipt_sha256=receipt,registration_sha256=regsha,
             model_digest=registration['model_digest'],domain='scientific-B',ordinal=i))
    # Recheck historical aggregate counts, not merely its claimed replay flag.
    for stratum,table in read(source/'result.json')['per_stratum'].items():
        selected=[r for r in rows if stratum=='pooled' or r['stratum']==stratum]
        wins=sum(r['scores']['v5']['strict_correct'] and not r['scores']['v4']['strict_correct'] for r in selected)
        losses=sum(r['scores']['v4']['strict_correct'] and not r['scores']['v5']['strict_correct'] for r in selected)
        if (table['n'],table['wins'],table['losses'])!=(len(selected),wins,losses):raise ValueError('aggregate_replay_mismatch')
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    authority=MemoryAuthority();actor=authority.issue('synthetic-science','model-research',permissions=('read','propose'))
    gateway=MemoryGateway(TrustedMemoryLedger(directory/'authority.sqlite',authority))
    scope=MemoryScope('synthetic-science','model-research','study-episodes')
    store=ExperienceStudyStoreV2(directory/'experiences.sqlite',gateway,scope)
    if not store.path.exists():store.initialize(actor)
    imported=store.append_many(actor,episodes);snapshot=store.query(actor)
    proposals=engine.propose(dict(episodes=snapshot['episodes'],head=snapshot['head'],source_sha256=filehash(store.path)))
    result=dict(version='overnight-historical-dev-import-v1',historical_only=True,source=str(source),
                receipt_sha256=receipt,registration_sha256=regsha,replayed_rows=100,
                new_model_calls=0,import_count=imported['count'],store_head=snapshot['head'],
                store_type='ExperienceStudyStoreV2 explicit dev-study companion; original pinned format schema unchanged',
                failure_clusters=len(proposals),proposals=proposals,
                fresh_experiments=0,promotion_authorized=False)
    engine.write_once(directory/'report.json',result)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--directory',required=True,type=Path);a=p.parse_args()
    print(json.dumps(run(a.source,a.directory),sort_keys=True))
