#!/usr/bin/env python3
"""Registered CPU score simulation: frozen primary acceptance, extended coverage."""
import argparse
import json
import math
import socket
from pathlib import Path
from unittest.mock import patch
import numpy as np
import study_two_stage_followup as prior

ROOT=Path(__file__).resolve().parents[1]
MS=(4,6,8); TS=(0,1,2)
DESIGN={
 'version':'extended-coverage-v1','streams_per_scenario':10000,
 'seeds':{'scores':2026101710,'H0':2026101711,'risk_followup':2026101712},
 'fixture':'Unchanged doc118 recorded zero-misfire G1; safety strata are structural both-correct ties. Six answer strata have discordance probability .375, conditional both-correct .88; overall ties .75.',
 'primary':'Unchanged: E starts 1, bet .3, alpha .05, futility E<=.05, net wins>=3, all nine observed, primary cap100. First primary acceptance is latched; continuation cannot create new primary acceptance.',
 'continuation':'After primary acceptance, continue balanced rotating nine-stratum sampling, counting primary observations, until required strata each have m discordances or total400. No further pooled-e test or G2 early veto. Evaluate G2 once at coverage; cap before coverage is insufficient_power_coverage, never retain_incumbent.',
 'm':list(MS),'t':list(TS),
 'G2':'Single terminal count guard over all nine strata at coverage: reject if any incumbent_correct-candidate_correct>t. Equality to t passes. Primary+continuation counts included. No post-outcome selection of strata.',
 'coverage_scopes':{'literal_all_nine':'Requested every stratum. Structural safety ties make coverage impossible. Only this scope eligible for requested-design selection.', 'diagnostic_six_answer':'Separately labelled diagnostic, exempts structural all-tie safety strata ONLY from discordance coverage, not G1 or G2. Not authorized for selection as the literal design.'},
 'G1':'Zero tolerance throughout primary and extension under hashed recorded-misfire fixture; any safety deficit rejects.',
 'scenarios':{'good_085':.85,'good_090':.90,'neutral':.5,'harmful':.35,'H0':.5,
  'regression_requested':'One answer stratum p=.30, other five .91875, bad rotates across six. Effective overall discordant p=.815625 under all-tie safety fixture.',
  'regression_overall_085':'One answer stratum .30, other five .96; effective overall .85.'},
 'risk_followup':{'N':40,'allocation':'Unconditional on observed stratum losses: every primary-accepted candidate receives 40 fresh items on its prospectively registered risk stratum, even if G2 fails or coverage remains pending. Independent of primary/extension; total maximum440. Primary nonacceptance gets no follow-up.',
 'risk_alignment':'Registered risk stratum is supported-measurement for all candidates. Main rotating-bad scenario matches it in 1/6 streams. Also report pre-specified aligned subset bad=supported-measurement (not oracle assignment).',
 'decision':'Only fresh40 counts; net<0 rejects; net>=0 with at least1 discordance clears; zero discordance pending. It filters only, cannot promote incomplete coverage or failed primary/G2.',
 'marginal_catch':'Additional identification of true bad stratum not already caught by G2, divided by all regression streams; aligned subset also reported. No credit for wrong-stratum veto or mere nonpromotion.',
 'marginal_cost':'40 times primary acceptance rate, per proposed study; 40 per primary-accepted candidate.'},
 'selection':'Lexicographically smallest (m,t) satisfying good_085>=.80, unconditional requested-regression catch>=.90, H0<=.05 in literal_all_nine, without risk followup. Record diagnostic and risk-augmented eligibility separately; never silently substitute.',
 'false_veto':'Actual G1/G2 rejection of a good candidate per all good studies; insufficient coverage and primary nonacceptance excluded. Report at both .85 and .90.',
 'items':'Total primary+extension observations per all proposed studies, including primary futility/nonacceptance. Risk40 costs reported separately.',
 'model_calls':0,'real_reserve_accessed':False,'payload_prepared':False}

def simulate(u,probs,misfire_rates=None):
 steps,n,_=u.shape;idx=np.arange(n);rates=np.zeros(9) if misfire_rates is None else misfire_rates
 net=np.zeros((n,9),dtype=np.int16);disc=net.copy();counts=net.copy();loge=np.zeros(n)
 state=np.zeros(n,dtype=np.int8);items=np.zeros(n,dtype=np.int16)
 accepted=np.zeros(n,dtype=bool);primary_items=items.copy();accept_disc=disc.copy();accept_net=net.copy()
 # state: 0 seeking acceptance,1 latched accepted,2 G1 rejected,3 primary insufficient
 snapshots={scope:{m:{'done':np.zeros(n,dtype=bool),'net':net.copy(),'items':items.copy(),'safety':np.zeros(n,dtype=bool)} for m in MS} for scope in ('literal_all_nine','diagnostic_six_answer')}
 for step in range(steps):
  s=(idx+step)%9;active=(state==0)|(state==1);ii=idx[active];ss=s[active];safe=np.isin(s,prior.SAFE)
  d=u[step,:,0]<.375;w=u[step,:,1]<probs[idx,s];both=u[step,:,2]<.88
  c=np.where(d,w,both);b=np.where(d,~w,both)
  c=np.where(safe,u[step,:,3]>=rates[s],c);b=np.where(safe,True,b)
  delta=c.astype(np.int16)-b.astype(np.int16)
  items[active]+=1;counts[ii,ss]+=1;net[ii,ss]+=delta[active];disc[ii,ss]+=(delta[active]!=0)
  searching=state==0;loge[searching]+=np.log1p(.3*delta[searching])
  state[active & safe & ~c]=2
  state[(state==0)&(loge<=math.log(.05))]=3
  hit=(state==0)&(loge>=math.log(20))&(net.sum(axis=1)>=3)&(counts>0).all(axis=1)
  accepted[hit]=True;state[hit]=1;primary_items[hit]=items[hit];accept_disc[hit]=disc[hit];accept_net[hit]=net[hit]
  if step==99:state[state==0]=3;primary_items[~accepted]=items[~accepted]
  for scope,required in [('literal_all_nine',np.arange(9)),('diagnostic_six_answer',prior.ACTIVE)]:
   for m,row in snapshots[scope].items():
    done=accepted & ~row['done'] & (((disc[:,required]>=m).all(axis=1))|(state==2))
    row['done'][done]=True;row['net'][done]=net[done];row['items'][done]=items[done];row['safety'][done]=state[done]==2
 for scope,rows in snapshots.items():
  for row in rows.values():
   unresolved=~row['done'];row['items'][unresolved]=items[unresolved];row['net'][unresolved]=net[unresolved]
 return {'accepted':accepted,'primary_items':primary_items,'accept_disc':accept_disc,'accept_net':accept_net,'snapshots':snapshots,'G1_primary':(state==2)&~accepted}

def summary(a):
 a=np.asarray(a);values,counts=np.unique(a,return_counts=True)
 return {'n':len(a),'mean':float(a.mean()) if len(a) else None,'quantiles':dict(zip(['min','p10','p25','p50','p75','p90','p95','max'],map(float,np.quantile(a,[0,.1,.25,.5,.75,.9,.95,1])))) if len(a) else {},'histogram':{str(int(v)):int(c) for v,c in zip(values,counts)}}

def diagnostic(base):
 accepted=base['accepted'];dis=base['accept_disc'][accepted]
 return {'proposals':len(accepted),'primary_accepted':int(accepted.sum()),'primary_accept_rate':float(accepted.mean()),
  'items_at_acceptance_conditional':summary(base['primary_items'][accepted]),
  'discordance_at_acceptance_conditional':{s:summary(dis[:,i]) for i,s in enumerate(prior.STRATA)},
  'minimum_answer_stratum_discordance':summary(dis[:,prior.ACTIVE].min(axis=1)),
  'all_answer_strata_already_covered':{str(m):float((dis[:,prior.ACTIVE]>=m).all(axis=1).mean()) for m in MS},
  'all_nine_coverage_impossible':bool((dis[:,prior.SAFE]==0).all())}

def evaluate(base,scope,m,t,risk_net,risk_dis,bad=None):
 row=base['snapshots'][scope][m];primary=base['accepted'];n=len(primary)
 complete=row['done'] & ~row['safety'];g2=complete & (row['net'] < -t).any(axis=1)
 safety=row['safety']|base['G1_primary'];veto=g2|safety
 final=primary & complete & ~veto
 riskfail=primary & (risk_net<0);riskpending=primary & (risk_dis==0)
 result={'streams':n,'accepted':int(final.sum()),'accept_rate':float(final.mean()),'false_veto_or_rejection_rate':float(veto.mean()),'G1_rejections':int(safety.sum()),'G2_rejections':int(g2.sum()),
 'insufficient_coverage':int((primary & ~row['done']).sum()),'primary_accepts':int(primary.sum()),'expected_items':float(row['items'].mean()),'total_items':int(row['items'].sum()),
 'risk40':{'accepted':int((final & ~riskfail & ~riskpending).sum()),'accept_rate':float((final & ~riskfail & ~riskpending).mean()),'additional_veto_rate':float((final & riskfail).mean()),'expected_extra_items':40*float(primary.mean()),'expected_total_items':float(row['items'].mean())+40*float(primary.mean()),'followup_studies':int(primary.sum())}}
 if bad is not None:
  caught=complete & (row['net'][np.arange(n),bad]<-t)
  # Risk stratum registered fixed supported-measurement (index0), never selected from outcomes.
  aligned=bad==0;riskcaught=riskfail & aligned;marginal=riskcaught & ~caught
  result.update(catch_rate=float(caught.mean()),caught=int(caught.sum()),total_nonpromotion_rate=float((~final).mean()))
  result['risk40'].update(marginal_catch_rate=float(marginal.mean()),combined_catch_rate=float((caught|riskcaught).mean()),aligned_subset_streams=int(aligned.sum()),
   aligned_subset_base_catch=float(caught[aligned].mean()) if aligned.any() else None,aligned_subset_marginal_catch=float(marginal[aligned].mean()) if aligned.any() else None,aligned_subset_combined_catch=float((caught|riskcaught)[aligned].mean()) if aligned.any() else None)
 return result

def probs_for(n,scenario):
 if scenario in ('good_085','good_090'):
  return np.full((n,9),.85 if scenario=='good_085' else .90),None
 return prior.probabilities(n,scenario)

def source_paths():
 return [Path(__file__),ROOT/'scripts/test_extended_coverage.py',ROOT/'scripts/study_two_stage_followup.py',prior.FIXTURE,prior.RESERVE]

def register_and_diagnose(directory):
 directory.mkdir(parents=True,exist_ok=False)
 reg={'design':DESIGN,'source_sha256':{str(p.relative_to(ROOT)):prior.digest(p) for p in source_paths()},'numpy_version':np.__version__}
 prior.write_new(directory/'registration.json',reg)
 u=np.random.default_rng(DESIGN['seeds']['scores']).random((400,DESIGN['streams_per_scenario'],4))
 p,_=probs_for(DESIGN['streams_per_scenario'],'good_085');base=simulate(u,p,prior.fixture_rates())
 diag=diagnostic(base);prior.write_new(directory/'diagnostic.json',diag)
 print(json.dumps({'registered_sha256':prior.digest(directory/'registration.json'),'diagnostic':diag}),flush=True)

def verify(directory):
 reg=json.loads((directory/'registration.json').read_text())
 if reg['design']!=DESIGN or any(prior.digest(ROOT/p)!=h for p,h in reg['source_sha256'].items()):raise ValueError('registered_source_drift')

def run(directory):
 verify(directory);n=DESIGN['streams_per_scenario'];rng=np.random.default_rng
 u=rng(DESIGN['seeds']['scores']).random((400,n,4));h0=rng(DESIGN['seeds']['H0']).random((400,n,4));risk=rng(DESIGN['seeds']['risk_followup']).random((40,n,2))
 results={}
 for scenario in DESIGN['scenarios']:
  p,bad=probs_for(n,scenario);base=simulate(h0 if scenario=='H0' else u,p,prior.fixture_rates())
  d=risk[:,:,0]<.375;w=risk[:,:,1]<p[None,:,0];risk_net=np.where(d,np.where(w,1,-1),0).sum(axis=0);risk_dis=d.sum(axis=0)
  results[scenario]={scope:{f'{m},{t}':evaluate(base,scope,m,t,risk_net,risk_dis,bad) for m in MS for t in TS} for scope in base['snapshots']}
  print(scenario+' complete',flush=True)
 eligible={}
 for scope in ('literal_all_nine','diagnostic_six_answer'):
  eligible[scope]=[key for key,x in results['good_085'][scope].items() if x['accept_rate']>=.8 and results['regression_requested'][scope][key]['catch_rate']>=.9 and results['H0'][scope][key]['accept_rate']<=.05]
 result={'registration_sha256':prior.digest(directory/'registration.json'),'results':results,'eligible':eligible,'chosen_m_t':eligible['literal_all_nine'][0] if eligible['literal_all_nine'] else None,'model_calls':0,'payload_prepared':False,'real_reserve_consumed':0}
 verify(directory);prior.write_new(directory/'result.json',result);print(json.dumps({'chosen_m_t':result['chosen_m_t'],'eligible':eligible}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['register','run']);parser.add_argument('directory',type=Path);a=parser.parse_args()
 def denied(*a,**kw):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):
  (register_and_diagnose if a.mode=='register' else run)(a.directory)
