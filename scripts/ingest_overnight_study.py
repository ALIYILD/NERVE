#!/usr/bin/env python3
"""Replay a completed overnight dev experiment, then ingest both arms, no inference."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import overnight_dev_study as study
from nerve_awim.memory_gateway.experience_study_store_v2 import ExperienceStudyStoreV2,build_episode
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger

def ingest(source,directory):
    replay=study.replay(source)
    registration,tasks=study.check(source)
    result=study.read(source/'result.json')
    for key,value in replay.items():
        if result[key]!=value:raise ValueError('terminal_result_replay_mismatch')
    episodes=[]
    receipt=study.filehash(source/'result.json');regsha=study.filehash(source/'registration.json')
    for i,task in enumerate(tasks):
        response=study.read(sorted(source.glob(f'attempt-{i:03}-*.json'))[-1])
        raw=study.old.transport.decode(response['wire'])[0]
        prepared=study.old.prepare(task,'candidate',study.MODULE)
        incumbent=study.old.score(raw,task,prepared)
        decision=study.v5.decide(task['query'],task['evidence'])
        candidate=study.v5score(decision,task,prepared)
        for arm,output,score,format_ok in (
                ('family-b-v4',raw,incumbent,incumbent['format_valid']),
                ('family-b-v5',study.old.canonical(decision),candidate,True)):
            failure='none' if score['strict_correct'] else 'format_failure' if not format_ok else 'incorrect_selection'
            row=dict(task_id=task['task_id'],stratum=task['stratum'],candidate_id=arm,
                raw_output=output,strict_correct=score['strict_correct'],format_ok=format_ok,
                failure_class=failure,inputs_hash=study.engine.digest({'query':task['query'],'evidence':task['evidence']}))
            episodes.append(build_episode(row=row,source_receipt_sha256=receipt,registration_sha256=regsha,
                 model_digest=registration['model_digest'],domain='scientific-B',ordinal=i))
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    authority=MemoryAuthority();actor=authority.issue('synthetic-science','model-research',permissions=('read','propose'))
    gateway=MemoryGateway(TrustedMemoryLedger(directory/'authority.sqlite',authority))
    store=ExperienceStudyStoreV2(directory/'experiences.sqlite',gateway,MemoryScope('synthetic-science','model-research','study-episodes'))
    if not store.path.exists():store.initialize(actor)
    appended=store.append_many(actor,episodes);snapshot=store.query(actor)
    next_incumbent='family-b-v5' if replay['kept'] else 'family-b-v4'
    remaining=[e for e in snapshot['episodes'] if e['candidate_id']==next_incumbent]
    proposals=study.engine.propose(dict(episodes=remaining,head=snapshot['head'],source_sha256=study.filehash(store.path)))
    report=dict(version='overnight-completed-dev-import-v1',source=str(source),
        source_receipt_sha256=receipt,registration_sha256=regsha,
        replayed_items=len(tasks),imported_episodes=appended['count'],store_head=snapshot['head'],
        next_dev_incumbent=next_incumbent,next_proposals=proposals,
        reason='no_observed_failure_clusters' if not proposals else 'proposed_from_remaining_failures',
        new_model_calls=0,promotion_authorized=False,synthetic_only=True,
        store_type='ExperienceStudyStoreV2 explicit dev-study companion')
    study.save(directory/'report.json',report)
    return report
if __name__=='__main__':
    import json
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--directory',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(ingest(args.source,args.directory),sort_keys=True))
