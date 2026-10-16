"""Pre-registered v3.2 sensitivity; CPU only, no reserve or network access."""
import json, sys, socket, gzip
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
import numpy as np
import confirm_gate_v3 as old
import study_extended_coverage as engine
import gate_v3_2_research as gate
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/galahad/evidence/gate-v3_2'
ACTIVE=[gate.STRATA.index(s) for s in gate.ANSWER]
def digest(p):return sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def register():
 OUT.mkdir(exist_ok=False)
 paths=[Path(__file__),ROOT/'scripts/gate_v3_2_research.py',ROOT/'scripts/confirm_gate_v3.py',ROOT/'scripts/study_extended_coverage.py',ROOT/'scripts/study_two_stage_followup.py',old.fixture.FIXTURE,ROOT/'src/nerve_awim/memory_gateway/scientific_promotion_gate_v3.py',ROOT/'docs/galahad/evidence/bank-v5-dev-study-registration.json']
 reg={'version':'v3.2-proposal','streams':10000,'seeds':{'registered':{'main':2026101801,'H0':2026101802},'fresh':{'main':2026102201,'H0':2026102202}},'design':{'primary_cap':100,'main_cap':460,'total_cap':500,'m':10,'t':0,'silent_coverage':'0 discordances AND >=60 main items in a stratum','schedule':'UNCHANGED balanced all-nine; stream index modulo9 offset','risk_N':40,'risk_stratum':'dissenter','G1':'unchanged zero-tolerance; recorded-zero-misfire structural safety ties','G2':'unchanged t=0; safety also guarded by G1; nonnegative net required in every covered answer stratum'},'cap_obstruction':'With unchanged nine-stratum main schedule each stratum has <=52 observations at460; silent60 branch unreachable. Vector engine equals signed-v3 engine under this schedule; scalar v3.2 parity verifies this. No allocation change is authorized by this proposal.','ties_definition':{'narrow_64':'64% ties WITHIN two agreement strata, other seven structural ties','narrow_88':'88% ties WITHIN two agreement strata, other seven structural ties','broad_75':'historical75% ties OVERALL, six answer discordance .375, safety structural ties'},'scenarios':{'good_085':.85,'good_090':.90,'neutral':.5,'harmful':.35,'H0':.5,'regression':'one active answer p=.30 rotates; other active p=.91875','silent_regression_05':'one of four silent answer strata rotates, per-item .05 loss-only discordance; two agreement strata p=.85','silent_regression_10':'same, .10 loss-only discordance'},'silent_regression_scope':'narrow fixtures only; broad has no silent stratum','targets':{'good_085_min':.80,'regressed_nonpromotion_min':.90,'H0_max':.05,'harmful_accepts':0},'bound':{'confidence':.95,'fixed_n':60,'approximate_upper':.05,'exact_upper':1-.05**(1/60),'meaning':'Marginal fixed-sample binomial bound under iid/stationarity, not equivalence, not a simultaneous or anytime confidence sequence. First60 is predeclared; later nonzero discordance disqualifies silent coverage. No <=5% claim when fewer than60 observed.','miss_probability_05':.95**60,'miss_probability_10':.90**60},'measured_analysis':'After completed100-item dev study and offline replay, plug in each agreement stratum discordance/win rate separately; other strata historical zero as assumption, not proof. Also p=.85 and1 and Wilson upper discordance sensitivity (not joint bound); original and fresh seeds. Same gate and schedule, no holdout use.','v3_1':'withdrawn, preserve historical payload; no signature','source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in paths},'numpy':np.__version__,'model_calls':0}
 write(OUT/'registration.json',reg)
 print('registered '+digest(OUT/'registration.json'),flush=True)
def simulate(label,rates,probs,seed,bad=None):
 n=10000;idx=np.arange(n);u=np.random.default_rng(seed).random((460,n,4))
 for step in range(460):
  r=rates[idx,(idx+step)%9];u[step,:,0]=np.divide(u[step,:,0]*.375,r,out=np.ones(n),where=r>0)
 engine.MS=(10,);base=engine.simulate(u,probs,old.fixture.fixture_rates());risk=np.zeros(n,dtype=np.int16)
 result=old.measure(base,10,bad,risk)
 snap=base['snapshots']['diagnostic_six_answer'][10];accepted=base['accepted'];covered=snap['done']&~snap['safety'];net=snap['net'];promoted=accepted&covered&(net[:,ACTIVE]>=0).all(axis=1)&~snap['safety']
 items=snap['items'].astype(int)+40*accepted
 rows=[{'stream':int(i),'primary':bool(accepted[i]),'covered':bool(covered[i]),'promoted':bool(promoted[i]),'items':int(items[i]),'net':net[i].tolist()} for i in range(n)]
 raw=(json.dumps(rows,sort_keys=True,separators=(',',':'))+'\n').encode();compressed=gzip.compress(raw,mtime=0);file=OUT/(label+'-streams.json.gz');file.write_bytes(compressed)
 result['stream_receipt']={'path':str(file.relative_to(ROOT)),'sha256':digest(file),'uncompressed_sha256':sha256(raw).hexdigest()}
 for i in range(100):
  proc=gate.Process(m=10,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=i%9);step=0
  while proc.next_stratum() is not None:
   s=proc.next_stratum();j=gate.STRATA.index(s)
   if proc.phase=='risk' or s in gate.SAFETY:c=b=True
   else:
    d=u[step,i,0]<.375;win=u[step,i,1]<probs[i,j];both=u[step,i,2]<.88;c=bool(win if d else both);b=bool(not win if d else both)
   proc.update(item_id=str(proc.items),stratum=s,candidate=c,incumbent=b,abstain=s in gate.SAFETY);step+=1
  assert proc.items==items[i] and proc.primary_accepted==bool(accepted[i]) and (proc.verdict=='promote_proposal')==bool(promoted[i]) and proc.coverage_complete==bool(accepted[i] and covered[i]),(label,i,proc.report())
 result['scalar_parity_streams']=100;result['silent_60_bound_certificates']=0
 print(label, result['accepted'],flush=True);return result
def run(measured=False):
 reg=read(OUT/'registration.json')
 for p,h in reg['source_sha256'].items():assert digest(ROOT/p)==h,p
 results={};n=10000;idx=np.arange(n)
 if measured:
  B=Path('/Users/aliyildirim/nerve-research-runs/bank-v5-dev-discrimination-20261016');report=read(B/'result.json');replay=read(B/'replay.json');assert replay['matched'] and replay['result_sha256']==digest(B/'result.json')
  for seedname,seeds in reg['seeds'].items():
   for scenario in ('empirical','good_085','never_worse','optimistic_upper'):
    rates=np.zeros((n,9));probs=np.full((n,9),.85)
    for j in (5,7):
     r=report['per_stratum'][gate.STRATA[j]];rates[:,j]=r['discordance_rate'];probs[:,j]=r['conditional_win_rate'] if r['conditional_win_rate'] is not None else .5
    if scenario=='good_085':probs[:]=.85
    if scenario in ('never_worse','optimistic_upper'):probs[:]=1
    if scenario=='optimistic_upper':
     for j in ACTIVE:
      rates[:,j]=(1.96**2/(100+1.96**2)) if j not in (5,7) else report['per_stratum'][gate.STRATA[j]]['discordance_interval'][1]
    label=f'measured-{seedname}-{scenario}';results[label]=simulate(label,rates,probs,seeds['main'])
  write(OUT/'measured-result.json',{'registration_sha256':digest(OUT/'registration.json'),'dev_result_sha256':digest(B/'result.json'),'results':results,'model_calls':0})
  return
 for seedname,seeds in reg['seeds'].items():
  for fixture in ('narrow_64','narrow_88','broad_75'):
   active=[5,7] if fixture.startswith('narrow') else ACTIVE
   for scenario in reg['scenarios']:
    if scenario.startswith('silent') and fixture=='broad_75':continue
    rates=np.zeros((n,9));rates[:,active]=(.36 if fixture=='narrow_64' else .12 if fixture=='narrow_88' else .375)
    p=reg['scenarios'][scenario];probs=np.full((n,9),p if isinstance(p,float) else .85);bad=None
    if scenario=='regression':probs[:]=.91875;bad=np.array(active)[idx%len(active)];probs[idx,bad]=.30
    if scenario.startswith('silent'):
     bad=np.array([0,1,2,6])[idx%4];rates[idx,bad]=.05 if scenario.endswith('05') else .10;probs[idx,bad]=0
    label=f'{seedname}-{fixture}-{scenario}';results[label]=simulate(label,rates,probs,seeds['H0' if scenario=='H0' else 'main'],bad)
 write(OUT/'result.json',{'registration_sha256':digest(OUT/'registration.json'),'results':results,'model_calls':0,'payload_prepared':False})
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('CPU analysis network forbidden')
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):
  if sys.argv[1]=='register':register()
  else:run(sys.argv[1]=='measured')
