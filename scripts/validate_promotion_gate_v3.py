"""CPU-only count-guard validation on frozen synthetic round-2 fixtures."""
import argparse,importlib.util,json,random,socket,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway.scientific_promotion_gate_v3 import Process,CONFIG
spec=importlib.util.spec_from_file_location('r2',ROOT/'scripts/study_sequential_round2.py');r2=importlib.util.module_from_spec(spec);spec.loader.exec_module(r2)
NINE=['supported-measurement','measurement-decoy','entity-decoy','unit-mismatch','conflict','multi-source-agreement','stale-vs-current','format-variant-agreement','dissenter']
def run_rows(rows,strata):
 p=Process(strata=strata,planned_discordant_p=.85)
 for row in rows:
  if p.verdict!='running':break
  p.update(item_id=row['item_id'],stratum=row['stratum'],candidate=row['candidate'],incumbent=row['incumbent'],abstain=row['always_abstain'])
 return p.report()
def schedule(i,strata):
 if len(strata)==5:return r2.r1.original.registration(i)['schedule']
 return [{'item_id':f'fixture-{i}-{j}','stratum':strata[j%len(strata)]} for j in range(100)]
def run(directory):
 root=Path(directory);root.mkdir(parents=True,exist_ok=False)
 paths=[Path(__file__),ROOT/'scripts/test_promotion_gate_v3.py',ROOT/'scripts/study_sequential_round2.py',ROOT/'scripts/study_sequential_investing.py',ROOT/'scripts/simulate_sequential_gate.py',ROOT/'scripts/run_scientific_runpod_gate.py',*sorted((ROOT/'src').rglob('*.py'))]
 reg={'config':CONFIG,'tolerance_choice':'zero, before testing changed guard; no retuning','simulation':'same known round2 synthetic streams; diagnostic, not independent confirmation','source_sha256':{str(p.relative_to(ROOT)):r2.r1.digest(p) for p in paths},'null_seed':r2.DESIGN['null_seed'],'planned_p_for_all_classes':.85,'class_labels_not_policy_inputs':True,'no_new_inference':True}
 r2.r1.write_new(root/'registration.json',reg);print('registered '+r2.r1.digest(root/'registration.json'),flush=True)
 fixture=r2.full_fixture(r2.DESIGN['seed']);results={};h0={}
 for strata in (r2.DESIGN['strata'],NINE):
  key=str(len(strata));results[key]=[]
  for p_good in (.65,.85,.9,.95):
   metric=r2.r1.metric();reasons={}
   for i,(label,uniforms) in enumerate(fixture):
    p={'good':p_good,'neutral':.5,'harmful':.35}[label];rows=r2.rows_from_uniforms(uniforms,p,schedule(i,strata));report=run_rows(rows,strata)
    r2.r1.tally(metric,label,report['verdict']=='promote_proposal',report['items']);reasons[report['verdict']]=reasons.get(report['verdict'],0)+1
   for label,n in r2.DESIGN['classes'].items():metric[label+'_accept_rate']=metric['accepted'][label]/n
   results[key].append({'good_p':p_good,'metrics':metric,'verdicts':reasons})
  rng=random.Random(r2.DESIGN['null_seed']);crossings=0
  for i in range(10000):
   uniforms=[[rng.random() for _ in range(5)] for _ in range(100)]
   rows=r2.rows_from_uniforms(uniforms,.5,schedule(i,strata));crossings+=run_rows(rows,strata)['verdict']=='promote_proposal'
  h0[key]={'streams':10000,'crossings':crossings,'rate':crossings/10000}
  print('completed '+key+' strata',flush=True)
 result={'registration_sha256':r2.r1.digest(root/'registration.json'),'simulations':results,'h0':h0,'model_calls':0,'new_holdout_access':False,'signed':False,'installed':False}
 result['power_target_met_all_registered_strata']=all(s['metrics']['good_accept_rate']>=.8 for ss in results.values() for s in ss if s['good_p']>=.85)
 if any(r2.r1.digest(ROOT/p)!=h for p,h in reg['source_sha256'].items()):raise ValueError('source_drift')
 r2.r1.write_new(root/'result.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory');a=p.parse_args()
 def denied(*a,**k):raise RuntimeError('network forbidden')
 with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):run(a.directory)
