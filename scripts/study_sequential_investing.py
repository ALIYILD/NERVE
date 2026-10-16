#!/usr/bin/env python3
"""Isolated simulated-score ablations/alpha-investing. Never installs a gate."""
import argparse
import copy
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import random
import socket
import sys
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
spec=importlib.util.spec_from_file_location('original_sim',ROOT/'scripts/simulate_sequential_gate.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
from nerve_awim.memory_gateway.scientific_sequential_gate import Process
DESIGN={
 'version':'sequential-ablation-investing-v1','original_design':original.DESIGN,
 'variants':{'baseline':{},'wallet_off':{'alpha':.05},'plateau_off':{'minimum_net_wins':0},'stratum_veto_off':{'veto_enabled':False},'bet_doubled':{'bet':.6}},
 'fixed_veto_alpha':.00025,
 'investing':{'initial_wealth':.05,'spend_fraction':.1,'max_study_alpha':.05,'bonus':.05,
  'spend':'phi=min(0.1*wealth, 0.05/(1-0.05)); debit before study',
  'study_alpha':'phi/(1+phi)',
  'promotion_reward':'phi + 0.05 (refund registered debit plus fixed bonus); only terminal promotion',
  'nonpromotion_reward':0,'wealth_update':'W-phi + I(promotion)*(phi+0.05)',
  'source':'https://faculty.wharton.upenn.edu/wp-content/uploads/2011/11/Alpha-investing.pdf',
  'error_target':'mFDR_1, not strong family-wise error control; empirical all-null FWER also reported'},
 'null':{'streams':10000,'original_seed':2026101601,'horizon':200,'alpha':.05,'futility':0,
  'single_study':'original stress null: paired win/loss each .5, no ties, abstain false; original early-stop RNG consumption',
  'portfolios':10000,'studies_per_portfolio':200,'items_per_study':100,'portfolio_seed':2026101602,
  'portfolio_fixture':'independent fair discordant win/loss; actual investing, futility, plateau and coverage; five round-robin strata; no domain violation; abstain false'},
 'targets':{'harmful_accept_rate_max':.01,'good_accept_rate_min':.8,'items_consumed_lt':20000,'global_null_familywise_rate_max':.05},
 'policy_inputs':'Only paired outcomes, strata, past verdicts and wealth; never proposal classes.',
 'registration_timing':'Source and parameters frozen before any new simulated draws; original published results already known.',
 'model_calls':0,'holdout_accessed':False,'canonical_gate_changed':False,'installation_authorized':False}

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def write_new(path,value):
 with Path(path).open('x') as f:f.write(canonical(value)+'\n')

def gate_config(**changes):
 g=dict(original.registration(0)['gate']);g.update(veto_enabled=True,veto_alpha=.00025);g.update(changes);return g

def run_rows(rows,g):
 log_e=0.;net=0;reverse={s:0. for s in g['strata']};counts={s:0 for s in g['strata']}
 reason='item_budget';verdict='insufficient_power'
 for n,row in enumerate(rows[:g['item_budget']],1):
  s=row['stratum'];delta=int(row['candidate'])-int(row['incumbent'])
  log_e+=math.log1p(g['bet']*delta);net+=delta;counts[s]+=1
  reverse[s]+=math.log1p(g['bet']*(int(row['always_abstain'])-int(row['candidate'])))
  if row.get('violations',False) or (g['veto_enabled'] and reverse[s]>=-math.log(g['veto_alpha']/len(reverse))):verdict='retain_incumbent';reason='domain_or_stratum_veto';break
  if g['futility_e'] and log_e<=math.log(g['futility_e']):verdict='retain_incumbent';reason='registered_futility_bound';break
  if log_e>=-math.log(g['alpha']) and net>=g['minimum_net_wins'] and all(counts.values()):verdict='promote_proposal';reason='e_threshold_and_plateau';break
 return dict(verdict=verdict,reason=reason,items=n,log_e=log_e,net_wins=net)

class Investing:
 def __init__(self):self.wealth=DESIGN['investing']['initial_wealth'];self.pending=None
 def start(self):
  if self.pending is not None:raise ValueError('unresolved_study')
  w=self.wealth;phi=min(DESIGN['investing']['spend_fraction']*w,.05/.95)
  if not math.isfinite(phi) or phi<=0:raise ValueError('wealth_exhausted')
  self.wealth-=phi;self.pending=dict(wealth_before=w,spend=phi,alpha=min(.05,phi/(1+phi)));return dict(self.pending)
 def settle(self,verdict):
  if self.pending is None:raise ValueError('no_registered_debit')
  if verdict not in ('promote_proposal','retain_incumbent','insufficient_power'):raise ValueError('terminal_verdict_required')
  reward=self.pending['spend']+.05 if verdict=='promote_proposal' else 0
  self.wealth+=reward;entry=dict(self.pending,reward=reward,wealth_after=self.wealth,verdict=verdict);self.pending=None;return entry

def fixtures():
 d=original.DESIGN;rng=random.Random(d['seed'])
 classes=[k for k,n in d['classes'].items() for _ in range(n)];rng.shuffle(classes)
 bank=[dict(stratum=s,incumbent=rng.random()<.5,always_abstain=rng.random()<.2,random=rng.random()<.15) for _ in range(20) for s in d['strata']]
 studies=[]
 for i,label in enumerate(classes):
  p=d['discordant_win_probabilities'][label]
  reused=[dict(row,candidate=rng.random()<p) for row in bank]
  rows=[dict(item,candidate=rng.random()<p,incumbent=rng.random()<.5,always_abstain=rng.random()<.2,random=rng.random()<.15) for item in original.registration(i)['schedule']]
  studies.append(dict(label=label,reused=reused,rows=rows))
 return studies

def metric():return dict(accepted={k:0 for k in original.DESIGN['classes']},items_consumed=0)
def tally(m,label,accepted,items):m['accepted'][label]+=int(accepted);m['items_consumed']+=items

def simulation():
 studies=fixtures();metrics={name:metric() for name in (*DESIGN['variants'],'investing','slice_reuse','slice_fresh_matched')};ledger=[];reports=[];wallet=Investing()
 for i,study in enumerate(studies):
  rows=study['rows'];label=study['label'];per={}
  for name,changes in DESIGN['variants'].items():
   report=run_rows(rows,gate_config(**changes));per[name]=report
   tally(metrics[name],label,report['verdict']=='promote_proposal',report['items'])
  admission=wallet.start();report=run_rows(rows,gate_config(alpha=admission['alpha']))
  entry=wallet.settle(report['verdict']);ledger.append(dict(study=i,**entry));per['investing']=report
  tally(metrics['investing'],label,report['verdict']=='promote_proposal',report['items'])
  for name,key in [('slice_reuse','reused'),('slice_fresh_matched','rows')]:tally(metrics[name],label,original.slice_accept(study[key]),100)
  reports.append(dict(study=i,proposal_class=label,reports=per))
 for m in metrics.values():
  for label,n in original.DESIGN['classes'].items():m[label+'_accept_rate']=m['accepted'][label]/n
 # Exact regression check against historical published results, not a tuning criterion.
 old=json.loads((ROOT/'docs/galahad/evidence/sequential-gate-sim-v1.json').read_text())['metrics']
 for new,prior in [('baseline','sequential_wallet'),('slice_reuse','current_slice_naive_reuse'),('slice_fresh_matched','current_slice_fresh_matched')]:
  if metrics[new]!=old[prior]:raise ValueError('historical_reproduction_mismatch:'+new)
 return dict(metrics=metrics,ledger=ledger,studies=reports,fixtures_sha256=sha256(canonical(studies).encode()).hexdigest(),historical_metrics_identical=True)

def null_single(alpha):
 rng=random.Random(DESIGN['null']['original_seed']);crossings=0
 # Exact original H0 test mechanism, changing only primary test alpha when requested.
 g=gate_config(alpha=alpha,item_budget=200,strata=['s'],futility_e=0)
 for _ in range(10000):
  p=Process(g)
  for _ in range(200):
   win=rng.random()<.5;p.update(candidate=win,incumbent=not win,abstain=False,stratum='s')
   if p.verdict!='running':break
  crossings+=p.verdict=='promote_proposal'
 return dict(streams=10000,crossings=crossings,rate=crossings/10000,alpha=alpha,horizon=200,futility_e=0)

def null_portfolios():
 import numpy as np
 rng=np.random.default_rng(DESIGN['null']['portfolio_seed']);size=10000
 wealth=np.full(size,.05);rejects=np.zeros(size,dtype=np.int64);used=0
 for study in range(200):
  phi=np.minimum(.1*wealth,.05/.95);alpha=np.minimum(.05,phi/(1+phi));wealth-=phi
  log_e=np.zeros(size);net=np.zeros(size,dtype=np.int64);active=np.ones(size,dtype=bool);promoted=np.zeros(size,dtype=bool)
  for item in range(100):
   # Generate full fixed streams even for stopped portfolios; masks prevent consumption.
   delta=np.where(rng.random(size)<.5,1,-1)
   used+=int(active.sum());log_e[active]+=np.log1p(.3*delta[active]);net[active]+=delta[active]
   futile=active & (log_e<=math.log(.05));active[futile]=False
   hit=active & (log_e>=-np.log(alpha)) & (net>=3) & (item>=4)
   promoted|=hit;active[hit]=False
  wealth+=promoted*(phi+.05);rejects+=promoted
 return dict(portfolios=size,studies_per_portfolio=200,items_per_study=100,
             false_promotions=int(rejects.sum()),portfolios_with_false_promotion=int((rejects>0).sum()),
             familywise_type_i_rate=float((rejects>0).mean()),alpha=.05,
             marginal_false_discovery_ratio_eta1=float(rejects.sum()/(rejects.sum()+size)),
             per_study_false_promotion_rate=float(rejects.sum()/(size*200)),items_consumed=used,
             wealth_min=float(wealth.min()),numpy_version=np.__version__)

def run(directory):
 root=Path(directory);root.mkdir(parents=True,exist_ok=False)
 paths=[Path(__file__),ROOT/'scripts/test_sequential_investing_study.py',ROOT/'scripts/simulate_sequential_gate.py',ROOT/'scripts/run_scientific_runpod_gate.py',*sorted((ROOT/'src').rglob('*.py'))]
 registration=dict(design=DESIGN,sources={str(p.relative_to(ROOT)):digest(p) for p in paths})
 write_new(root/'registration.json',registration)
 print('registered '+digest(root/'registration.json'),flush=True)
 result=simulation();print('simulation complete; historical metrics reproduced',flush=True)
 result['h0_original']=null_single(.05);print('original H0 complete',flush=True)
 initial=Investing().start()['alpha'];result['h0_initial_investing_study']=null_single(initial);print('investing first-study H0 complete',flush=True)
 result['h0_investing_portfolios']=null_portfolios();print('10000 all-null investing portfolios complete',flush=True)
 m=result['metrics']['investing'];h=result['h0_investing_portfolios']
 result['targets']={'harmful':m['harmful_accept_rate']<=.01,'power':m['good_accept_rate']>=.8*result['metrics']['slice_reuse']['good_accept_rate'],'items':m['items_consumed']<result['metrics']['slice_reuse']['items_consumed'],'type_i_global_null':h['familywise_type_i_rate']<=.05,'type_i_first_study':result['h0_initial_investing_study']['rate']<=initial}
 result.update(registration_sha256=digest(root/'registration.json'),model_calls=0,holdout_accessed=False,canonical_gate_changed=False,installed=False)
 result['all_targets_met']=all(result['targets'].values())
 if any(digest(ROOT/p)!=h for p,h in registration['sources'].items()):raise ValueError('source_drift')
 write_new(root/'result.json',result)
 print(canonical({k:v for k,v in result.items() if k not in ('studies','ledger')}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('directory');args=parser.parse_args()
 def denied(*a,**k):raise RuntimeError('network forbidden in score simulation')
 with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):run(args.directory)
