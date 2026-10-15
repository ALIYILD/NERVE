#!/usr/bin/env python3
"""Prospectively registered CPU bank generation and versioned nine-stratum seal."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import stat
from nerve_awim.memory_gateway import scientific_task_bank_v3 as bank
from nerve_awim.memory_gateway.scientific_bank_v3_truth import validate
from nerve_awim.memory_gateway.scientific_task_bank import RULES,SCHEMA

ROOT=Path(__file__).resolve().parents[1]
SOURCES=['src/nerve_awim/memory_gateway/'+name for name in ('scientific_task_bank_v3.py','scientific_bank_v3_truth.py','scientific_family_b_adapter.py','scientific_task_bank.py','scientific_structured_tasks.py')]+['scripts/build_scientific_task_bank_v3.py']

def pins():return {p:sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
def write(path,value):
    raw=(bank.canonical(value)+'\n').encode();fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return sha256(raw).hexdigest()

def build(root,protocol):
    root.mkdir(mode=0o700,parents=False);seed=secrets.token_bytes(32);sources=pins()
    devcounts={s:100 for s in bank.STRATA};holdcounts={s:34 if i<3 else 33 for i,s in enumerate(bank.STRATA)}
    registration={'version':bank.VERSION,'created_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha256(protocol.read_bytes()).hexdigest(),'sources':sources,'seed_identity':sha256(seed).hexdigest(),'counts':{'dev':devcounts,'holdout':holdcounts},'total':1200,'slices':3,'slice_size':100,'split_disjointness':'HMAC version/split/stratum/index','model_calls':0,'candidate_design_authorized':False,'independent_truth':'scientific_bank_v3_truth; no generator or adapter import'}
    regsha=write(root/'generation-registration.json',registration);write(root/'private-seed.json',{'seed':seed.hex()})
    files={};holdout=[];allids=set();alltexts=set()
    for split,counts in [('dev',devcounts),('holdout',holdcounts)]:
        items=[bank.item(seed,split,s,i) for s,n in counts.items() for i in range(n)]
        for task in items:
            validate(task)
            if task['task_id'] in allids:raise ValueError('duplicate_task')
            allids.add(task['task_id']);finger=bank.digest({'query':task['query'],'evidence':task['evidence']})
            if finger in alltexts:raise ValueError('reused_task_facts')
            alltexts.add(finger)
        files[split]=write(root/(split+'.json'),items)
        if split=='holdout':holdout=items
    slices=[];slice_ids=[]
    for j in range(3):
        tasks=[]
        for i,s in enumerate(bank.STRATA):
            rows=[t for t in holdout if t['stratum']==s];start=11*j+(1 if i<j else 0);size=11+int(i==j)
            tasks.extend(rows[start:start+size])
        if len(tasks)!=100:raise ValueError('slice_count')
        slice_ids.extend(t['task_id'] for t in tasks)
        name=f'slice{j+1}.json';digest=write(root/name,tasks)
        slices.append({'name':name,'sha256':digest,'count':100,'stratum_counts':dict(Counter(t['stratum'] for t in tasks))})
    if len(slice_ids)!=len(set(slice_ids)) or set(slice_ids)!={t['task_id'] for t in holdout}:raise ValueError('slice_partition')
    manifest={'version':bank.VERSION,'generation_registration_sha256':regsha,'seed_identity':registration['seed_identity'],'protocol_sha256':registration['protocol_sha256'],'source_sha256':sources,'rules':RULES,'schema':SCHEMA,'files':files,'counts':registration['counts'],'split_counts':{'dev':900,'holdout':300},'total':1200,'slices':slices}
    manifestsha=write(root/'manifest.json',manifest)
    private=('private-seed.json','holdout.json','slice1.json','slice2.json','slice3.json')
    for name in private:(root/name).chmod(0)
    if any(stat.S_IMODE((root/name).stat().st_mode)!=0 for name in private):raise ValueError('failed_seal')
    if pins()!=sources:raise ValueError('source_changed_during_build')
    receipt={'version':bank.VERSION,'sealed':True,'sealed_at_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':manifestsha,'generation_registration_sha256':regsha,'independently_validated':1200,'model_calls':0,'private_file_modes':{name:'000' for name in private},'candidate_designed_before_sealing':False,'boundary':'Trusted host filesystem permissions; not an independent enclave.'}
    write(root/'sealing-receipt.json',receipt);return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--protocol',type=Path,required=True);a=parser.parse_args();print(json.dumps(build(a.directory,a.protocol),indent=2))
