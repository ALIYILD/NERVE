#!/usr/bin/env python3
"""Round 2: exact power and simulated paired scores only; never installs a gate."""
import argparse
from collections import defaultdict
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import random
import socket
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('round1',ROOT/'scripts/study_sequential_investing.py')
r1=importlib.util.module_from_spec(spec);spec.loader.exec_module(r1)
DESIGN={
 'version':'sequential-round2-v1','seed':2026101703,'null_seed':2026101704,
 'good_discordant_probabilities':[.65,.85,.9,.95],'harmful_discordant_p':.35,'neutral_discordant_p':.5,
 'classes':{'harmful':40,'neutral':60,'good':100},'tie_probability':.75,'both_correct_given_tie':14/15,
 'joint_fixture':'P(win)=.25*p; P(loss)=.25*(1-p); P(both correct)=.70; P(both wrong)=.05',
 'calibration_scope':'75% ties is a user-supplied scenario, not reconstructed paired holdout data. At p=.92 the marginals are .93/.72, compatible with published totals but not identified by them.',
 'gate':{'fresh_alpha':.05,'bet':.3,'futility_e':.05,'minimum_net_wins':3,'item_budget':100,'veto_alpha':.00025},
 'strata':r1.original.DESIGN['strata'],'controls':{'always_abstain_p':.2,'random_p':.15},
 'power_grid':{'discordant_p':[.6,.7,.8,.9,.95],'discordant_pairs':[5,10,25,50,100],
  'outputs':['exact terminal P(E_n>=20)','exact anytime P(max E_k>=20, k<=n)'],
  'ties':'E multiplies by1 on a tie. Fixed discordant count n corresponds to 4n expected total items, not n items.'},
 'hundred_item_power':'Exact Markov recursion at random discordant count Binomial(100,.25), with futility; coverage cannot delay crossing before minimum12 discordances. Reverse safety veto ignored gives an upper bound on full-gate power.',
 'allocation':{'fresh':'alpha=.05 per study, no wealth debit and no reward; unique item IDs checked across studies',
  'reuse':'Only overlap enters alpha-investing; W0=.05; debit phi=min(.1W,.05/.95); alpha=min(.05,phi/(1+phi)); promotion refund phi plus bonus .05',
  'validity':'Overlapping items require a separate conditional-null validity certificate; absent certificate refuse reuse before outcomes or debit. Alpha-investing alone does not correct reuse dependence.',
  'claim':'Per-study type I on fresh data; no across-200 FWER claim.'},
 'null_streams':10000,'null_horizon_items':100,'null_discordant_p':.5,
 'comparison':'Both gates on the identical fresh score stream per proposal, including controls; different from historical naive-reuse fixture.',
 'targets':{'harmful_accept_max':.01,'good_power_min':.8,'fresh_type_i_max':.05,'items_lt':20000},
 'stop':'No seed/parameter tuning. If exact 100-item power upper bound at p=.85 is below .8, shelve this fixed specification; report higher-p results separately.',
 'model_calls':0,'holdout_accessed':False,'installed':False}

def exact_discordant(p,n):
 up=math.log1p(.3);down=math.log1p(-.3);threshold=math.log(20)
 terminal=sum(math.comb(n,w)*p**w*(1-p)**(n-w) for w in range(n+1) if w*up+(n-w)*down>=threshold)
 states={0:1.};hit=0.
 for k in range(1,n+1):
  nxt=defaultdict(float)
  for w,mass in states.items():
   for ww,pr in ((w+1,p),(w,1-p)):
    x=mass*pr
    if ww*up+(k-ww)*down>=threshold:hit+=x
    else:nxt[ww]+=x
  states=nxt
 return dict(discordant_p=p,discordant_pairs=n,expected_total_items=4*n,terminal=terminal,anytime=hit)

def exact_item_power(p,items=100,futility=True):
 # State (wins, losses) retains identical e-value through ties.
 up=math.log1p(.3);down=math.log1p(-.3);states={(0,0):1.};hit=0.;failed=0.;expected_used=0.
 for _ in range(items):
  expected_used+=sum(states.values());nxt=defaultdict(float)
  for (w,l),mass in states.items():
   for ww,ll,pr in ((w,l,.75),(w+1,l,.25*p),(w,l+1,.25*(1-p))):
    x=mass*pr;log_e=ww*up+ll*down
    if futility and log_e<=math.log(.05):failed+=x
    elif log_e>=math.log(20) and ww-ll>=3:hit+=x
    else:nxt[(ww,ll)]+=x
  states=nxt
 return dict(discordant_p=p,items=items,anytime_power=hit,futility_probability=failed,budget_probability=sum(states.values()),expected_items=expected_used)

class FreshReusePolicy:
 def __init__(self):self.seen=set();self.investing=r1.Investing();self.pending=None
 def admit(self,identities,*,conditional_null_verified=False):
  if self.pending is not None:raise ValueError('unsettled_study')
  if len(identities)!=len(set(identities)) or not identities:raise ValueError('unique_nonempty_items_required')
  overlap=bool(self.seen.intersection(identities))
  if overlap and not conditional_null_verified:raise ValueError('reuse_conditional_null_certificate_required')
  a=self.investing.start() if overlap else {'alpha':.05,'spend':0}
  self.pending='reuse' if overlap else 'fresh';self.seen.update(identities)
  return dict(mode=self.pending,**a)
 def settle(self,verdict):
  if self.pending is None:raise ValueError('no_study')
  if verdict not in ('promote_proposal','retain_incumbent','insufficient_power'):raise ValueError('terminal_required')
  receipt=self.investing.settle(verdict) if self.pending=='reuse' else {'alpha':.05,'spend':0,'reward':0,'wealth_after':self.investing.wealth}
  self.pending=None;return receipt

def rows_from_uniforms(us,p,schedule):
 rows=[]
 for item,(tie,sign,tie_correct,abstain,random_control) in zip(schedule,us):
  if tie<.75:candidate=incumbent=tie_correct<14/15
  else:candidate=sign<p;incumbent=not candidate
  rows.append(dict(item,candidate=candidate,incumbent=incumbent,always_abstain=abstain<.2,random=random_control<.15))
 return rows

def full_fixture(seed):
 rng=random.Random(seed);labels=[label for label,n in DESIGN['classes'].items() for _ in range(n)];rng.shuffle(labels)
 return [(label,[[rng.random() for _ in range(5)] for _ in range(100)]) for label in labels]

def simulate(p_good,fixture):
 metrics={name:r1.metric() for name in ('slice_fresh','sequential_fresh')};policy=FreshReusePolicy();reports=[]
 for i,(label,us) in enumerate(fixture):
  p={'good':p_good,'harmful':.35,'neutral':.5}[label];schedule=r1.original.registration(i)['schedule'];rows=rows_from_uniforms(us,p,schedule)
  admit=policy.admit([row['item_id'] for row in rows]);report=r1.run_rows(rows,r1.gate_config(alpha=admit['alpha']))
  settle=policy.settle(report['verdict'])
  r1.tally(metrics['slice_fresh'],label,r1.original.slice_accept(rows),100)
  r1.tally(metrics['sequential_fresh'],label,report['verdict']=='promote_proposal',report['items'])
  reports.append(dict(study=i,proposal_class=label,admission=admit,settlement=settle,report=report))
 for m in metrics.values():
  for label,n in DESIGN['classes'].items():m[label+'_accept_rate']=m['accepted'][label]/n
 return dict(good_discordant_p=p_good,metrics=metrics,studies=reports,reuse_studies=0)

def null_test():
 rng=random.Random(DESIGN['null_seed']);counts={'slice_fresh':0,'sequential_fresh':0};used={'slice_fresh':0,'sequential_fresh':0}
 for i in range(10000):
  us=[[rng.random() for _ in range(5)] for _ in range(100)]
  rows=rows_from_uniforms(us,.5,r1.original.registration(i)['schedule'])
  counts['slice_fresh']+=r1.original.slice_accept(rows);used['slice_fresh']+=100
  report=r1.run_rows(rows,r1.gate_config(alpha=.05));counts['sequential_fresh']+=report['verdict']=='promote_proposal';used['sequential_fresh']+=report['items']
 return {k:dict(crossings=counts[k],streams=10000,rate=counts[k]/10000,items_consumed=used[k],horizon=100) for k in counts}

def run(directory):
 root=Path(directory);root.mkdir(parents=True,exist_ok=False)
 paths=[Path(__file__),ROOT/'scripts/test_sequential_round2.py',ROOT/'scripts/study_sequential_investing.py',ROOT/'scripts/simulate_sequential_gate.py',ROOT/'scripts/run_scientific_runpod_gate.py',*sorted((ROOT/'src').rglob('*.py'))]
 registration=dict(design=DESIGN,sources={str(p.relative_to(ROOT)):r1.digest(p) for p in paths})
 r1.write_new(root/'registration.json',registration);print('registered '+r1.digest(root/'registration.json'),flush=True)
 grid=[exact_discordant(p,n) for p in DESIGN['power_grid']['discordant_p'] for n in DESIGN['power_grid']['discordant_pairs']]
 powers=[exact_item_power(p) for p in DESIGN['good_discordant_probabilities']]
 fixture=full_fixture(DESIGN['seed']);simulations=[simulate(p,fixture) for p in DESIGN['good_discordant_probabilities']]
 print('exact power and four 200-proposal scenarios complete',flush=True)
 h0=null_test();print('10000 paired H0 streams complete',flush=True)
 result=dict(registration_sha256=r1.digest(root/'registration.json'),power_grid=grid,power_100_items=powers,simulations=simulations,h0=h0,
  shared_uniforms_sha256=sha256(r1.canonical(fixture).encode()).hexdigest(),model_calls=0,holdout_accessed=False,installed=False,
  shelve_fixed_specification=next(x['anytime_power'] for x in powers if x['discordant_p']==.85)<.8,
  interpretation='Exact 100-item power omits reverse veto and hence upper-bounds full-gate power. Per-study H0 rates, not 200-study FWER.')
 if any(r1.digest(ROOT/p)!=h for p,h in registration['sources'].items()):raise ValueError('source_drift')
 r1.write_new(root/'result.json',result)
 print(r1.canonical({**result,'simulations':[{k:v for k,v in s.items() if k!='studies'} for s in simulations]}),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory');args=p.parse_args()
 def denied(*a,**k):raise RuntimeError('network disabled in simulation')
 with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):run(args.directory)
