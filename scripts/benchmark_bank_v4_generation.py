#!/usr/bin/env python3
"""CPU capacity benchmark only; public seed, never an eligible scientific bank."""
import argparse,json,os,socket,stat,sys,time
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import scientific_task_bank_v3 as bank
from nerve_awim.memory_gateway.scientific_bank_v3_truth import validate

def main(directory):
 directory.mkdir(mode=0o700,parents=False,exist_ok=False)
 source_paths=[Path(__file__),ROOT/'src/nerve_awim/memory_gateway/scientific_task_bank_v3.py',ROOT/'src/nerve_awim/memory_gateway/scientific_bank_v3_truth.py']
 sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in source_paths}
 def write(p,value):
  raw=(bank.canonical(value)+'\n').encode();fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  return {'sha256':sha256(raw).hexdigest(),'bytes':len(raw)}
 registration={'purpose':'public-seed capacity benchmark, NOT bank v4 and NEVER eligible for dev/holdout','dev_per_stratum':100,'reserve_per_stratum':200,'model_calls':0,'source_sha256':sources}
 write(directory/'benchmark-registration.json',registration)
 start=time.perf_counter();seed=sha256(b'public-capacity-benchmark-20261016-not-a-study-bank').digest()
 files={};ids=set();facts=set();private=[]
 for split,count in [('benchmark-dev',100),('benchmark-reserve',200)]:
  for s in bank.STRATA:
   items=[bank.item(seed,split,s,i) for i in range(count)]
   for item in items:
    validate(item)
    assert item['task_id'] not in ids;ids.add(item['task_id'])
    finger=bank.digest({'query':item['query'],'evidence':item['evidence']});assert finger not in facts;facts.add(finger)
   name=split+'-'+s+'.json';files[name]=write(directory/name,items)
   if split=='benchmark-reserve':private.append(directory/name)
 generated=time.perf_counter();manifest=write(directory/'benchmark-manifest.json',{'purpose':registration['purpose'],'files':files,'total':2700,'seed_public':True})
 for p in private:p.chmod(0)
 assert all(stat.S_IMODE(p.stat().st_mode)==0 for p in private)
 sealed=time.perf_counter()
 receipt={'purpose':registration['purpose'],'source_sha256':sources,'dev_items':900,'reserve_items':1800,'reserve_per_stratum':200,'total':2700,'independently_validated':len(ids),'generation_validation_write_seconds':generated-start,'manifest_sealing_seconds':sealed-generated,'total_seconds':sealed-start,'serialized_item_bytes':sum(x['bytes'] for x in files.values()),'model_calls':0,'GPU_hours':0,'incremental_cloud_compute_usd':0,'manifest_sha256':manifest['sha256'],'private_modes':'000','real_bank_v4_created':False,'scope':'Same existing synthetic family-B templates, larger capacity; no new template development, clinician verification or real-data costs included. CPU electricity not priced.'}
 write(directory/'benchmark-receipt.json',receipt);print(json.dumps(receipt))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
 def denied(*a,**kw):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):main(a.directory)
