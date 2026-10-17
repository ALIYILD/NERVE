#!/usr/bin/env python3
"""Ingest replayed A routing failures; register one fresh dev routing candidate.

No model inference, no holdout access. Six clusters do not make six novel ideas.
"""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tarfile
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import inspect_family_a_dev_routes as audit
import overnight_dev_study as records
from nerve_awim.memory_gateway.experience_study_store_v2 import ExperienceStudyStoreV2,build_episode
from nerve_awim.memory_gateway.contracts import MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.scientific_candidates import _clusters
from nerve_awim.memory_v18 import MemoryAuthority,TrustedMemoryLedger

def run(archive,source,directory):
    replay=audit.run(archive,source)
    with tarfile.open(archive) as tar:tasks=json.load(tar.extractfile('nerve-attended-bank-v3/dev.json'))
    byid={t['task_id']:t for t in tasks};rows=records.read(source/'rows.json')
    source_hash=records.filehash(source/'result.json');reg_hash=records.filehash(source/'registration.json')
    episodes=[]
    for i,row in enumerate(rows):
        if row['route']!='deterministic_abstention' or type(row['strict_correct'])is not bool:raise ValueError('only_observed_deterministic_outcomes_allowed')
        task=byid[row['task_id']]
        e=dict(task_id=row['task_id'],stratum=row['stratum'],candidate_id='scientific-v3',raw_output='ABSTAIN',
            strict_correct=row['strict_correct'],format_ok=True,
            failure_class='none' if row['strict_correct'] else 'unsupported_evidence_abstention',
            inputs_hash=records.engine.digest({'query':task['query'],'evidence':task['evidence']}))
        episodes.append(build_episode(row=e,source_receipt_sha256=source_hash,registration_sha256=reg_hash,
            model_digest=records.DIGEST,domain='scientific-A',ordinal=i))
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    authority=MemoryAuthority();actor=authority.issue('synthetic-science','model-research',permissions=('read','propose'))
    gateway=MemoryGateway(TrustedMemoryLedger(directory/'authority.sqlite',authority))
    store=ExperienceStudyStoreV2(directory/'experiences.sqlite',gateway,MemoryScope('synthetic-science','model-research','study-episodes'))
    if not store.path.exists():store.initialize(actor)
    store.append_many(actor,episodes);snapshot=store.query(actor);clusters=_clusters(snapshot['episodes'])
    # One explicit rule generates one candidate from all six corroborating clusters.
    if not clusters or any(c['failure_class']!='unsupported_evidence_abstention' for c in clusters):raise ValueError('registered_grammar_failure_rule_required')
    candidate='src/nerve_awim/memory_gateway/overnight_family_a_routing.py'
    proposal=dict(seam='routing',candidate_module=candidate,candidate_sha256=records.filehash(ROOT/candidate),
        hypothesis='Fallback to retained family-B v4 only on canonical v3 unsupported input grammar; retain v3 route otherwise.',
        clusters=clusters,store_head=snapshot['head'],novel_candidates=1,
        scope='Bank-v3 input grammar compatibility; not a general v3 accuracy claim',
        risk='Fallback may regress safety or source choice; all nine strata and frozen controls required.',
        evaluated=False,promotion_authorized=False)
    selected=[]
    for n,stratum in enumerate(sorted({t['stratum'] for t in tasks})):
        pool=sorted((t for t in tasks if t['stratum']==stratum),key=lambda t:sha256(('2026101703:'+t['task_id']).encode()).hexdigest())
        selected.extend(pool[:12 if n==0 else 11])
    selected.sort(key=lambda t:sha256(('2026101704:'+t['task_id']).encode()).hexdigest())
    records.save(directory/'tasks.json',selected)
    registration=dict(version='overnight-A-routing-next-study-v1',experiment_id='A01-planned',
        proposal=proposal,rule=records.engine.RULE,items=100,tasks_sha256=records.filehash(directory/'tasks.json'),
        incumbent='scientific-v3',fallback='retained-family-b-v4',model_digest=records.DIGEST,
        seed=20261015,control_seed=20261016,
        controls='Use family-B registered control_raw/control_prepared deterministic controls on original evidence; score with its original fixed evaluator.',
        evaluator='canonical v3 score for incumbent; family-B v4 fixed score for fallback; strict ground-truth correctness per original task',
        sources={p:records.filehash(ROOT/p) for p in (candidate,'scripts/register_overnight_family_a.py','scripts/inspect_family_a_dev_routes.py','src/nerve_awim/memory_gateway/scientific_candidate_v3_study.py','scripts/run_scientific_family_b_v4_sweden.py')},
        protected_sha256=records.read(ROOT/'docs/galahad/evidence/overnight-protected-paths.json')['paths'],
        inference_authorized=False,execution_status='registered_design_awaiting_runner_and_authorization',
        prior_data='Tasks have CPU canonical-v3 routing outcomes observed; candidate outcomes unobserved. This is dev reuse, not sealed or unseen-data confirmation.',
        new_model_calls=0,holdout_opened=False,promotion_authorized=False)
    records.save(directory/'registration.json',registration)
    report=dict(imported_episodes=len(episodes),deterministic_failures=replay['deterministic_failures'],
        failure_clusters=len(clusters),distinct_candidates=1,proposal_iterations=1,
        registration_sha256=records.filehash(directory/'registration.json'),store_head=snapshot['head'],
        new_model_calls=0,execution_status=registration['execution_status'],promotion_authorized=False)
    records.save(directory/'report.json',report)
    return report
if __name__=='__main__':print(json.dumps(run(*map(Path,sys.argv[1:])),sort_keys=True))
