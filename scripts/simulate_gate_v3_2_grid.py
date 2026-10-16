"""Pre-registered budget-only proposal, independent scalar/vector parity, CPU only."""
import json, gzip, math, socket, sys
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nerve_awim.memory_gateway import scientific_promotion_gate_v3_2 as gate
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/galahad/evidence/gate-v3_2-coverage-grid'
ANSWER=np.array([gate.STRATA.index(s) for s in gate.ANSWER]);SAFE=np.array([3,4,8])
N=10000
def read(p):return json.loads(p.read_text())
def h(p):return sha256(p.read_bytes()).hexdigest()
def write(p,x):
 with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
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
def simulate(label,rates,probs,bad,seed,m):
 n=N;idx=np.arange(n);offset=idx%9;rng=np.random.default_rng(seed)
 counts=np.zeros((n,9),dtype=np.int16);disc=counts.copy();net=counts.copy()
 state=np.zeros(n,dtype=np.int8);primary=np.zeros(n,dtype=bool);covered=primary.copy();promote=primary.copy();veto=primary.copy()
 primary_items=np.zeros(n,dtype=np.int16);items=primary_items.copy();loge=np.zeros(n)
 first60=np.zeros((n,9),dtype=bool);terminal_bound=first60.copy();saved=[]
 priority=(np.arange(6)[None,:]-(offset%6)[:,None])%6
 for step in range(960):
  active=state!=2
  if not active.any():break
  u=rng.random((n,4));saved.append(u[:100].copy())
  complete=(disc[:,ANSWER]>=m)|((disc[:,ANSWER]==0)&(counts[:,ANSWER]>=60))
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
  complete=((disc[:,ANSWER]>=m)|((disc[:,ANSWER]==0)&(counts[:,ANSWER]>=60))).all(axis=1)
  ending=(state==1)&(complete|(step==959));covered[ending]=complete[ending]
  veto[ending]=complete[ending]&(net[ending][:,ANSWER]<0).any(axis=1)
  promote[ending]=complete[ending]&~veto[ending]
  terminal_bound[ending]=((disc[ending]==0)&(counts[ending]>=60))
  items[ending]+=40;state[ending]=2
 observed_bad=np.zeros(n,dtype=bool) if bad is None else disc[idx,bad]>0
 identified=np.zeros(n,dtype=bool) if bad is None else covered&(net[idx,bad]<0)
 bound_bad=np.zeros(n,dtype=bool) if bad is None else terminal_bound[idx,bad]
 first_bad=np.zeros(n,dtype=bool) if bad is None else first60[idx,bad]
 result={'streams':n,'accepted':int(promote.sum()),'accept_rate':float(promote.mean()),'nonpromotion_rate':float((~promote).mean()),'primary_accepts':int(primary.sum()),'coverage_incomplete':int((primary&~covered).sum()),'G1_false_veto':0,'G2_veto_count':int(veto.sum()),'G2_rejection_rate_all':float(veto.mean()),'G2_rejection_rate_evaluated':float(veto.sum()/covered.sum()) if covered.any() else None,'G2_identified_bad_rate_evaluated':float(identified.sum()/covered.sum()) if covered.any() else None,'evaluated_G2_count':int(covered.sum()),'primary_nonacceptance_count':int((~primary).sum()),'m':m,'identification_rate':float(identified.mean()) if bad is not None else None,'bad_stratum_loss_or_discordance_observed_rate':float(observed_bad.mean()) if bad is not None else None,'bad_stratum_bound_activated_count':int(bound_bad.sum()) if bad is not None else None,'bad_stratum_bound_activation_rate':float(bound_bad.mean()) if bad is not None else None,'bad_stratum_first60_certificate_count':int(first_bad.sum()) if bad is not None else None,'bad_stratum_promotions_with_bound':int((promote&bound_bad).sum()) if bad is not None else None,'any_answer_bound_activation_rate':float(terminal_bound[:,ANSWER].any(axis=1).mean()),'mean_items':float(items.mean()),'p90_items':float(np.quantile(items,.9)),'max_items':int(items.max()),'total_items':int(items.sum()),'risk_followups':int(primary.sum())}
 for name,value in [('mean',result['mean_items']),('p90',result['p90_items'])]:
  result[name+'_A40_minutes']=[value*t/60 for t in (2.3,3.4)];result[name+'_A40_usd']=[value*t/3600*.59 for t in (2.3,3.4)]
 for i in range(100):
  p=gate._Kernel(m=m,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=int(offset[i]));k=0
  while p.next_stratum() is not None:
   s=p.next_stratum();j=gate.STRATA.index(s)
   if p.phase=='risk' or s in gate.SAFETY:c=b=True
   else:
    u=saved[k][i];d=u[0]<rates[i,j];win=u[1]<probs[i,j];both=u[2]<.88;c=bool(win if d else both);b=bool(not win if d else both)
   p.update(item_id=str(p.items),stratum=s,candidate=c,incumbent=b,abstain=s in gate.SAFETY);k+=1
  assert p.items==items[i] and p.primary_accepted==bool(primary[i]) and p.coverage_complete==bool(covered[i]) and (p.verdict=='promote_proposal')==bool(promote[i]),(label,i,p.report())
  assert [p.counts[s] for s in gate.STRATA]==counts[i].tolist() and [p.net[s] for s in gate.STRATA]==net[i].tolist() and [p.discordance[s] for s in gate.STRATA]==disc[i].tolist()
 rows=[{'stream':i,'promoted':bool(promote[i]),'primary':bool(primary[i]),'covered':bool(covered[i]),'items':int(items[i]),'counts':counts[i].tolist(),'discordance':disc[i].tolist(),'net':net[i].tolist(),'first60_certificates':first60[i,ANSWER].tolist(),'terminal_bounds':terminal_bound[i,ANSWER].tolist()} for i in range(n)]
 raw=(json.dumps(rows,sort_keys=True,separators=(',',':'))+'\n').encode();file=OUT/(label+'-streams.json.gz');file.write_bytes(gzip.compress(raw,compresslevel=1,mtime=0))
 result['receipt']={'path':str(file.relative_to(ROOT)),'sha256':h(file),'raw_sha256':sha256(raw).hexdigest()};result['scalar_parity_streams']=100
 print(label,json.dumps({k:result[k] for k in ['accepted','nonpromotion_rate','mean_items','p90_items','bad_stratum_bound_activated_count']}),flush=True);return result

def register():
 OUT.mkdir(exist_ok=False)
 parent=ROOT/'docs/galahad/evidence/gate-v3_2-budget/registration.json'
 reg=read(parent)
 reg.update(gate='v3.2 coverage grid, unsigned',parent_registration_sha256=h(parent),coverage_grid=[12,14,16],seeds={'registered':{'main':2026101801,'H0':2026101802},'fresh':{'main':2026102401,'H0':2026102402}})
 reg['sampling']['main_cap']=960;reg['sampling']['total_cap']=1000
 reg['sampling']['coverage']='Only uncovered answer strata, least observed first with same rotated tie break. Coverage >=m discordances for m in12,14,16 OR zero in>=60 observations. Primary observations count. Main cap960 reserves40 risk items inside1000.'
 reg['scope']={'minimum_primary_discordance':.08,'denominator':'all nine equally weighted primary strata; not only agreement items','minimum_conditional_win_p':.85,'in_scope_profiles':['broad_75','narrow_64','measured'],'out_of_scope':['narrow_88'],'fixture_primary_discordance':{'broad_75':.25,'narrow_64':.08,'narrow_88':2*.12/9,'measured':(.22+.64)/9},'claim_limit':'Validation is for these declared profile families, including their registered regression/null alternatives. The8% floor is necessary, not a distribution-free power guarantee for every heterogeneous vector above it. Measured zeros outside agreement are assumptions, not proof.','admission':'Public Process requires prospective dev-scope evidence hash, profile and declared primary discordance before any holdout item. Below.08 or unvalidated profile returns insufficient_power immediately. No threshold inferred retrospectively from holdout outcomes. Study custodian must independently verify hash and registration provenance.','outside_diagnostic':'Run raw kernel for narrow88 without scope admission solely to report residual power/H0 and cost. Actual scope-enforced verdict is insufficient_power for every stream, zero accepted and zero items. Raw and admitted results remain separate.'}
 reg['targets']['qualification']='Smallest m satisfying all targets on broad75,narrow64,measured in BOTH original and fresh seeds. Additionally broad G2 identification among evaluated candidates >=.90, with raw out-of-scope H0<=.05. Silent5/10 regressions reported separately; no invented additional target.'
 reg['metric_decomposition']='Report any-route nonpromotion, primary nonacceptance, incomplete coverage, G2 rejection (all proposals and evaluated denominator), and identification of bad stratum separately. Historical v3 92% includes non-evaluations; never relabel total v3.2 nonpromotion as G2 alone.'
 paths=[Path(__file__),ROOT/'src/nerve_awim/memory_gateway/scientific_promotion_gate_v3_2.py',ROOT/'scripts/test_gate_v3_2_grid.py',parent,ROOT/'docs/galahad/evidence/gate-v3_2-budget/result.json',ROOT/'docs/galahad/evidence/gate-v3-confirmation-v1-result.json',ROOT/'docs/galahad/evidence/bank-v5-dev-study-result.json',ROOT/'docs/galahad/evidence/two-stage-rule-gated-safety-fixture.json']
 reg['sources']={str(p.relative_to(ROOT)):h(p) for p in paths};reg['verification']='100 independent scalar/vector parity streams per cell; public scope admission separately tested. Deterministic gzip level1 receipts. Original seed set completes before fresh; no tuning between sets.'
 write(OUT/'registration.json',reg);print('registered '+h(OUT/'registration.json'),flush=True)

def run():
 reg=read(OUT/'registration.json')
 for p,value in reg['sources'].items():assert h(ROOT/p)==value,p
 results={}
 for seedname in reg['seed_order']:
  for m in reg['coverage_grid']:
   for name in ('broad_75','narrow_64','narrow_88','measured'):
    for scenario in ('good_085','good_090','never_worse','regression','neutral','harmful','H0','silent_regression_05','silent_regression_10'):
     if scenario=='never_worse' and name!='measured':continue
     if scenario.startswith('silent') and name=='broad_75':continue
     rates,p,bad=fixture(name,scenario);label=f'{seedname}-m{m}-{name}-{scenario}'
     row=simulate(label,rates,p,bad,reg['seeds'][seedname]['H0' if scenario=='H0' else 'main'],m)
     row['scope_admitted']=name!='narrow_88';row['admitted_accepted']=row['accepted'] if name!='narrow_88' else 0
     if name=='narrow_88':row['actual_scoped_verdict']='insufficient_power';row['admitted_items']=0
     results[label]=row
     write(OUT/(label+'-result.json'),row)
 qualifications={};eligible=[]
 for m in reg['coverage_grid']:
  qualifications[str(m)]={}
  for seedname in reg['seed_order']:
   for name in reg['scope']['in_scope_profiles']:
    prefix=f'{seedname}-m{m}-{name}-'
    checks={'good_085':results[prefix+'good_085']['accept_rate']>=.8,'regression_nonpromotion':results[prefix+'regression']['nonpromotion_rate']>=.9,'H0':results[prefix+'H0']['accept_rate']<=.05,'harmful_zero':results[prefix+'harmful']['accepted']==0}
    if name=='broad_75':checks['G2_detection_evaluated']=results[prefix+'regression']['G2_identified_bad_rate_evaluated']>=.9
    qualifications[str(m)][seedname+'-'+name]=checks
   qualifications[str(m)][seedname+'-outside_H0']={'raw_H0':results[f'{seedname}-m{m}-narrow_88-H0']['accept_rate']<=.05,'admitted_H0':True}
  if all(all(row.values()) for row in qualifications[str(m)].values()):eligible.append(m)
 for p,value in reg['sources'].items():assert h(ROOT/p)==value,p
 write(OUT/'result.json',{'registration_sha256':h(OUT/'registration.json'),'results':results,'qualifications':qualifications,'eligible_m':eligible,'chosen_m':min(eligible) if eligible else None,'model_calls':0,'reserve_items_consumed':0,'payload_prepared':False})
 print(json.dumps({'eligible_m':eligible,'chosen_m':min(eligible) if eligible else None}),flush=True)
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('CPU only, no network')
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):
  if sys.argv[1]=='register':register()
  else:run()
