#!/usr/bin/env python3
"""Trusted CPU generator: exactly300 fresh items, then mode000, aggregate output."""
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time
import run_scientific_runpod_gate as base
from nerve_awim.memory_gateway import scientific_task_bank as bank


def seal(root,robustness):
    # Only the completed exploratory aggregate is read, never its item outcomes.
    aggregate=base.read(robustness/'aggregate.json')
    if (aggregate.get('complete') is not True or aggregate.get('promotion_authorized') is not False
        or aggregate.get('version')!='scientific-runpod-robustness-36.5-v1'
        or aggregate.get('status')!='complete_exploratory' or aggregate.get('holdout_accessed') is not False):raise ValueError('completed_exploratory_robustness_required')
    identity=base.identity()
    if identity!=aggregate['identity']:raise ValueError('substrate_changed')
    root.mkdir(mode=0o700)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_directory_required')
    started=time.monotonic();seed=secrets.token_bytes(32)
    counts={s:43 if i<6 else 42 for i,s in enumerate(bank.STRATA)}
    sources=base.pins();sources['scripts/seal_scientific_holdout_v2.py']=base.digest(Path(__file__).read_bytes())
    registration=dict(version='scientific-holdout-bank-v2',count=300,counts=counts,seed_identity=hashlib.sha256(seed).hexdigest(),sources=sources,robustness_aggregate_sha256=base.digest((robustness/'aggregate.json').read_bytes()),identity=identity,template_rule='Existing synthetic families, new256-bit private seed; no candidate design yet',inference_calls=0,promotion_authorized=False)
    base.write(root/'generation-registration.json',registration)
    base.write(root/'private-seed.json',{'seed':seed.hex()})
    items=[bank._item(seed,'holdout',s,i) for s,n in counts.items() for i in range(n)]
    if len({t['task_id'] for t in items})!=300 or Counter(t['stratum'] for t in items)!=Counter(counts):raise ValueError('generation_counts_changed')
    base.write(root/'holdout.json',items)
    manifest=dict(version=registration['version'],count=300,counts=counts,seed_identity=registration['seed_identity'],content_sha256=base.digest((root/'holdout.json').read_bytes()),generation_registration_sha256=base.digest((root/'generation-registration.json').read_bytes()),source_sha256=sources,rules=bank.RULES,scope='New instances, same generation templates; no holdout evaluation authorized')
    base.write(root/'manifest.json',manifest)
    for name in ('holdout.json','private-seed.json'):(root/name).chmod(0)
    if any(stat.S_IMODE((root/name).stat().st_mode)!=0 for name in ('holdout.json','private-seed.json')):raise ValueError('filesystem_failed_to_seal')
    after=base.pins();after['scripts/seal_scientific_holdout_v2.py']=base.digest(Path(__file__).read_bytes())
    if after!=sources:raise ValueError('sources_changed_during_generation')
    elapsed=time.monotonic()-started
    receipt=dict(version=registration['version'],sealed=True,count=300,counts=counts,manifest_sha256=base.digest((root/'manifest.json').read_bytes()),holdout_mode='000',seed_mode='000',sealed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),identity=identity,wall_seconds=elapsed,allocated_cost_estimate_usd=elapsed*0.59/3600,cost_method='CPU generation walltime allocated at live pod rate0.59USD/hour; excludes idle, estimate not invoice',model_calls=0,candidate_designed_before_sealing=False,promotion_authorized=False)
    base.write(root/'sealing-receipt.json',receipt)
    return receipt

if __name__=='__main__':print(json.dumps(seal(Path(sys.argv[1]),Path(sys.argv[2])),sort_keys=True,indent=2))
