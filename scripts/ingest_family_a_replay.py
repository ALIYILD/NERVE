#!/usr/bin/env python3
"""Ingest both observed A replay arms and propose from remaining failures."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import replay_overnight_family_a as replay
from nerve_awim.memory_gateway.experience_study_store_v2 import ExperienceStudyStoreV2,build_episode
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger
study=replay.records

def ingest(source,directory,authorization):
    result=replay.evaluate(source,authorization)
    registration=study.read(source/'registration.json')
    _,_,observations,_=replay.bindings(Path(registration['planned']),Path(registration['source']))
    episodes=[]
    receipt=study.filehash(source/'result.json');regsha=study.filehash(source/'registration.json')
    for ordinal,(task,prepared,raw) in enumerate(observations):
        a=replay.canonical.score('ABSTAIN',task,replay.canonical.prepared_for(task,'candidate'))
        b=replay.old.score(raw,task,prepared)
        for arm,output,score in [('scientific-v3','ABSTAIN',a),('A01-routing-replay',''+raw,b)]:
            failure='none' if score['strict_correct'] else 'format_failure' if not score['format_valid'] else 'incorrect_selection'
            row=dict(task_id=task['task_id'],stratum=task['stratum'],candidate_id=arm,raw_output=output,
                     strict_correct=score['strict_correct'],format_ok=score['format_valid'],failure_class=failure,
                     inputs_hash=study.engine.digest({'query':task['query'],'evidence':task['evidence']}))
            episodes.append(build_episode(row=row,source_receipt_sha256=receipt,registration_sha256=regsha,
                                         model_digest=registration['model_digest'],domain='scientific-A',ordinal=ordinal))
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    authority=MemoryAuthority();actor=authority.issue('synthetic-science','model-research',permissions=('read','propose'))
    gateway=MemoryGateway(TrustedMemoryLedger(directory/'authority.sqlite',authority))
    store=ExperienceStudyStoreV2(directory/'experiences.sqlite',gateway,MemoryScope('synthetic-science','model-research','study-episodes'))
    if not store.path.exists():store.initialize(actor)
    store.append_many(actor,episodes);snapshot=store.query(actor)
    before=snapshot['head'];store.append_many(actor,episodes);again=store.query(actor)
    replay.require(before==again['head'] and len(snapshot['episodes'])==len(again['episodes'])==200,'idempotent_import_failed')
    next_incumbent='A01-routing-replay' if result['kept'] else 'scientific-v3'
    remaining=[e for e in snapshot['episodes'] if e['candidate_id']==next_incumbent]
    proposals=study.engine.propose(dict(episodes=remaining,head=before,source_sha256=study.filehash(store.path)))
    report=dict(version='historical-family-A-replay-import-v1',source_receipt_sha256=receipt,registration_sha256=regsha,
                imported_episodes=200,idempotent_reimport_verified=True,store_head=before,store_sha256=study.filehash(store.path),
                next_dev_incumbent=next_incumbent,next_proposals=proposals,
                distinct_candidate_configs=len({p['candidate_sha256'] for p in proposals}),
                reason='proposed_from_remaining_failures' if proposals else 'no_observed_failure_clusters',
                new_model_calls=0,historical_dev_reuse=True,promotion_authorized=False,
                store_type='ExperienceStudyStoreV2 explicit dev-study companion; no retained-store mutation')
    study.save(directory/'report.json',report)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--directory',type=Path,required=True);p.add_argument('--authorization',type=Path,required=True);a=p.parse_args()
    print(json.dumps(ingest(a.source,a.directory,a.authorization),sort_keys=True))
