"""Pre-register/run/replay the fixed 100-item dev-only bank discrimination study.

Run requires a separately supplied attended-operation authorization receipt.
Never opens reserve files; SSH requests execute only on the bound A40 pod.
"""
import sys,json,time,subprocess,os,fcntl,ipaddress,socket
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import run_scientific_family_b_v4_sweden as historical
from nerve_awim.memory_gateway import scientific_family_b_v5 as candidate
from nerve_awim.memory_gateway.scientific_bank_v3_truth import validate
from run_v5_signed_gate_study import v5score
from nerve_awim.memory_gateway.retained_promotion_gate import verify
from run_v5_identity_replay import write,digest
E=ROOT/'docs/galahad/evidence';BANK=Path('/Users/aliyildirim/nerve-research-runs/scientific-bank-v5-20261016')
BASE=Path('/Users/aliyildirim/nerve-research-runs/bank-v5-dev-discrimination-20261016')
STRATA=('multi-source-agreement','format-variant-agreement');SEED=2026102101
def read(p):return json.loads(p.read_text())
def replace(p,x):
 tmp=p.with_suffix('.pending');tmp.write_text(json.dumps(x,sort_keys=True,indent=2)+'\n');tmp.chmod(0o600);os.replace(tmp,p)
def sources():
 paths=[Path(__file__),ROOT/'scripts/bank_v5_fallback_remote.py',ROOT/'scripts/run_v5_signed_gate_study.py',ROOT/'scripts/run_scientific_family_b_v4_sweden.py',ROOT/'scripts/run_scientific_runpod_gate.py']
 paths+=list((ROOT/'src/nerve_awim/memory_gateway').glob('scientific*.py'))
 return {str(p.relative_to(ROOT)):digest(p) for p in paths}
def register():
 assert read(BANK/'sealing-receipt.json')['sealed'];assert digest(BANK/'manifest.json')==read(E/'bank-v5-sealing-receipt.json')['manifest_sha256']
 verify();BASE.mkdir(mode=0o700)
 order={s:sorted(range(100),key=lambda i:sha256(f'{SEED}:{s}:{i}'.encode()).hexdigest())[:50] for s in STRATA}
 schedule=[{'stratum':s,'dev_index':order[s][i]} for i in range(50) for s in STRATA]
 write(BASE/'schedule.json',schedule)
 registration={'version':'bank-v5-dev-discrimination-v1','created_at':datetime.now(timezone.utc).isoformat(),'seed':SEED,'dev_only':True,'task_count':100,'per_stratum':{s:50 for s in STRATA},'schedule_sha256':digest(BASE/'schedule.json'),'selection':'50 seed-ranked indices per agreement dev file; alternating strata, no outcome-based selection','bank_manifest_sha256':digest(BANK/'manifest.json'),'gate_version_for_future_simulation':'signed v3, unchanged; v3.1 unsigned and not used','candidate':'unchanged family-B v5','incumbent':'retained family-B v4','arms':['v4','v5'],'model':historical.transport.MODEL,'model_digest':historical.transport.DIGEST,'runtime':'0.40.5','gpu':'NVIDIA A40','pod_id':'lvojhtouu5gede','model_seed':20261016,'temperature':0,'max_tokens':128,'concurrency':1,'timeout_seconds':41.27330717537552,'timeout_basis':'3 x prior measured13.757769058458507-second max, doc122 preflight','retry_limit':2,'retry_on':'timeout only, identical requests, journaled','max_model_attempts':300,'wall_budget_seconds':1500,'pod_budget_seconds':1800,'hourly_usd':.59,'operational_authority':'awaiting explicit user start instruction; authorization receipt and live connection/identity receipt required before any inference','source_sha256':sources(),'source_hashing':'once at study start; independent once on replay','metrics':['v4 error rate','discordance rate','v5 wins/losses/ties','v4/v5 correctness','decoded byte equivalence vs numeric equivalence','per-stratum counts and Wilson intervals'],'verdict':'dev_discrimination_only; no promotion, signing or holdout','stop_rule':'exactly100 dev items; no early optional stop except infrastructure/budget; stop pod and verify EXITED on success or failure','resimulation':{'gate':'v3 exactly as signed','seeds':{'main':2026101801,'H0':2026101802},'streams':10000,'m':10,'t':0,'primary_cap':100,'main_cap':460,'total_cap':500,'risk_N':40,'risk_stratum':'dissenter','fixture':'Use measured stratum-specific discordance and win fractions for the two agreement strata; unchanged strata use historical dev rates as explicit assumptions, not new measurements. Report both plug-in and uncertainty; no diffuse redistribution pretending every answer stratum has agreement-stratum discordance.','empty_discordance':'undefined conditional win probability, never invent p=1','reachability_limit':'If four other answer strata are structural ties in the plug-in fixture, six-stratum coverage is impossible at any cap. Zero observed is not proof of population zero.'},'new_allocation':False,'promotion_authorized':False}
 write(BASE/'registration.json',registration);write(E/'bank-v5-dev-study-registration.json',registration)
 print(json.dumps({'registered':True,'registration_sha256':digest(BASE/'registration.json'),'awaiting_pod_authorization':True,'holdout_accessed':False,'model_calls':0}))
def remote(connection,action,payload=None):
 host=str(ipaddress.ip_address(connection['host']));port=connection['port'];assert type(port)is int and 1<=port<=65535 and connection['pod_id']=='lvojhtouu5gede'
 cmd=['ssh','-p',str(port),'-i','/Users/aliyildirim/.ssh/id_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','root@'+host,'python3','/workspace/bank_v5_fallback_remote.py',action]
 r=subprocess.run(cmd,input=None if payload is None else json.dumps(payload),text=True,capture_output=True,check=True,timeout=180)
 return json.loads(r.stdout)
def execute(replay=False):
 reg=read(BASE/'registration.json')
 for p,h in reg['source_sha256'].items():assert digest(ROOT/p)==h,p
 assert digest(BASE/'schedule.json')==reg['schedule_sha256'];schedule=read(BASE/'schedule.json')
 if replay:
  def denied(*a,**kw):raise RuntimeError('offline replay')
  socket.socket=denied;globals()['remote']=denied;tasks=read(BASE/'private-tasks.json')
 else:
  auth=read(BASE/'operation-authorization.json');assert auth['authorized'] is True and auth['registration_sha256']==digest(BASE/'registration.json') and auth['maximum_pod_seconds']<=1800
  assert isinstance(auth['exact_user_authorization'],str) and auth['exact_user_authorization'].strip()
  connection=read(BASE/'connection.json');identity=remote(connection,'identity')
  assert identity['pod_id']==reg['pod_id'] and identity['runtime']=={'version':reg['runtime']} and identity['model_digest']==reg['model_digest'] and identity['gpu']==reg['gpu']
  write(BASE/'identity.json',identity);write(BASE/'connection-binding.json',{'connection_sha256':digest(BASE/'connection.json'),'authorization_sha256':digest(BASE/'operation-authorization.json')})
  lock=(BANK/'dev-study.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  ledger=read(BANK/'consumption-ledger.json');assert not ledger['allocations'] and ledger['reserve_consumed']==0 and ledger['dev_consumed']==0
  ledger['allocations']=[{'kind':'dev','registration_sha256':digest(BASE/'registration.json'),'count':100,'schedule_sha256':reg['schedule_sha256'],'state':'allocated'}];replace(BANK/'consumption-ledger.json',ledger)
  manifest=read(BANK/'manifest.json');assert digest(BANK/'manifest.json')==reg['bank_manifest_sha256'];pool={}
  for s in STRATA:
   name=f'dev-{s}.json';p=BANK/name;assert p.stat().st_mode&0o777==0
   try:p.chmod(0o400);assert digest(p)==manifest['files'][name]['sha256'];pool[s]=read(p)
   finally:p.chmod(0)
  tasks=[pool[x['stratum']][x['dev_index']] for x in schedule]
  for t in tasks:validate(t);assert t['split']=='dev'
  write(BASE/'private-tasks.json',tasks)
 rows=[];start=time.monotonic()
 for i,t in enumerate(tasks):
  p=historical.prepare(t,'candidate','src/nerve_awim/memory_gateway/scientific_family_b_v4.py');payload=historical.schedule([t],['candidate'],'src/nerve_awim/memory_gateway/scientific_family_b_v4.py')[0]['payload'];assert payload is not None
  body=historical.canonical(payload)
  if replay:
   expected=read(BASE/f'row-{i:03}.json');attempts=sorted(BASE.glob(f'attempt-{i:03}-*.json'));assert attempts
   for file in attempts:assert read(BASE/file.name.replace('attempt-','claim-'))['body_sha256']==sha256(body.encode()).hexdigest();result=read(file)
  else:
   assert time.monotonic()-start<reg['wall_budget_seconds']
   ledger['dev_consumed']=i+1;replace(BANK/'consumption-ledger.json',ledger)
   for retry in range(3):
    write(BASE/f'claim-{i:03}-{retry}.json',{'body_sha256':sha256(body.encode()).hexdigest()})
    result=remote(connection,'call',{'body':body,'timeout':reg['timeout_seconds']});write(BASE/f'attempt-{i:03}-{retry}.json',result)
    if result['status']=='ok':break
  assert result['status']=='ok';raw=historical.transport.decode(result['wire'])[0];a=historical.adapter.decode(raw,p);b=candidate.decide(t['query'],t['evidence']);scores={'v4':historical.score(raw,t,p),'v5':v5score(b,t,p)}
  row={'task_id':t['task_id'],'stratum':t['stratum'],'v4_decoded':a,'v5_decoded':b,'scores':scores,'byte_identical':historical.canonical(a)==historical.canonical(b)}
  if replay:assert row==expected
  else:write(BASE/f'row-{i:03}.json',row)
  rows.append(row)
  if not replay and (i+1)%10==0:print(json.dumps({'dev_completed':i+1}),flush=True)
 table={}
 for s in [*STRATA,'pooled']:
  selected=[r for r in rows if s=='pooled' or r['stratum']==s];n=len(selected);c=sum(r['scores']['v5']['strict_correct'] for r in selected);b=sum(r['scores']['v4']['strict_correct'] for r in selected)
  wins=sum(r['scores']['v5']['strict_correct'] and not r['scores']['v4']['strict_correct'] for r in selected);losses=sum(r['scores']['v4']['strict_correct'] and not r['scores']['v5']['strict_correct'] for r in selected);d=wins+losses
  table[s]={'n':n,'v4_correct':b,'v5_correct':c,'v4_error_rate':(n-b)/n,'v4_error_interval':historical.transport.wilson(n-b,n),'wins':wins,'losses':losses,'ties':n-d,'discordance_rate':d/n,'discordance_interval':historical.transport.wilson(d,n),'conditional_win_rate':wins/d if d else None,'conditional_win_interval':historical.transport.wilson(wins,d),'byte_identical':sum(r['byte_identical'] for r in selected)}
 report={'status':'dev_discrimination_only','registration_sha256':digest(BASE/'registration.json'),'per_stratum':table,'reserve_items_consumed':0,'promotion_authorized':False}
 if replay:
  assert report==read(BASE/'result.json');write(BASE/'replay.json',{'matched':True,'rows':100,'model_calls':0,'result_sha256':digest(BASE/'result.json')})
 else:
  write(BASE/'result.json',report);write(BASE/'execution.json',{'wall_seconds':time.monotonic()-start,'model_attempts':len(list(BASE.glob('attempt-*.json')))});ledger['allocations'][0]['state']='complete';replace(BANK/'consumption-ledger.json',ledger)
 print(json.dumps(report))
if __name__=='__main__':
 if sys.argv[1]=='register':register()
 elif sys.argv[1]=='run':execute()
 elif sys.argv[1]=='replay':execute(True)
 else:raise ValueError('action')
