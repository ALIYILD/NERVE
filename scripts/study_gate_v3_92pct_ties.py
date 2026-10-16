"""Post-study CPU sensitivity analysis; frozen signed gate, no reserve access."""
import sys,json,math,socket
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import confirm_gate_v3 as original
import study_extended_coverage as coverage
from nerve_awim.memory_gateway.retained_promotion_gate import verify
from nerve_awim.memory_gateway import scientific_promotion_gate_v3 as gate
OUT=ROOT/'docs/galahad/evidence/gate-v3-92pct-ties'
def h(p):return sha256(p.read_bytes()).hexdigest()
def write(name,obj):
    with (OUT/name).open('x') as f:json.dump(obj,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def run():
    proof=verify();OUT.mkdir(exist_ok=False)
    paths=[Path(__file__),ROOT/'scripts/confirm_gate_v3.py',ROOT/'scripts/study_extended_coverage.py',ROOT/'scripts/study_two_stage_followup.py',ROOT/'src/nerve_awim/memory_gateway/scientific_promotion_gate_v3.py',ROOT/'docs/galahad/evidence/v5-gate-v3-result.json']
    reg={'kind':'post-hoc sensitivity, not new confirmatory validation','streams':10000,'seeds':{'main':2026101801,'H0':2026101802,'risk':2026101803},
      'signed_payload_sha256':proof['payload_sha256'],'m':10,'t':0,'primary_cap':100,'main_cap':460,'total_cap':500,'risk_N':40,'risk_stratum':'dissenter',
      'fixtures':{'diffuse':{'answer_discordance':.12,'overall_ties':.92},'concentrated':{'multi-source-agreement':.36,'format-variant-agreement':.36,'other_strata_discordance':0,'overall_ties':.92}},
      'fixture_notes':'G1 recorded-zero-misfire safety ties unchanged. Concentrated fixture preserves observed support and normalizes 4/11 in each agreement stratum to .36 for exactly .08 population discordance under balanced nine-stratum sampling. Zero observed discordance is not proof of population zero.',
      'p':[.85,1.0],'H0_p':.5,'coverage_diagnostic':'Uncapped balanced sampling ignoring primary rejection: independent negative-binomial draws with main seed for ten discordances in each answer stratum; hypothetical, not a gate continuation. Positions include round-robin offset and exclude risk40.',
      'parity':'First 100 streams of each fixture/scenario replayed through exact signed scalar Process and compared to vector simulation',
      'sources':{str(p.relative_to(ROOT)):h(p) for p in paths},'numpy':np.__version__,'model_calls':0,'reserve_access':False}
    write('registration.json',reg);coverage.MS=(10,);results={}
    n=10000;idx=np.arange(n);active=[gate.STRATA.index(s) for s in gate.ANSWER]
    for fixture in ('diffuse','concentrated'):
      rates=np.zeros(9);rates[active]=.12
      if fixture=='concentrated':rates[:]=0;rates[[5,7]]=.36
      results[fixture]={}
      for label,p in [('good_085',.85),('never_worse',1.0),('H0',.5)]:
        seed=reg['seeds']['H0' if label=='H0' else 'main']
        u=np.random.default_rng(seed).random((460,n,4))
        for step in range(460):
          r=rates[(idx+step)%9];u[step,:,0]=np.divide(u[step,:,0]*.375,r,out=np.ones(n),where=r>0)
        probs=np.full((n,9),p);base=coverage.simulate(u,probs,original.fixture.fixture_rates())
        row=original.measure(base,10,None,np.zeros(n,dtype=np.int16))
        snap=base['snapshots']['diagnostic_six_answer'][10];primary=base['accepted'];covered=snap['done']&~snap['safety']
        insufficient=(~primary & ~base['G1_primary'])|(primary & ~covered & ~snap['safety'])
        row['insufficient_power']=int(insufficient.sum());row['insufficient_power_rate']=float(insufficient.mean())
        row['coverage_completed_after_primary']=int((primary&covered).sum())
        row['conditional_coverage_items_mean']=float(snap['items'][primary&covered].mean()) if (primary&covered).any() else None
        streams=[]
        for i in range(n):
          streams.append({'stream':i,'primary_accepted':bool(primary[i]),'coverage_complete':bool(covered[i]),'insufficient_power':bool(insufficient[i]),'items':int(snap['items'][i]+40*primary[i])})
        write(f'{fixture}-{label}-streams.json',streams)
        for i in range(100):
          proc=gate.Process(m=10,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=i%9)
          step=0
          while proc.next_stratum() is not None:
            s=proc.next_stratum()
            if proc.phase=='risk':c=b=True
            else:
              d=u[step,i,0]<.375;w=u[step,i,1]<p;both=u[step,i,2]<.88
              c=bool(w if d else both);b=bool(not w if d else both)
              if s in gate.SAFETY:c=b=True
            proc.update(item_id=str(proc.items),stratum=s,candidate=c,incumbent=b,abstain=s in gate.SAFETY)
            step+=1
          assert proc.items==streams[i]['items']
          assert (proc.verdict=='insufficient_power')==streams[i]['insufficient_power']
          assert proc.primary_accepted==streams[i]['primary_accepted']
          assert (proc.verdict=='promote_proposal')==(bool(primary[i] and covered[i] and (snap['net'][i,active]>=0).all()))
        row['scalar_parity_streams']=100;results[fixture][label]=row
        print(fixture,label,json.dumps(row),flush=True)
    trials=np.random.default_rng(2026101801).negative_binomial(10,.12,size=(n,6))+10
    offsets=np.arange(n)%9;positions=(np.array(active)[None,:]-offsets[:,None])%9+1
    items=(9*(trials-1)+positions).max(axis=1)
    diagnostic={'diffuse':{'mean_items':float(items.mean()),'median_items':float(np.median(items)),'p90_items':float(np.quantile(items,.9)),'minimum_items':int(items.min()),'maximum_items':int(items.max()),'covered_by_460':int((items<=460).sum()),'covered_by_500_ignoring_risk40':int((items<=500).sum()),'mean_with_risk40':float(items.mean()+40)},'concentrated':{'finite_coverage_possible':False,'reason':'Four required answer strata have structural zero discordance in this sensitivity fixture; no finite sample covers them.'}}
    for name,v in reg['sources'].items():assert h(ROOT/name)==v
    write('result.json',{'registration_sha256':h(OUT/'registration.json'),'results':results,'uncapped_coverage_diagnostic':diagnostic,'model_calls':0,'reserve_items_consumed':0,'gate_changed':False})
    print(json.dumps(diagnostic),flush=True)
if __name__=='__main__':
    def denied(*a,**kw):raise RuntimeError('network forbidden: CPU sensitivity only')
    with patch.object(socket.socket,'connect',denied),patch.object(socket.socket,'connect_ex',denied),patch.object(socket,'create_connection',denied):run()
