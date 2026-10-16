#!/usr/bin/env python3
"""Fresh private bank-v4 reserve; aggregate metadata only. No model calls."""
import argparse,hmac,json,os,secrets,socket,stat,sys,time,subprocess
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import scientific_task_bank_v3 as generator
from nerve_awim.memory_gateway.scientific_bank_v3_truth import validate
VERSION='task-bank-v4-family-b-reserve'

def digest(p):return sha256(p.read_bytes()).hexdigest()
def write(p,value):
 raw=(generator.canonical(value)+'\n').encode();fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 return sha256(raw).hexdigest()
def build(root,confirmation,predecessor_commit):
 result=json.loads(confirmation.read_text())
 if result.get('chosen_m')!=10 or 10 not in result.get('eligible_m',[]):raise ValueError('qualifying_confirmation_required')
 registration_path=confirmation.parent/'registration.json'
 if digest(registration_path)!=result['registration_sha256']:raise ValueError('confirmation_registration_mismatch')
 registration=json.loads(registration_path.read_text())
 if any(digest(ROOT/p)!=v for p,v in registration['source_sha256'].items()):raise ValueError('confirmation_source_drift')
 # Verify the earlier committed candidate specification before creating any bank data.
 for relative in ['docs/galahad/evidence/family-b-v5-registration.json',str(next((ROOT/'docs/galahad').glob('113-*.md')).relative_to(ROOT))]:
  historical=subprocess.check_output(['git','show',predecessor_commit+':'+relative],cwd=ROOT)
  if historical!=(ROOT/relative).read_bytes():raise ValueError('v5_prior_commit_mismatch')
 subprocess.run(['git','merge-base','--is-ancestor',predecessor_commit,'HEAD'],cwd=ROOT,check=True)
 root.mkdir(mode=0o700,parents=False,exist_ok=False);start=time.perf_counter();seed=secrets.token_bytes(32)
 seed_id=sha256(seed).hexdigest();old=json.loads((ROOT/'docs/galahad/evidence/attended-bank-v3-generation-registration.json').read_text())
 if seed_id==old['seed_identity']:raise ValueError('seed_reuse')
 child_seed=hmac.new(seed,VERSION.encode(),'sha256').digest()
 paths=[Path(__file__),ROOT/'src/nerve_awim/memory_gateway/scientific_task_bank_v3.py',ROOT/'src/nerve_awim/memory_gateway/scientific_bank_v3_truth.py']
 pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
 v5=ROOT/'docs/galahad/evidence/family-b-v5-registration.json';doc=next((ROOT/'docs/galahad').glob('113-*.md'))
 reg={'version':VERSION,'created_at_utc':datetime.now(timezone.utc).isoformat(),'confirmation_result_sha256':digest(confirmation),'source_sha256':pins,'seed_identity':seed_id,
 'counts':{'dev':{s:100 for s in generator.STRATA},'reserve':{s:200 for s in generator.STRATA}},'total':2700,
 'generator_template_family':generator.VERSION,'namespace':'HMAC(new_private_seed, bank_v4_version) then existing generator HMAC(split,stratum,index)',
 'v5_predates_bank':{'registration_sha256':digest(v5),'doc113_sha256':digest(doc),'prior_commit':predecessor_commit,'specification_unchanged':True},
 'eligibility':'Fresh sealed unused holdout reserve; execution still requires signed gate, candidate implementation, prospective study registration and exclusive consumption ledger. Not old slice reuse.',
 'secrecy':'All item-level dev and reserve files plus seed stay gate-private mode000; directory0700. Trusted host permissions, not independent enclave.',
 'disjointness':'Exact task-ID and query/evidence uniqueness across all2700 new items checked; cryptographically independent new seed namespace vs prior bank, no old private reserve opened.',
 'model_calls':0}
 regsha=write(root/'generation-registration.json',reg);private=[root/'private-seed.json'];write(private[0],{'seed':seed.hex()})
 ids=set();facts=set();files={};counts={}
 for split,n in [('dev',100),('reserve',200)]:
  counts[split]={}
  for s in generator.STRATA:
   tasks=[generator.item(child_seed,split,s,i) for i in range(n)]
   for task in tasks:
    validate(task)
    fingerprint=generator.digest({'query':task['query'],'evidence':task['evidence']})
    if task['task_id'] in ids or fingerprint in facts:raise ValueError('duplicate_task_or_facts')
    ids.add(task['task_id']);facts.add(fingerprint)
   name=f'{split}-{s}.json';p=root/name;files[name]={'sha256':write(p,tasks),'count':n,'stratum':s,'split':split};private.append(p);counts[split][s]=len(tasks)
 manifest={'version':VERSION,'generation_registration_sha256':regsha,'seed_identity':seed_id,'source_sha256':pins,'files':files,'counts':counts,'total':2700,'reserve_total':1800,'reserve_per_stratum':200,'slice_gate':False,'consumed_items':0,'item_level_exported':False}
 manifestsha=write(root/'manifest.json',manifest)
 for p in private:p.chmod(0)
 if any(stat.S_IMODE(p.stat().st_mode)!=0 for p in private):raise ValueError('seal_failed')
 if any(digest(ROOT/p)!=v for p,v in pins.items()):raise ValueError('source_changed')
 ledger={'version':VERSION,'manifest_sha256':manifestsha,'consumed_items':0,'allocations':[],'requires':'Exclusive atomic fresh-item allocation before outcomes; no signature grants implicit item reuse.'};write(root/'consumption-ledger.json',ledger)
 receipt={'version':VERSION,'sealed':True,'sealed_at_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':manifestsha,'generation_registration_sha256':regsha,'validated':len(ids),'reserve_items':1800,'reserve_per_stratum':200,'dev_items':900,'private_modes':{p.name:'000' for p in private},'directory_mode':'0700','item_level_exported':False,'new_seed':True,'v5_registration_predates_seal':reg['v5_predates_bank'],'eligible_fresh_reserve':True,'execution_authorized':False,'model_calls':0,'GPU_hours':0,'cloud_compute_usd':0,'wall_seconds':time.perf_counter()-start}
 write(root/'sealing-receipt.json',receipt);print(json.dumps(receipt));return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--confirmation',type=Path,required=True);p.add_argument('--v5-prior-commit',required=True);a=p.parse_args()
 def denied(*a,**kw):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):build(a.directory,a.confirmation,a.v5_prior_commit)
