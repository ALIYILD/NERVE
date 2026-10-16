"""Frozen post-dev analysis; refuses to run without completed dev and offline replay."""
import sys,json,socket
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import confirm_gate_v3 as confirmation
import study_extended_coverage as coverage
from nerve_awim.memory_gateway import scientific_promotion_gate_v3 as gate
from nerve_awim.memory_gateway.retained_promotion_gate import verify
E=ROOT/'docs/galahad/evidence';BASE=Path('/Users/aliyildirim/nerve-research-runs/bank-v5-dev-discrimination-20261016')
OUT=E/'bank-v5-measured-gate-power'
def h(p):return sha256(p.read_bytes()).hexdigest()
def register():
 paths=[Path(__file__),ROOT/'scripts/confirm_gate_v3.py',ROOT/'scripts/study_extended_coverage.py',ROOT/'scripts/study_two_stage_followup.py',ROOT/'src/nerve_awim/memory_gateway/scientific_promotion_gate_v3.py',E/'bank-v5-dev-study-registration.json',E/'gate-v3_1-dev-seam-replay.json']
 reg={'source_sha256':{str(p.relative_to(ROOT)):h(p) for p in paths},'seeds':{'main':2026101801,'H0':2026101802},'streams':10000,'m':10,'t':0,'primary_cap':100,'main_cap':460,'total_cap':500,'risk_N':40,'risk_stratum':'dissenter','fixtures':['per-stratum empirical rates: new measured agreement dev and historical unchanged-stratum dev','optimistic sensitivity: Wilson95 upper discordance endpoints in all answer strata, p=1; not a joint confidence bound or measured performance'],'targets':{'good085_accept_min':.8,'H0_max':.05},'conditional_win_rate':'Use observed wins/discordances only where nonzero; else report undefined and no outcome depends on it at discordance0. Also simulate p=.85 and p=1 for comparison.','no_redistribution':'Do not spread agreement discordance uniformly into the four answer strata not changed by bank v5.','unchanged_strata_assumption':'Historical dev replay used as plug-in; zero observed discordance is not population zero.','run_admission':'Complete new dev result plus byte-identical offline replay required; no model calls','model_calls':0}
 with (E/'bank-v5-power-preregistration.json').open('x') as f:json.dump(reg,f,sort_keys=True,indent=2);f.write('\n')
 print(json.dumps({'registered':True,'sha256':h(E/'bank-v5-power-preregistration.json'),'awaiting_measured_dev':True}))
def run():
 reg=json.loads((E/'bank-v5-power-preregistration.json').read_text())
 for p,d in reg['source_sha256'].items():assert h(ROOT/p)==d
 verify();result=json.loads((BASE/'result.json').read_text());replay=json.loads((BASE/'replay.json').read_text());assert replay['matched'] and replay['rows']==100 and replay['result_sha256']==h(BASE/'result.json')
 assert result['status']=='dev_discrimination_only';rates=np.zeros(9);prob=np.ones(9);upper=np.zeros(9)
 # Wilson zero/100 upper endpoint for the unchanged answer-stratum replay.
 import run_scientific_runpod_gate as transport
 for s in gate.ANSWER:upper[gate.STRATA.index(s)]=transport.wilson(0,100)[1]
 for s in ('multi-source-agreement','format-variant-agreement'):
  row=result['per_stratum'][s];j=gate.STRATA.index(s);rates[j]=row['discordance_rate'];prob[j]=row['conditional_win_rate'] if row['conditional_win_rate'] is not None else 1.;upper[j]=row['discordance_interval'][1]
 OUT.mkdir(exist_ok=False);coverage.MS=(10,);summaries={};n=10000;idx=np.arange(n)
 for label,r,p in [('empirical_plugin',rates,prob),('good085_plugin_rates',rates,np.full(9,.85)),('never_worse_plugin_rates',rates,np.ones(9)),('optimistic_upper_discordance',upper,np.ones(9)),('H0_plugin_rates',rates,np.full(9,.5))]:
  u=np.random.default_rng(reg['seeds']['H0' if label.startswith('H0') else 'main']).random((460,n,4))
  for step in range(460):
   rr=r[(idx+step)%9];u[step,:,0]=np.divide(u[step,:,0]*.375,rr,out=np.ones(n),where=rr>0)
  base=coverage.simulate(u,np.broadcast_to(p,(n,9)),confirmation.fixture.fixture_rates());row=confirmation.measure(base,10,None,np.zeros(n,dtype=np.int16));row['discordance_by_stratum']=dict(zip(gate.STRATA,map(float,r)));summaries[label]=row
 out={'preregistration_sha256':h(E/'bank-v5-power-preregistration.json'),'measured_dev_result_sha256':h(BASE/'result.json'),'results':summaries,'model_calls':0,'signed_gate_changed':False,'structural_plugin_coverage_impossible':any(rates[gate.STRATA.index(s)]==0 for s in gate.ANSWER),'warning':'Structural impossibility is a property of the plug-in fixture, not proof of population zero discordance. No future study is authorized by this simulation.'}
 with (OUT/'result.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2);f.write('\n')
 print(json.dumps(out,indent=2))
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('CPU only')
 with patch.object(socket.socket,'connect',deny),patch.object(socket,'create_connection',deny):(register if sys.argv[1]=='register' else run)()
