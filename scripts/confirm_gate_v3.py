#!/usr/bin/env python3
"""Prospective fresh-seed confirmation, CPU scores only; no inference."""
import argparse,json,socket,sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
import study_extended_coverage as previous
import study_two_stage_followup as fixture
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import scientific_promotion_gate_v3 as gate
MS=(8,10,12)
DESIGN={'version':'gate-v3-confirmation-v1','gate_id':gate.GATE_ID,'gate_version':'v3','streams_per_scenario':10000,
 'seeds':{'scores':2026101801,'H0':2026101802,'risk_followup':2026101803},
 'primary':{'alpha':.05,'bet':.3,'cap':100,'minimum_net_wins':3,'futility_e':.05,'coverage':'observe all nine once','acceptance':'latched; extension cannot create acceptance'},
 'coverage':{'m':[8,10,12],'strata':list(gate.ANSWER),'schedule':'balanced all-nine rotating round-robin, initial offset stream_index modulo9','count_primary_items':True,'main_cap':460,'total_cap_including_followup':500},
 'G1':{'tolerance':0,'strata':list(sorted(gate.SAFETY)),'fixture':'Doc118 recorded v3/v4 zero-misfire rates; structural both-correct ties. Zero observed is not population zero risk.'},
 'G2':{'tolerance_net_losses':0,'strata':list(gate.ANSWER),'when':'once at complete coverage, not early veto','cap_without_coverage':'insufficient_power'},
 'risk_followup':{'N':40,'stratum':'dissenter','source':'doc113 / family-b-v5-registration.json predictions.risk_primary','allocation':'Every primary acceptance, irrespective of observed losses/G2 outcome; 40 fresh items within total500. Immediate G1/domain failures terminate.','decision':'Nonnegative fresh net passes; negative net rejects. Safety-risk structural ties are judged by G1 alone, no discordance minimum; no pooling risk40 into G2/e-process.'},
 'paired_fixture':'Safety strata both-correct ties; answer strata discordance .375, both-correct conditional on tie .88; overall75% ties.',
 'scenarios':{'good_085':.85,'good_090':.90,'neutral':.5,'harmful':.35,'H0':.5,'regression_requested':{'bad_answer_p':.30,'other_answer_p':.91875,'bad_stratum':'rotates across six answer strata','overall_discordant_p':.815625}},
 'regression_metric':{'gated':'nonpromotion by ANY route, including primary nonacceptance, G1, G2, risk followup and cap insufficient_power','clarification':'Post-hoc clarification of doc119 catch, explicitly requested before this fresh-seed confirmation. Earlier identification results not relabelled.','reported_not_gated':'identification of the deliberately regressed stratum'},
 'selection':'smallest m with good_085 acceptance>=.80, regressed nonpromotion>=.90, H0 false promotion<=.05 and observed harmful acceptance==0; .90 good acceptance also reported',
 'items':'all proposed streams, include primary nonacceptances and risk40; mean and empirical p90; time/cost at historical2.3..3.4 seconds/item and $0.59/hour',
 'scope':'Fresh simulated scores; no model calls; signature payload conditional on qualification, no activation. Risk-stratum fixture matches v5 and does not establish power for arbitrary risk strata.',
 'model_calls':0}

def raw(n,scenario,seed,followseed):
 u=np.random.default_rng(seed).random((460,n,4));p,bad=previous.probs_for(n,scenario)
 previous.MS=MS # explicit registered replacement of candidate coverage grid; imported source stays unchanged
 b=previous.simulate(u,p,fixture.fixture_rates())
 # Registered safety risk: empirical both-correct ties. Still consume40 fresh outcomes.
 risk=np.zeros(n,dtype=np.int16)
 return u,p,bad,b,risk

def measure(base,m,bad,risk):
 row=base['snapshots']['diagnostic_six_answer'][m];a=base['accepted'];covered=row['done'] & ~row['safety'];safety=row['safety']|base['G1_primary']
 veto=covered & (row['net'][:,fixture.ACTIVE]<0).any(axis=1)
 risk_fail=a & (risk<0);accepted=a & covered & ~veto & ~safety & ~risk_fail
 items=row['items'].astype(np.int32)+40*a
 result={'streams':len(a),'accepted':int(accepted.sum()),'accept_rate':float(accepted.mean()),'nonpromotion_rate':float((~accepted).mean()),'primary_accepts':int(a.sum()),
 'false_veto_rate':float((veto|safety|risk_fail).mean()),'G1_rejections':int(safety.sum()),'coverage_incomplete':int((a & ~covered).sum()),
 'mean_items':float(items.mean()),'p90_items':float(np.quantile(items,.9)),'maximum_items':int(items.max()),'total_items':int(items.sum()),
 'risk_followup_studies':int(a.sum()),'risk_extra_items_mean':float(40*a.mean()),'risk_marginal_identification_rate':0.0}
 for label,value in [('mean',result['mean_items']),('p90',result['p90_items'])]:
  result[label+'_A40_minutes_range']=[value*sec/60 for sec in (2.3,3.4)]
  result[label+'_A40_compute_usd_range']=[value*sec/3600*.59 for sec in (2.3,3.4)]
 if bad is not None:
  caught=covered & (row['net'][np.arange(len(a)),bad]<0)
  result['identified']=int(caught.sum());result['identification_rate']=float(caught.mean())
 return result

def sources():return [Path(__file__),ROOT/'scripts/test_promotion_gate_v3.py',ROOT/'src/nerve_awim/memory_gateway/scientific_promotion_gate_v3.py',ROOT/'scripts/study_extended_coverage.py',ROOT/'scripts/study_two_stage_followup.py',fixture.FIXTURE,ROOT/'docs/galahad/evidence/family-b-v5-registration.json']

def run(directory):
 directory.mkdir(mode=0o700,parents=True,exist_ok=False)
 reg={'design':DESIGN,'source_sha256':{str(p.relative_to(ROOT)):fixture.digest(p) for p in sources()},'numpy_version':np.__version__}
 fixture.write_new(directory/'registration.json',reg);print('registered '+fixture.digest(directory/'registration.json'),flush=True)
 results={}
 for scenario in DESIGN['scenarios']:
  seed=DESIGN['seeds']['H0' if scenario=='H0' else 'scores'];u,p,bad,base,risk=raw(10000,scenario,seed,DESIGN['seeds']['risk_followup'])
  results[scenario]={str(m):measure(base,m,bad,risk) for m in MS};print(scenario+' complete',flush=True)
 eligible=[m for m in MS if results['good_085'][str(m)]['accept_rate']>=.8 and results['regression_requested'][str(m)]['nonpromotion_rate']>=.9 and results['H0'][str(m)]['accept_rate']<=.05 and results['harmful'][str(m)]['accepted']==0]
 assert all(fixture.digest(ROOT/p)==v for p,v in reg['source_sha256'].items())
 result={'registration_sha256':fixture.digest(directory/'registration.json'),'results':results,'eligible_m':eligible,'chosen_m':min(eligible) if eligible else None,'model_calls':0,'signed':False,'installed':False}
 fixture.write_new(directory/'result.json',result);print(json.dumps({'chosen_m':result['chosen_m'],'eligible_m':eligible}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
 def denied(*a,**kw):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):run(a.directory)
