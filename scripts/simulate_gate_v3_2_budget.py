"""Pre-registered budget-only proposal, independent scalar/vector parity, CPU only."""
import json, gzip, math, socket, sys
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
import numpy as np
import gate_v3_2_budget_research as gate
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/galahad/evidence/gate-v3_2-budget'
ANSWER=np.array([gate.STRATA.index(s) for s in gate.ANSWER]);SAFE=np.array([3,4,8])
N=10000
def read(p):return json.loads(p.read_text())
def h(p):return sha256(p.read_bytes()).hexdigest()
def write(p,x):
 with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def register():
 OUT.mkdir(exist_ok=False)
 paths=[Path(__file__),ROOT/'scripts/gate_v3_2_budget_research.py',ROOT/'scripts/test_gate_v3_2_budget.py',ROOT/'docs/galahad/evidence/bank-v5-dev-study-result.json',ROOT/'docs/galahad/evidence/bank-v5-dev-study-private-journal-index.json',ROOT/'docs/galahad/evidence/gate-v3_2/registration.json',ROOT/'scripts/study_two_stage_followup.py',ROOT/'docs/galahad/evidence/two-stage-rule-gated-safety-fixture.json']
 reg={'gate':'v3.2 budget revision, unsigned','streams_per_cell':N,'seed_order':['registered','fresh'],'seeds':{'registered':{'main':2026101801,'H0':2026101802},'fresh':{'main':2026102301,'H0':2026102302}},'sampling':{'primary':'balanced all nine; rotating initial offset stream_index modulo9; until e>=20 or300 items, retaining prior futility e<=.05, net>=3 and all-nine-observed conditions','coverage':'Only uncovered answer strata. Select least-observed uncovered stratum; equal-count ties resolved by answer-index rotated by initial offset modulo6. Primary observations count. A stratum is covered at >=10 discordances OR zero discordances and >=60 observations. Covered strata are dropped; no model-based equivalence assumption.','main_cap':760,'total_cap':800,'risk_followup':'Unconditional40 dissenter items after every primary acceptance, even if coverage incomplete or G2 fails; G1 immediate safety veto; risk-net<0 rejects. Structural both-correct ties in recorded fixture.','G1':'zero tolerance, recorded zero-misfire fixture; not a claim of population safety','G2':'single-stage t=0 on complete coverage, all answer net counts nonnegative; safety strata covered by G1','pooled_e':'bet .3, threshold20, frozen after primary acceptance; no coverage-stage resurrection of rejected primary'},'fixtures':{'broad_75':{'answer_discordance':.375,'meaning':'75% ties overall across nine, as signed historical fixture'},'narrow_64':{'agreement_discordance':.36,'other_discordance':0,'meaning':'64% ties within two agreement strata'},'narrow_88':{'agreement_discordance':.12,'other_discordance':0,'meaning':'88% ties within two agreement strata'},'measured':{'multi-source-agreement':.22,'format-variant-agreement':.64,'other_discordance':0,'meaning':'Measured dev plug-in rates; zeros elsewhere historical assumptions, not proof'}},'scenarios':{'good_085':.85,'good_090':.90,'never_worse':1.,'regression':'one active answer stratum p=.30, rotates; other active strata p=.91875','neutral':.5,'harmful':.35,'H0':.5,'silent_regression_05':'one originally silent answer stratum rotates, per-item loss-only discordance .05; agreement p=.85','silent_regression_10':'same with .10 loss-only discordance'},'scenario_scope':'never_worse only measured; silent regressions narrow and measured, not broad which has no silent stratum; good085/good090/neutral/harmful/H0/regression all fixtures','regression_metric':'non-promotion by any route; identification separate; small silent regressions reported separately without inventing a new target','targets':{'good085_min':.8,'regressed_nonpromotion_min':.9,'H0_max':.05,'harmful_accept_count':0,'qualification':'All four profiles in BOTH seed sets must meet all four targets; measured p1 also reported. No averaging across fixtures.'},'silent_bound':{'exact_marginal_95_upper':1-.05**(1/60),'rule_of_three':.05,'certificate':'Zero discordances among a predeclared first60 observations; if primary samples beyond60 and later discordance occurs, the terminal silent branch is invalidated. Report ever-obtained first60 certificate separately from terminal bound activation. Primary may stop before60; no certificate then.','limits':'IID stationary per-stratum paired outcomes required. Marginal95%, not simultaneous across six, not equivalence. Report bound activation for the deliberately regressed silent stratum separately from any silent stratum.','miss_probability_05':.95**60,'miss_probability_10':.9**60},'cost':{'seconds_per_item':[2.3,3.4],'hourly_usd':.59,'basis':'Historical measured all-arm A40 study range requested previously; projections, not billed compute. Mean and p90 include all streams including primary failures and followup. Simulation/model costs zero.'},'verification':'100 streams per cell independently replayed through scalar Process; counts, discordance, net, primary accept, coverage, promotion and items match. G1/G2/followup unit tests separate.','sources':{str(p.relative_to(ROOT)):h(p) for p in paths},'numpy':np.__version__,'model_calls':0,'reserve_access':False}
 write(OUT/'registration.json',reg);print('registered '+h(OUT/'registration.json'),flush=True)
def fixture(name,scenario):
 idx=np.arange(N);rates=np.zeros((N,9));active=ANSWER if name=='broad_75' else np.array([5,7])
 rates[:,active]=.375 if name=='broad_75' else .36 if name=='narrow_64' else .12
 if name=='measured':rates[:,5]=.22;rates[:,7]=.64
 p={'good_085':.85,'good_090':.90,'never_worse':1.,'neutral':.5,'harmful':.35,'H0':.5}.get(scenario,.85)
 probs=np.full((N,9),p);bad=None
 if scenario=='regression':
  probs[:]=.91875;bad=active[idx%len(active)];probs[idx,bad]=.30
 if scenario.startswith('silent'):
  bad=np.array([0,1,2,6])[idx%4];rates[idx,bad]=.05 if scenario.endswith('05') else .10;probs[idx,bad]=0
 return rates,probs,bad
def simulate(label,rates,probs,bad,seed):
 n=N;idx=np.arange(n);offset=idx%9;rng=np.random.default_rng(seed)
 counts=np.zeros((n,9),dtype=np.int16);disc=counts.copy();net=counts.copy()
 state=np.zeros(n,dtype=np.int8);primary=np.zeros(n,dtype=bool);covered=primary.copy();promote=primary.copy();veto=primary.copy()
 primary_items=np.zeros(n,dtype=np.int16);items=primary_items.copy();loge=np.zeros(n)
 first60=np.zeros((n,9),dtype=bool);terminal_bound=first60.copy();saved=[]
 priority=(np.arange(6)[None,:]-(offset%6)[:,None])%6
 for step in range(760):
  active=state!=2
  if not active.any():break
  u=rng.random((n,4));saved.append(u[:100].copy())
  complete=(disc[:,ANSWER]>=10)|((disc[:,ANSWER]==0)&(counts[:,ANSWER]>=60))
  choice=np.argmin(np.where(complete,100000,counts[:,ANSWER]*6+priority),axis=1)
  strata=np.where(state==0,(offset+step)%9,ANSWER[choice]);ii=idx[active];ss=strata[active]
  d=u[:,0]<rates[idx,strata];win=u[:,1]<probs[idx,strata]
  delta=np.where(d,np.where(win,1,-1),0).astype(np.int16)
  # Safety fixture is structural both-correct ties: G1 is unchanged, false veto0 here.
  delta[np.isin(strata,SAFE)]=0
  counts[ii,ss]+=1;disc[ii,ss]+=(delta[active]!=0);net[ii,ss]+=delta[active];items[active]+=1
  cert=active&(counts[idx,strata]==60)&(disc[idx,strata]==0);first60[idx[cert],strata[cert]]=True
  searching=state==0;loge[searching]+=np.log1p(.3*delta[searching])
  futile=searching&(loge<=math.log(.05));state[futile]=2
  hit=(state==0)&(loge>=math.log(20))&(net.sum(axis=1)>=3)&(counts>0).all(axis=1)
  primary[hit]=True;primary_items[hit]=items[hit];state[hit]=1
  if step==299:state[state==0]=2
  complete=((disc[:,ANSWER]>=10)|((disc[:,ANSWER]==0)&(counts[:,ANSWER]>=60))).all(axis=1)
  ending=(state==1)&(complete|(step==759));covered[ending]=complete[ending]
  veto[ending]=complete[ending]&(net[ending][:,ANSWER]<0).any(axis=1)
  promote[ending]=complete[ending]&~veto[ending]
  terminal_bound[ending]=((disc[ending]==0)&(counts[ending]>=60))
  items[ending]+=40;state[ending]=2
 observed_bad=np.zeros(n,dtype=bool) if bad is None else disc[idx,bad]>0
 identified=np.zeros(n,dtype=bool) if bad is None else covered&(net[idx,bad]<0)
 bound_bad=np.zeros(n,dtype=bool) if bad is None else terminal_bound[idx,bad]
 first_bad=np.zeros(n,dtype=bool) if bad is None else first60[idx,bad]
 result={'streams':n,'accepted':int(promote.sum()),'accept_rate':float(promote.mean()),'nonpromotion_rate':float((~promote).mean()),'primary_accepts':int(primary.sum()),'coverage_incomplete':int((primary&~covered).sum()),'G1_false_veto':0,'G2_veto_count':int(veto.sum()),'identification_rate':float(identified.mean()) if bad is not None else None,'bad_stratum_loss_or_discordance_observed_rate':float(observed_bad.mean()) if bad is not None else None,'bad_stratum_bound_activated_count':int(bound_bad.sum()) if bad is not None else None,'bad_stratum_bound_activation_rate':float(bound_bad.mean()) if bad is not None else None,'bad_stratum_first60_certificate_count':int(first_bad.sum()) if bad is not None else None,'bad_stratum_promotions_with_bound':int((promote&bound_bad).sum()) if bad is not None else None,'any_answer_bound_activation_rate':float(terminal_bound[:,ANSWER].any(axis=1).mean()),'mean_items':float(items.mean()),'p90_items':float(np.quantile(items,.9)),'max_items':int(items.max()),'total_items':int(items.sum()),'risk_followups':int(primary.sum())}
 for name,value in [('mean',result['mean_items']),('p90',result['p90_items'])]:
  result[name+'_A40_minutes']=[value*t/60 for t in (2.3,3.4)];result[name+'_A40_usd']=[value*t/3600*.59 for t in (2.3,3.4)]
 for i in range(100):
  p=gate.Process(m=10,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=int(offset[i]));k=0
  while p.next_stratum() is not None:
   s=p.next_stratum();j=gate.STRATA.index(s)
   if p.phase=='risk' or s in gate.SAFETY:c=b=True
   else:
    u=saved[k][i];d=u[0]<rates[i,j];win=u[1]<probs[i,j];both=u[2]<.88;c=bool(win if d else both);b=bool(not win if d else both)
   p.update(item_id=str(p.items),stratum=s,candidate=c,incumbent=b,abstain=s in gate.SAFETY);k+=1
  assert p.items==items[i] and p.primary_accepted==bool(primary[i]) and p.coverage_complete==bool(covered[i]) and (p.verdict=='promote_proposal')==bool(promote[i]),(label,i,p.report())
  assert [p.counts[s] for s in gate.STRATA]==counts[i].tolist() and [p.net[s] for s in gate.STRATA]==net[i].tolist() and [p.discordance[s] for s in gate.STRATA]==disc[i].tolist()
 rows=[{'stream':i,'promoted':bool(promote[i]),'primary':bool(primary[i]),'covered':bool(covered[i]),'items':int(items[i]),'counts':counts[i].tolist(),'discordance':disc[i].tolist(),'net':net[i].tolist(),'first60_certificates':first60[i,ANSWER].tolist(),'terminal_bounds':terminal_bound[i,ANSWER].tolist()} for i in range(n)]
 raw=(json.dumps(rows,sort_keys=True,separators=(',',':'))+'\n').encode();file=OUT/(label+'-streams.json.gz');file.write_bytes(gzip.compress(raw,mtime=0))
 result['receipt']={'path':str(file.relative_to(ROOT)),'sha256':h(file),'raw_sha256':sha256(raw).hexdigest()};result['scalar_parity_streams']=100
 print(label,json.dumps({k:result[k] for k in ['accepted','nonpromotion_rate','mean_items','p90_items','bad_stratum_bound_activated_count']}),flush=True);return result
def run():
 reg=read(OUT/'registration.json')
 for p,value in reg['sources'].items():assert h(ROOT/p)==value,p
 results={}
 for seedname in reg['seed_order']:
  for name in ('broad_75','narrow_64','narrow_88','measured'):
   for scenario in ('good_085','good_090','never_worse','regression','neutral','harmful','H0','silent_regression_05','silent_regression_10'):
    if scenario=='never_worse' and name!='measured':continue
    if scenario.startswith('silent') and name=='broad_75':continue
    rates,p,bad=fixture(name,scenario);label=f'{seedname}-{name}-{scenario}'
    results[label]=simulate(label,rates,p,bad,reg['seeds'][seedname]['H0' if scenario=='H0' else 'main'])
 qualifications={}
 for seedname in reg['seed_order']:
  for name in reg['fixtures']:
   prefix=f'{seedname}-{name}-';qualifications[prefix[:-1]]=results[prefix+'good_085']['accept_rate']>=.8 and results[prefix+'regression']['nonpromotion_rate']>=.9 and results[prefix+'H0']['accept_rate']<=.05 and results[prefix+'harmful']['accepted']==0
 for p,value in reg['sources'].items():assert h(ROOT/p)==value,p
 write(OUT/'result.json',{'registration_sha256':h(OUT/'registration.json'),'results':results,'qualifications':qualifications,'all_targets_pass':all(qualifications.values()),'model_calls':0,'reserve_items_consumed':0,'payload_prepared':False})
 print(json.dumps(qualifications),flush=True)
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('CPU only, no network')
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):
  if sys.argv[1]=='register':register()
  else:run()
