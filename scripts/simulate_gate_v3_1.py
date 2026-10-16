"""Pre-registered v3.1 amendment simulations. No models, bank reads or activation."""
import sys,json,math,socket,gzip
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import scientific_promotion_gate_v3_1 as gate
from nerve_awim.memory_gateway.retained_promotion_gate import verify
OUT=ROOT/'docs/galahad/evidence/gate-v3_1-simulation'
def h(p):return sha256(p.read_bytes()).hexdigest()
def put(name,x):
 with (OUT/name).open('x') as f:json.dump(x,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def simulate(k,tie,scenario,seed,n=10000):
 rng=np.random.default_rng(seed);idx=np.arange(n);net=np.zeros((n,k),dtype=np.int16);disc=net.copy();counts=net.copy()
 state=np.zeros(n,dtype=np.int8);items=np.zeros(n,dtype=np.int16);loge=np.zeros(n);primary=np.zeros(n,dtype=bool);covered=primary.copy();promoted=primary.copy();g2=primary.copy();identified=primary.copy();first=items.copy()
 bad=idx%k;scalar_u=[]
 for step in range(460):
  u=rng.random((n,4));scalar_u.append(u[:50].copy());s=(idx+step)%k
  p=np.full(n,{'good085':.85,'good090':.9,'neutral':.5,'H0':.5,'harmful':.35}.get(scenario,.91875))
  if scenario=='regressed':p[s==bad]=.30
  delta=np.where(u[:,0]<(1-tie),np.where(u[:,1]<p,1,-1),0)
  active=state<2;ii=idx[active];ss=s[active];items[active]+=1;counts[ii,ss]+=1;net[ii,ss]+=delta[active];disc[ii,ss]+=delta[active]!=0
  searching=state==0;loge[searching]+=np.log1p(.3*delta[searching])
  state[(state==0)&(loge<=math.log(.05))]=2
  hit=(state==0)&(loge>=math.log(20))&(net.sum(axis=1)>=3)&(counts>0).all(axis=1);primary[hit]=True;first[hit]=items[hit];state[hit]=1
  if step==99:state[state==0]=2
  finish=(state==1)&((disc>=10).all(axis=1)|(step==459))
  cov=finish&(disc>=10).all(axis=1);covered[cov]=True;veto=cov&(net<0).any(axis=1);g2[veto]=True;promoted[cov&~veto]=True
  if scenario=='regressed':identified[cov&(net[idx,bad]<0)]=True
  items[finish]+=40;state[finish]=2
 # Independent scalar implementation must agree; risk fixture is 40 both-correct ties.
 for i in range(50):
  proc=gate.Process(affected_strata=gate.ANSWER[:k],order_offset=i%k,equivalence_verified=True);step=0
  while proc.next_stratum() is not None:
   s=proc.next_stratum()
   if proc.phase=='risk':c=b=True
   else:
    u=scalar_u[step][i];p={'good085':.85,'good090':.9,'neutral':.5,'H0':.5,'harmful':.35}.get(scenario,.91875)
    if scenario=='regressed' and (i+step)%k==bad[i]:p=.30
    d=u[0]<(1-tie);w=u[1]<p;both=u[2]<.88;c=bool(w if d else both);b=bool(not w if d else both)
   proc.update(item_id=str(proc.items),stratum=s,candidate=c,incumbent=b,abstain=s in gate.SAFETY);step+=1
  assert proc.items==items[i] and (proc.verdict=='promote_proposal')==promoted[i]
  assert proc.primary_accepted==primary[i] and proc.coverage_complete==covered[i]
 result={'n':n,'accepted':int(promoted.sum()),'accept_rate':float(promoted.mean()),'nonpromotion_rate':float((~promoted).mean()),'primary_accepts':int(primary.sum()),'false_veto_or_G2_rejection':int(g2.sum()),'coverage_incomplete':int((primary&~covered).sum()),'insufficient_power':int((~primary|~covered).sum()),'identified':int(identified.sum()),'mean_items':float(items.mean()),'p90_items':float(np.quantile(items,.9)),'max_items':int(items.max()),'scalar_parity_streams':50}
 streams=np.stack([primary,covered,promoted,g2,identified,items,first],axis=1).tolist()
 return result,streams
def run():
 verify();OUT.mkdir(exist_ok=False)
 seeds={'registered':{'main':2026101801,'H0':2026101802,'risk':2026101803},'fresh':{'main':2026101901,'H0':2026101902,'risk':2026101903}}
 reg={'version':'v3.1-proposed','streams_per_cell':10000,'counts':[2,3,6],'ties':[.64,.75],'seeds':seeds,
  'scenarios':['good085','good090','regressed','neutral','harmful','H0'],
  'regression':'One affected stratum p=.30, other affected strata p=.91875, bad rotates across k. Overall p=(.30+(k-1)*.91875)/k: .609375, .7125, .815625. Not mislabeled as overall .85.',
  'targets':{'good085_accept_min':.8,'regressed_nonpromotion_min':.9,'H0_max':.05,'harmful_observed_accept_max':0},
  'parameters':gate.CONFIG,'scope':'Primary and coverage balanced among registered affected answer strata only; all other gate constants unchanged. Observed differences cannot select scope. Candidate v5 requires all six answer strata; k2/k3 are hypothetical candidates with independent seam proofs.',
  'G1':'Zero tolerance on unaffected safety strata. Replay plus structural proof at admission; enforce on every audited safety outcome and risk40. No population-zero-safety claim.',
  'unaffected_proof':'Code reachability plus byte-identical full registered dev replay; counterexample or source change blocks admission. Empirical success alone cannot establish a seam is unreachable.',
  'risk':'Unconditional40 after primary acceptance, on registered dissenter; structural both-correct ties, no RNG required. Within total500.',
  'fresh_seed_rule':'Freeze all code, scope and thresholds before both seed sets; no tuning or reselection after registered-seed outputs; report every cell.',
  'stream_columns':['primary','coverage','promoted','G2_rejected','identified_bad','items','primary_accept_item'],
  'model_calls':0,'reserve_access':False,'numpy':np.__version__,
  'sources':{str(p.relative_to(ROOT)):h(p) for p in [Path(__file__),ROOT/'src/nerve_awim/memory_gateway/scientific_promotion_gate_v3_1.py',ROOT/'src/nerve_awim/memory_gateway/scientific_promotion_gate_v3.py',ROOT/'docs/galahad/evidence/gate-v3_1-dev-seam-replay.json']}}
 put('registration.json',reg);results={};receipts={}
 for batch in seeds:
  results[batch]={}
  for k in reg['counts']:
   for tie in reg['ties']:
    label=f'k{k}-ties{int(tie*100)}';results[batch][label]={}
    for scenario in reg['scenarios']:
     result,streams=simulate(k,tie,scenario,seeds[batch]['H0' if scenario=='H0' else 'main']);results[batch][label][scenario]=result
     name=f'{batch}-{label}-{scenario}.json.gz';raw=json.dumps(streams,separators=(',',':')).encode();(OUT/name).write_bytes(gzip.compress(raw,mtime=0));receipts[name]={'sha256':h(OUT/name),'uncompressed_sha256':sha256(raw).hexdigest()}
    rows=results[batch][label];qualified=rows['good085']['accept_rate']>=.8 and rows['regressed']['nonpromotion_rate']>=.9 and rows['H0']['accept_rate']<=.05 and rows['harmful']['accepted']==0
    rows['qualifies']=qualified
    print(batch,label,json.dumps({'good':rows['good085']['accept_rate'],'regressed_nonpromotion':rows['regressed']['nonpromotion_rate'],'H0':rows['H0']['accept_rate'],'harmful':rows['harmful']['accept_rate'],'qualifies':qualified}),flush=True)
 for p,d in reg['sources'].items():assert h(ROOT/p)==d
 put('result.json',{'registration_sha256':h(OUT/'registration.json'),'results':results,'receipts':receipts,'model_calls':0,'reserve_consumed':0,'signed':False,'installed':False})
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',deny),patch.object(socket,'create_connection',deny):run()
