"""Fixed measured-rate target checks; no inference or study continuation."""
import socket
from unittest.mock import patch
import numpy as np
import simulate_gate_v3_2 as s

def run():
 reg=s.read(s.OUT/'registration.json')
 for path,h in reg['source_sha256'].items():assert s.digest(s.ROOT/path)==h
 report=s.read(s.ROOT/'docs/galahad/evidence/bank-v5-dev-study-result.json')
 replay=s.read(s.ROOT/'docs/galahad/evidence/bank-v5-dev-study-replay.json');assert replay['matched']
 scenarios={'good_090':.9,'regression':None,'neutral':.5,'harmful':.35,'H0':.5,'silent_regression_05':None,'silent_regression_10':None}
 registration={'parent_registration_sha256':s.digest(s.OUT/'registration.json'),'source_sha256':s.digest(s.Path(__file__)),'dev_result_sha256':s.digest(s.ROOT/'docs/galahad/evidence/bank-v5-dev-study-result.json'),'seeds':reg['seeds'],'scenarios':scenarios,'reason':'Complete target metrics at measured per-stratum rates in addition to already registered empirical/.85/never-worse/optimistic sensitivity. Measured rates are known; these target simulations are registered before their execution. No gate tuning.','fixtures':'Parent narrow fixture with agreement discordances replaced by measured .22/.64; four other answer strata zero except stated silent regression. Regression p=.30 alternates agreement strata; other agreement p=.91875. Silent losses follow parent specification.','model_calls':0}
 s.write(s.OUT/'measured-targets-registration.json',registration)
 result={};n=10000;idx=np.arange(n)
 for seedname in ('registered','fresh'):
  for scenario,p in scenarios.items():
   rates=np.zeros((n,9));probs=np.full((n,9),p if p is not None else .85);bad=None
   for j in (5,7):rates[:,j]=report['per_stratum'][s.gate.STRATA[j]]['discordance_rate']
   if scenario=='regression':probs[:]=.91875;bad=np.array([5,7])[idx%2];probs[idx,bad]=.30
   if scenario.startswith('silent'):
    bad=np.array([0,1,2,6])[idx%4];rates[idx,bad]=.05 if scenario.endswith('05') else .10;probs[idx,bad]=0
   label=f'measured-targets-{seedname}-{scenario}'
   result[label]=s.simulate(label,rates,probs,reg['seeds'][seedname]['H0' if scenario=='H0' else 'main'],bad)
 s.write(s.OUT/'measured-targets-result.json',{'registration_sha256':s.digest(s.OUT/'measured-targets-registration.json'),'results':result,'model_calls':0})
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('CPU analysis only')
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):run()
