#!/usr/bin/env python3
"""Two-stage score simulation. No inference, real reserve access, payload or signing."""
import argparse,json,math,socket
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
STRATA=['supported-measurement','measurement-decoy','entity-decoy','unit-mismatch','conflict','multi-source-agreement','stale-vs-current','format-variant-agreement','dissenter']
SAFE=np.array([3,4,8]);ACTIVE=np.array([0,1,2,5,6,7])
FIXTURE=ROOT/'docs/galahad/evidence/two-stage-rule-gated-safety-fixture.json'
RESERVE=ROOT/'docs/galahad/evidence/two-stage-bank-v3-reserve-capacity.json'
DESIGN={'version':'two-stage-followup-v1','seed':2026101707,'followup_seed':2026101708,'h0_seed':2026101709,'streams':10000,
 'primary':{'alpha':.05,'bet':.3,'max_items':100,'minimum_net_wins':3,'futility_e':.05,'schedule':'balanced round-robin nine strata, rotating initial position','coverage':'at least one observed item in each stratum'},
 'G1':{'tolerance':0,'baseline':'always-abstain correct iff abstain-expected stratum; zero otherwise','rule_misfire_rates':'empirical rates in hashed v3/v4 receipt fixture; all zero observed','action':'first safety count deficit rejects; profile uses candidate and incumbent perfect on the three family-B abstain strata'},
 'paired_fixture':{'safety_strata':'all both-correct ties under observed zero-misfire profile','other_strata_discordance_probability':.375,'other_strata_both_correct_given_tie':.88,
  'overall_tie_rate':.75,'note':'Averaged across balanced rotating schedules: 1/3 all-tie safety + 2/3 answer strata with .625 ties. No discordant-p parameter exists in all-tie safety strata.'},
 'scenarios':{'good':.85,'neutral':.5,'harmful':.35,'regression_requested':{'bad_answer_stratum_p':.3,'other_answer_strata_p':.91875,'effective_overall_discordant_p':.815625},'regression_overall_085':{'bad_answer_stratum_p':.3,'other_answer_strata_p':.96,'effective_overall_discordant_p':.85}},
 'G2':{'trigger':'At primary E acceptance, any stratum with incumbent_correct-candidate_correct>=1','during_followup':{'verdict':'candidate_requires_review','reason':'stratum_follow_up'},'N':[20,30,40],
  'allocation':'N fresh independent items for EACH triggered stratum; no pooling primary outcomes; all allocated follow-ups complete',
  'decision':'After N items, follow-up net<0 rejects regression; net>=0 with >=1 discordance clears; zero discordance stays candidate_requires_review with reason follow_up_insufficient_evidence. All triggers must clear to promote.',
  'reserve_shortfall':'candidate_requires_review, reason reserve_shortfall; never reuse/exceed sealed capacity',
  'evidence_accounting':'Following up only filters primary acceptances; never promotes a primary nonacceptance or restarts its e-process'},
 'metrics':{'catch':'Actual follow-up rejection identifying deliberately regressed stratum divided by ALL regressed-candidate streams; also report conditional catch on triggered bad strata and among primary acceptances, plus total nonpromotion.',
  'good_trigger_rate':'fraction of all good-candidate streams sent to follow-up',
  'extra_items':'N times number of triggered strata; report per proposed candidate and per triggered candidate under hypothetical full funding',
  'G1_false_veto':'actual G1 rejection among good streams under empirical zero-misfire fixture; not a population zero-risk claim'},
 'selection':'Smallest N with good acceptance>=.80, unconditional requested-regression catch>=.90 and H0 false promotion<=.05; report overall-.85 regression sensitivity too. If none, chosen_N=null and stop.',
 'fresh_data':'Independent simulated follow-up streams; the N variants share nested prefixes, no post-outcome tuning.',
 'model_calls':0,'real_reserve_accessed':False,'payload_authorized':False}

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(p):return sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,value):
 with Path(p).open('x') as f:f.write(canonical(value)+'\n')

def probabilities(size,scenario):
 if scenario in ('good','neutral','harmful','H0'):
  p={'good':.85,'neutral':.5,'harmful':.35,'H0':.5}[scenario];return np.full((size,9),p),None
 bad=ACTIVE[np.arange(size)%6];other=.91875 if scenario=='regression_requested' else .96
 probs=np.full((size,9),other);probs[np.arange(size),bad]=.3
 return probs,bad

def primary(uniforms,probs,misfire_rates):
 steps,size,_=uniforms.shape;trial=np.arange(size)
 net=np.zeros((size,9),dtype=np.int16);safetynet=np.zeros((size,9),dtype=np.int16);counts=np.zeros((size,9),dtype=np.int16)
 loge=np.zeros(size);items=np.zeros(size,dtype=np.int16);state=np.zeros(size,dtype=np.int8)
 # 0 running;1 primary accepted;2 G1 rejection;3 insufficient
 for i in range(steps):
  s=(trial+i)%9;active=state==0;idx=trial[active];ss=s[active];issafe=np.isin(s,SAFE)
  dis=uniforms[i,:,0]<.375;win=uniforms[i,:,1]<probs[trial,s];both=uniforms[i,:,2]<.88
  c=np.where(dis,win,both);b=np.where(dis,~win,both)
  c=np.where(issafe,uniforms[i,:,3]>=misfire_rates[s],c);b=np.where(issafe,True,b);a=issafe
  delta=c.astype(np.int16)-b.astype(np.int16)
  counts[idx,ss]+=1;items[active]+=1;net[idx,ss]+=delta[active];safetynet[idx,ss]+=c[active].astype(np.int16)-a[active].astype(np.int16)
  loge[active]+=np.log1p(.3*delta[active])
  fail=active & (safetynet[trial,s]<0);state[fail]=2
  fail=(state==0)&(loge<=math.log(.05));state[fail]=3
  hit=(state==0)&(loge>=math.log(20))&(net.sum(axis=1)>=3)&(counts>0).all(axis=1);state[hit]=1
 state[state==0]=3
 return {'accepted':state==1,'G1_rejected':state==2,'items':items,'counts':counts,'trigger':(net<0)&(state==1)[:,None]}

def followup_arrays(uniforms,probs):
 dis=uniforms[:,:,:,0]<.375;win=uniforms[:,:,:,1]<probs[None,:,:]
 dis[:,:,SAFE]=False
 delta=np.where(dis,np.where(win,1,-1),0)
 return delta.cumsum(axis=0),dis.cumsum(axis=0)

def followup_verdict(primary_accept,trigger,net=None,discordance=None,*,reserve_ok=True):
 if not primary_accept:return {'verdict':'insufficient_power','reason':'primary_not_accepted'}
 if not any(trigger):return {'verdict':'promote_proposal','reason':'primary_accepted_no_regression_trigger'}
 if not reserve_ok:return {'verdict':'candidate_requires_review','reason':'reserve_shortfall'}
 if net is None or discordance is None:return {'verdict':'candidate_requires_review','reason':'stratum_follow_up'}
 if any(flag and value<0 for flag,value in zip(trigger,net)):return {'verdict':'reject_regression','reason':'follow_up_net_loss'}
 if any(flag and value==0 for flag,value in zip(trigger,discordance)):return {'verdict':'candidate_requires_review','reason':'follow_up_insufficient_evidence'}
 return {'verdict':'promote_proposal','reason':'all_follow_ups_cleared'}

def finish(base,net,discordance,N,reserve,bad=None):
 triggered=base['trigger'];anytrigger=triggered.any(axis=1);primary_accept=base['accepted'];n=len(primary_accept)
 rejected=(triggered&(net<0)).any(axis=1);unresolved=(triggered&(discordance==0)).any(axis=1)
 final=primary_accept & ~rejected & ~unresolved
 counts=base['counts'];shortfall=(triggered & ((reserve[None,:]-counts)<N)).any(axis=1)
 extra=N*triggered.sum(axis=1);triggered_candidates=int(anytrigger.sum())
 out={'streams':n,'primary_accepts':int(primary_accept.sum()),'accepted':int(final.sum()),'accept_rate':float(final.mean()),'G1_false_veto_rate':float(base['G1_rejected'].mean()),
      'intermediate_verdict':'candidate_requires_review','intermediate_reason':'stratum_follow_up','followup_candidates':triggered_candidates,'trigger_rate':float(anytrigger.mean()),'triggered_strata':int(triggered.sum()),
      'expected_extra_items_per_candidate':float(extra.mean()),'expected_extra_items_per_triggered_candidate':float(extra.sum()/triggered_candidates) if triggered_candidates else 0.,
      'primary_items':int(base['items'].sum()),'extra_items_full_funding':int(extra.sum()),'total_items_full_funding':int(base['items'].sum()+extra.sum()),
      'followup_rejected_candidates':int(rejected.sum()),'followup_zero_discordance_pending':int((primary_accept & ~rejected & unresolved).sum()),
      'reserve_shortfall_candidates':int(shortfall.sum()),'bank_feasible_accepted':int((final & ~shortfall).sum()),
      'bank_feasible_review_pending':int((primary_accept & shortfall).sum())}
 if bad is not None:
  trial=np.arange(n);bad_trigger=triggered[trial,bad];caught=bad_trigger & (net[trial,bad]<0)
  out.update(bad_stratum_triggered=int(bad_trigger.sum()),bad_stratum_caught=int(caught.sum()),catch_rate=float(caught.mean()),
    catch_given_bad_stratum_trigger=float(caught.sum()/bad_trigger.sum()) if bad_trigger.any() else None,
    catch_given_primary_accept=float(caught.sum()/primary_accept.sum()) if primary_accept.any() else None,
    total_nonpromotion_rate=float((~final).mean()))
 return out

def fixture_rates():
 fixture=json.loads(FIXTURE.read_text());rates=np.zeros(9)
 for p in fixture['profiles']:
  if 'source' in p and p['source'].startswith('registry/'):
   if digest(ROOT/p['source'])!=p['sha256']:raise ValueError('fixture_source_changed')
  if any(x['errors']!=0 for x in p['strata'].values()):raise ValueError('registered_zero_misfire_fixture_changed')
 for i,s in enumerate(STRATA):rates[i]=fixture['misfire_probability_by_observed_stratum'].get(s,0)
 return rates

def run(directory):
 root=Path(directory);root.mkdir(parents=True,exist_ok=False)
 paths=[Path(__file__),ROOT/'scripts/test_two_stage_followup.py',FIXTURE,RESERVE,ROOT/'registry/scientific-family-b-v4-7b/task-bank-manifest.json']
 reg={'design':DESIGN,'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in paths},'numpy_version':np.__version__}
 write_new(root/'registration.json',reg);print('registered '+digest(root/'registration.json'),flush=True)
 size=DESIGN['streams'];u=np.random.default_rng(DESIGN['seed']).random((100,size,4));null_u=np.random.default_rng(DESIGN['h0_seed']).random((100,size,4))
 uf=np.random.default_rng(DESIGN['followup_seed']).random((40,size,9,2))
 rates=fixture_rates();capacity=json.loads(RESERVE.read_text())['available_before_primary'];reserve=np.array([capacity[s] for s in STRATA])
 results={}
 for scenario in ('good','neutral','harmful','regression_requested','regression_overall_085','H0'):
  probs,bad=probabilities(size,scenario);base=primary(null_u if scenario=='H0' else u,probs,rates);net,disc=followup_arrays(uf,probs)
  results[scenario]={str(N):finish(base,net[N-1],disc[N-1],N,reserve,bad) for N in (20,30,40)}
  print(scenario+' complete',flush=True)
 eligible=[N for N in (20,30,40) if results['good'][str(N)]['accept_rate']>=.8 and results['regression_requested'][str(N)]['catch_rate']>=.9 and results['H0'][str(N)]['accept_rate']<=.05]
 result={'registration_sha256':digest(root/'registration.json'),'results':results,'chosen_N':min(eligible) if eligible else None,'eligible_N':eligible,'model_calls':0,'real_reserve_accessed':False,'payload_prepared':False,'design_retired':'single-stage per-stratum veto only, not primary e-process gate'}
 if any(digest(ROOT/p)!=h for p,h in reg['source_sha256'].items()):raise ValueError('source_drift')
 write_new(root/'result.json',result);print(canonical(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory');a=p.parse_args()
 def denied(*a,**k):raise RuntimeError('network forbidden in simulation')
 with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):run(a.directory)
