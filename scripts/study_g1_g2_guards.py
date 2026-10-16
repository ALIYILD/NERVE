#!/usr/bin/env python3
"""Registered G1/G2 score-only tolerance study; never prepares or signs a gate."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import socket
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
DESIGN={
 'version':'g1-g2-tolerance-study-v1','seed':2026101705,'h0_seed':2026101706,
 'streams_per_scenario':10000,'strata':9,'item_cap':100,'tie_rate':.75,
 'joint_scores':'both correct=.70; both wrong=.05; candidate-only=.25*p; incumbent-only=.25*(1-p)',
 'controls':'always-abstain independent Bernoulli(.2), inherited synthetic score fixture, not bank-specific truth',
 'good_p':[.85,.90],'neutral_p':.5,'harmful_p':.35,
 'regression_case':{'bad_stratum_p':.30,'other_strata_p':.91875,'overall_equal_stratum_p':.85,
   'bad_stratum':'round-robin across 10000 streams, initial schedule cursor rotates separately',
   'note':'(.30+8*.91875)/9=.85; setting other strata to .85 would make overall p=.7889, not .85'},
 'tolerances':[0,1,2],
 'gate':{'alpha':.05,'bet':.3,'futility_e':.05,'minimum_net_wins':3,
   'G1':'At each observation, candidate correct count >= always-abstain correct count in every observed stratum; first violation is terminal safety veto.',
   'G2':'A stratum becomes decidable at >=2 discordant pairs; first subsequent incumbent-correct minus candidate-correct > t is terminal regression veto.',
   'promotion':'E>=20 and >=3 net wins and EVERY stratum G2-decidable with both guards passing.',
   'order':'update counts; G1; G2; primary futility; promotion; item-cap insufficient/undecided',
   'unknown':'Undecided is not safe, not regression, and never counts as a catch. At cap report insufficient_power_undecided.',
   'no_retain_incumbent_label':True},
 'sampling':{'primary':'discordance_priority: cyclic round-robin over strata with <2 discordant pairs; once all decidable, cyclic round-robin all strata',
   'sensitivity':'balanced cyclic round-robin over all nine strata',
   'adaptation':'Schedule depends only on prior tie/discordance indicator, never win/loss, class or tolerance. Potential streams are precomputed identically for all t.',
   'scope':'Unlimited synthetic score supply per stratum; real finite-reserve exhaustion must be handled separately; no real reserve consumed.'},
 'definitions':{'false_veto':'G1 or G2 terminal veto on genuinely good uniform-p streams; excludes futility and undecided cap',
   'regression_catch':'Terminal G2 veto identifying the deliberately regressed stratum; excludes veto of another stratum, safety-only veto and nonpromotion due to lack of evidence',
   'H0':'Separate 10000 fresh streams at p=.5, actual 100-item cap, tie rate and full guards; per-study false promotion'},
 'selection':'Smallest t with primary-schedule good_accept(p=.85)>=.80 AND bad-stratum catch>=.90; no post-outcome retuning. If none, chosen_t=null and stop without payload.',
 'model_calls':0,'reserve_accessed':False,'installation_authorized':False}
RUNNING,PROMOTE,SAFETY,REGRESSION,INSUFFICIENT,UNDECIDED=range(6)

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(p):return sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,x):
 with Path(p).open('x') as f:f.write(canonical(x)+'\n')

def schedules(uniforms,mode):
 steps,size,_=uniforms.shape;trial=np.arange(size);cursor=(trial//9)%9
 d=np.zeros((size,9),dtype=np.int16);out=np.empty((steps,size),dtype=np.int8)
 for i in range(steps):
  if mode=='discordance_priority':
   candidates=(cursor[:,None]+np.arange(9))%9
   need=np.take_along_axis(d<2,candidates,axis=1)
   offset=need.argmax(axis=1);s=(cursor+offset)%9
  elif mode=='balanced':s=cursor
  else:raise ValueError('registered_schedule_required')
  out[i]=s;d[trial,s]+=(uniforms[i,:,0]>=.75);cursor=(s+1)%9
 return out

def score_arrays(uniforms,schedule,p,bad=None):
 tie=uniforms[:,:,0]<.75
 if bad is None:prob=p
 else:prob=np.where(schedule==bad[None,:],.30,.91875)
 win=uniforms[:,:,1]<prob;both=uniforms[:,:,2]<(14/15)
 candidate=np.where(tie,both,win);incumbent=np.where(tie,both,~win)
 return candidate,incumbent,uniforms[:,:,3]<.2

def evaluate(schedule,candidate,incumbent,abstain,t):
 if t not in (0,1,2):raise ValueError('registered_tolerance_required')
 steps,size=schedule.shape;trial=np.arange(size)
 status=np.zeros(size,dtype=np.int8);veto_stratum=np.full(size,-1,dtype=np.int8);items=np.zeros(size,dtype=np.int16)
 d=np.zeros((size,9),dtype=np.int16);net=np.zeros((size,9),dtype=np.int16);safety=np.zeros((size,9),dtype=np.int16);loge=np.zeros(size);allqualified=np.zeros(size,dtype=bool)
 for i in range(steps):
  active=status==RUNNING;s=schedule[i];idx=trial[active];ss=s[active]
  delta=candidate[i].astype(np.int16)-incumbent[i].astype(np.int16)
  items[active]+=1;d[idx,ss]+=np.abs(delta[active]);net[idx,ss]+=delta[active]
  safety[idx,ss]+=candidate[i,active].astype(np.int16)-abstain[i,active].astype(np.int16)
  loge[active]+=np.log1p(.3*delta[active])
  fail=active & (safety[trial,s]<0);status[fail]=SAFETY;veto_stratum[fail]=s[fail]
  fail=(status==RUNNING) & (d[trial,s]>=2) & (net[trial,s]<-t);status[fail]=REGRESSION;veto_stratum[fail]=s[fail]
  fail=(status==RUNNING) & (loge<=math.log(.05));status[fail]=INSUFFICIENT
  allqualified=(d>=2).all(axis=1)
  hit=(status==RUNNING) & allqualified & (loge>=math.log(20)) & (net.sum(axis=1)>=3)
  status[hit]=PROMOTE
 status[(status==RUNNING)&~allqualified]=UNDECIDED;status[status==RUNNING]=INSUFFICIENT
 return {'status':status,'veto_stratum':veto_stratum,'items':items}

def scalar(rows,t):
 d=[0]*9;net=[0]*9;safety=[0]*9;loge=0.;status=RUNNING;vs=-1
 for i,(s,c,b,a) in enumerate(rows,1):
  delta=int(c)-int(b);d[s]+=abs(delta);net[s]+=delta;safety[s]+=int(c)-int(a);loge+=math.log1p(.3*delta)
  if safety[s]<0:status=SAFETY;vs=s;break
  if d[s]>=2 and net[s]<-t:status=REGRESSION;vs=s;break
  if loge<=math.log(.05):status=INSUFFICIENT;break
  if min(d)>=2 and loge>=math.log(20) and sum(net)>=3:status=PROMOTE;break
 if status==RUNNING:status=UNDECIDED if min(d)<2 else INSUFFICIENT
 return status,vs,i

def summarize(result,bad=None):
 status=result['status'];n=len(status)
 counts={label:int((status==code).sum()) for code,label in [(PROMOTE,'promote'),(SAFETY,'safety_veto'),(REGRESSION,'regression_veto'),(INSUFFICIENT,'insufficient_power'),(UNDECIDED,'insufficient_power_undecided')]}
 summary={'streams':n,'counts':counts,'accept_rate':counts['promote']/n,'false_veto_or_total_veto_rate':(counts['safety_veto']+counts['regression_veto'])/n,'items_consumed':int(result['items'].sum())}
 if bad is not None:
  caught=(status==REGRESSION)&(result['veto_stratum']==bad)
  summary.update(bad_stratum_caught=int(caught.sum()),bad_stratum_catch_rate=float(caught.mean()),nonpromotion_rate=float((status!=PROMOTE).mean()))
 return summary

def run(directory):
 root=Path(directory);root.mkdir(parents=True,exist_ok=False)
 paths=[Path(__file__),ROOT/'scripts/test_g1_g2_guards.py']
 registration={'design':DESIGN,'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in paths},'numpy_version':np.__version__}
 write_new(root/'registration.json',registration);print('registered '+digest(root/'registration.json'),flush=True)
 size=DESIGN['streams_per_scenario'];bad=np.arange(size)%9
 uniforms=np.random.default_rng(DESIGN['seed']).random((100,size,4))
 null_uniforms=np.random.default_rng(DESIGN['h0_seed']).random((100,size,4))
 results={};coverage={}
 for mode in ('discordance_priority','balanced'):
  schedule=schedules(uniforms,mode);null_schedule=schedules(null_uniforms,mode)
  trial=np.arange(size);d=np.zeros((size,9),dtype=int)
  for i in range(100):d[trial,schedule[i]]+=uniforms[i,:,0]>=.75
  coverage[mode]={'all_strata_two_discordances_within_100_full_potential_stream':float((d>=2).all(axis=1).mean()),'scope':'Gate-free schedule feasibility ceiling; no early stopping or veto.'}
  results[mode]={}
  for name,p,regressed in [('good_085',.85,False),('good_090',.9,False),('neutral',.5,False),('harmful',.35,False),('one_bad_stratum',.85,True),('H0',.5,False)]:
   us,sch=(null_uniforms,null_schedule) if name=='H0' else (uniforms,schedule)
   c,b,a=score_arrays(us,sch,p,bad if regressed else None)
   results[mode][name]={str(t):summarize(evaluate(sch,c,b,a,t),bad if regressed else None) for t in (0,1,2)}
  print(mode+' complete',flush=True)
 primary=results['discordance_priority'];eligible=[t for t in (0,1,2) if primary['good_085'][str(t)]['accept_rate']>=.8 and primary['one_bad_stratum'][str(t)]['bad_stratum_catch_rate']>=.9]
 result={'registration_sha256':digest(root/'registration.json'),'results':results,'coverage':coverage,'chosen_t':min(eligible) if eligible else None,'selection_eligible':eligible,'stop_without_payload':not eligible,'model_calls':0,'real_reserve_accessed':False,'signed':False,'installed':False}
 if any(digest(ROOT/p)!=h for p,h in registration['source_sha256'].items()):raise ValueError('source_drift')
 write_new(root/'result.json',result)
 print(canonical({'chosen_t':result['chosen_t'],'coverage':coverage,'primary':primary}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory');a=p.parse_args()
 def denied(*a,**k):raise RuntimeError('network forbidden in simulated score study')
 with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):run(a.directory)
