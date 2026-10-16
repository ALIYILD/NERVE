"""CPU-only trusted bank custodian; dev failures only, no candidate execution."""
import sys,json,os,secrets,hmac,time,socket
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import scientific_task_bank_v5 as generator,scientific_task_bank_v3 as old
from nerve_awim.memory_gateway.scientific_bank_v3_truth import validate
PRIVATE=Path('/Users/aliyildirim/nerve-research-runs/scientific-bank-v5-20261016')
HIST=Path('/Users/aliyildirim/nerve-research-runs/sweden-20261016/final-extracted/v4-dev')
E=ROOT/'docs/galahad/evidence'
def h(p):return sha256(p.read_bytes()).hexdigest()
def write(p,x):
 raw=(old.canonical(x)+'\n').encode();fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 return sha256(raw).hexdigest()
def build():
 started=time.perf_counter();PRIVATE.mkdir(mode=0o700)
 historical=json.loads((HIST/'private-report.json').read_text());replay=json.loads((E/'gate-v3_1-dev-seam-replay.json').read_text())
 for name,d in replay['historical_receipts'].items():assert h(HIST/name)==d
 episodes=[]
 for i,r in enumerate(historical['rows']):
  if r['arm']=='candidate' and r['stratum'] in generator.AGREEMENT:
   episodes.append({'episode_id':sha256((h(HIST/'registration.json')+':'+str(i)).encode()).hexdigest(),'stratum':r['stratum'],'failure_class':r['score']['diagnosis'] if not r['score']['strict_correct'] else 'none'})
 hypothesis=generator.propose(episodes);assert hypothesis['status']=='proposed' and len(hypothesis['proposals'])==1
 write(E/'bank-v5-hardening-hypothesis.json',dict(hypothesis,dev_report_sha256=h(HIST/'private-report.json'),scope='New bounded bank-mutation extension reusing Loop39 _clusters; not the existing candidate mutation SPACE, not a model research agent or an imported ExperienceStore claim.'))
 seed=secrets.token_bytes(32);seed_id=sha256(seed).hexdigest()
 for name in ['bank-v4-manifest.json','attended-bank-v3-generation-registration.json']:assert seed_id!=json.loads((E/name).read_text())['seed_identity']
 child=hmac.new(seed,generator.VERSION.encode(),'sha256').digest()
 paths=[Path(__file__),ROOT/'src/nerve_awim/memory_gateway/scientific_task_bank_v5.py',ROOT/'src/nerve_awim/memory_gateway/scientific_task_bank_v3.py',ROOT/'src/nerve_awim/memory_gateway/scientific_bank_v3_truth.py',ROOT/'src/nerve_awim/memory_gateway/scientific_candidates.py',ROOT/'scripts/test_scientific_bank_v5.py']
 pins={str(p.relative_to(ROOT)):h(p) for p in paths}
 reg={'version':generator.VERSION,'created_at':datetime.now(timezone.utc).isoformat(),'source_sha256':pins,'seed_identity':seed_id,'seed_namespace':'HMAC(new private 256-bit seed, task-bank-v5-hard-agreement-v1)','dev_per_stratum':100,'reserve_per_stratum':200,'strata':list(generator.STRATA),'unchanged_strata':list(s for s in generator.STRATA if s not in generator.AGREEMENT),'hypothesis_sha256':h(E/'bank-v5-hardening-hypothesis.json'),'dev_failure_receipt_sha256':h(HIST/'private-report.json'),'bank_v4_manifest_sha256':h(E/'bank-v4-manifest.json'),'candidate_sources_unchanged':{str(p.relative_to(ROOT)):h(p) for p in [ROOT/'src/nerve_awim/memory_gateway/scientific_family_b_v4.py',ROOT/'src/nerve_awim/memory_gateway/scientific_family_b_v5.py']},'model_calls':0,'private_item_level_export':False,'no_candidate_evaluated_on_reserve':True,'status':'generation_registered_before_items'}
 regsha=write(PRIVATE/'generation-registration.json',reg);write(E/'bank-v5-generation-registration.json',reg)
 write(PRIVATE/'private-seed.json',{'seed':seed.hex()});private=[PRIVATE/'private-seed.json'];files={};ids=set();facts=set()
 for split,n in [('dev',100),('reserve',200)]:
  for s in generator.STRATA:
   tasks=[generator.item(child,split,s,i) for i in range(n)]
   for i,t in enumerate(tasks):
    validate(t)
    if s not in generator.AGREEMENT:assert t==old.item(child,split,s,i)
    fingerprint=old.digest({'query':t['query'],'evidence':t['evidence']});assert t['task_id'] not in ids and fingerprint not in facts;ids.add(t['task_id']);facts.add(fingerprint)
   name=f'{split}-{s}.json';p=PRIVATE/name;files[name]={'sha256':write(p,tasks),'count':n,'split':split,'stratum':s};private.append(p)
 manifest={'version':generator.VERSION,'seed_identity':seed_id,'generation_registration_sha256':regsha,'files':files,'total':2700,'dev_items':900,'reserve_items':1800,'reserve_per_stratum':200,'consumed_items':0,'source_sha256':pins,'candidate_designed_after_seal':False}
 manifestsha=write(PRIVATE/'manifest.json',manifest);assert write(E/'bank-v5-manifest.json',manifest)==manifestsha
 for p in private:p.chmod(0)
 assert all(p.stat().st_mode&0o777==0 for p in private)
 ledger={'version':generator.VERSION,'manifest_sha256':manifestsha,'reserve_consumed':0,'dev_consumed':0,'allocations':[]};write(PRIVATE/'consumption-ledger.json',ledger)
 for name,d in pins.items():assert h(ROOT/name)==d
 receipt={'sealed':True,'sealed_at':datetime.now(timezone.utc).isoformat(),'manifest_sha256':manifestsha,'generation_registration_sha256':regsha,'validated_items':2700,'dev_items':900,'reserve_items':1800,'reserve_per_stratum':200,'new_seed':True,'all_private_files_mode':'000','private_files_count':len(private),'directory_mode':'0700','model_calls':0,'GPU_hours':0,'compute_cost_usd':0,'wall_seconds':time.perf_counter()-started,'reserved_items_consumed':0,'dev_items_consumed':0,'candidate_evaluated_on_reserve':False,'private_directory':str(PRIVATE),'eligible_fresh_reserve':True,'execution_authorized':False}
 write(PRIVATE/'sealing-receipt.json',receipt);write(E/'bank-v5-sealing-receipt.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':
 def denied(*a,**kw):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',denied),patch.object(socket,'create_connection',denied):build()
