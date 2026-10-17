#!/usr/bin/env python3
"""Registered CPU-only canonical-v3 routing audit on bank-v3 dev.

Reads only manifest/dev archive members. Never evaluates a model-routed item,
opens holdout, changes bank files or manufactures an unobserved model answer.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
import tarfile
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import overnight_dev_study as records
from nerve_awim.memory_gateway import scientific_candidate_v3_study as canonical
from nerve_awim.memory_gateway.scientific_bank_v3_truth import validate

def run(archive,directory):
    digest=records.filehash(archive)
    if digest!='6b61fdc3cd68ca4d9ed45fb937b46765936e9e049827ce3133b4278ad8f921dc':raise ValueError('registered_bank_archive_changed')
    with tarfile.open(archive) as source:
        manifest_raw=source.extractfile('nerve-attended-bank-v3/manifest.json').read()
        dev_raw=source.extractfile('nerve-attended-bank-v3/dev.json').read()
    manifest=json.loads(manifest_raw)
    # Archive and published manifest hashes bind the exact dev split.
    if sha256(manifest_raw).hexdigest()!=records.filehash(ROOT/'docs/galahad/evidence/attended-bank-v3-manifest.json'):raise ValueError('published_manifest_changed')
    tasks=json.loads(dev_raw)
    if len(tasks)!=900 or any(t['split']!='dev' for t in tasks):raise ValueError('nine_stratum_dev_only_required')
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    reg=dict(version='canonical-v3-bank-v3-dev-routing-audit-v1',items=900,
       archive_sha256=digest,manifest_sha256=sha256(manifest_raw).hexdigest(),dev_sha256=sha256(dev_raw).hexdigest(),
       evaluator_sha256=records.filehash(ROOT/'src/nerve_awim/memory_gateway/scientific_candidate_v3_study.py'),
       candidate_sha256=records.filehash(ROOT/'src/nerve_awim/memory_gateway/scientific_candidate_v3.py'),
       script_sha256=records.filehash(Path(__file__)),
       metrics=['route counts','deterministic-path strict correctness','unobserved model-route count'],
       next_study='100 seed-ranked dev items stratified across nine strata; freeze before any model call',
       seed=2026101703,new_model_calls=0,holdout_opened=False,promotion_authorized=False)
    records.save(directory/'registration.json',reg)
    rows=[]
    for task in tasks:
        validate(task);p=canonical.prepared_for(task,'candidate')
        row=dict(task_id=task['task_id'],stratum=task['stratum'],route=p['route'],gate_reason=p['gate_reason'],strict_correct=None)
        if p['route']=='deterministic_abstention':row['strict_correct']=canonical.score('ABSTAIN',task,p)['strict_correct']
        rows.append(row)
    records.save(directory/'rows.json',rows)
    result=dict(registration_sha256=records.filehash(directory/'registration.json'),rows_sha256=records.filehash(directory/'rows.json'),
        routes=dict(Counter(r['route'] for r in rows)),gate_reasons=dict(Counter(r['gate_reason'] for r in rows)),
        deterministic_failures=sum(r['strict_correct'] is False for r in rows),
        deterministic_correct=sum(r['strict_correct'] is True for r in rows),
        unobserved_model_outcomes=sum(r['strict_correct'] is None for r in rows),
        per_stratum={s:dict(deterministic_failures=sum(r['strict_correct'] is False for r in rows if r['stratum']==s),
                           unobserved=sum(r['strict_correct'] is None for r in rows if r['stratum']==s)) for s in sorted({r['stratum'] for r in rows})},
        new_model_calls=0,holdout_opened=False,promotion_authorized=False)
    records.save(directory/'result.json',result)
    return result
if __name__=='__main__':
    print(json.dumps(run(Path(sys.argv[1]),Path(sys.argv[2])),sort_keys=True))
