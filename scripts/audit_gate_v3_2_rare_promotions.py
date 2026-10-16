"""Independent scalar replay of every harmful promotion; zero inference."""
import json,gzip,socket
from unittest.mock import patch
import numpy as np
import simulate_gate_v3_2_grid as sim

def run():
 reg=sim.read(sim.OUT/'registration.json');result=sim.read(sim.OUT/'result.json');audits=[]
 for p,h in reg['sources'].items():assert sim.h(sim.ROOT/p)==h,p
 for q,admitted in ((.0799,False),(.08,True)):
  p=sim.gate.Process(m=14,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=0,declared_primary_discordance=q,scope_profile='narrow_64',scope_evidence_sha256=sim.h(sim.OUT/'registration.json'))
  assert (p.next_stratum() is not None)==admitted
  if not admitted:assert p.verdict=='insufficient_power' and p.items==0
 for label,row in result['results'].items():
  if not label.endswith('-harmful') or not row['accepted']:continue
  seed,mt,profile,scenario=label.split('-',3);m=int(mt[1:])
  path=sim.ROOT/row['receipt']['path'];assert sim.h(path)==row['receipt']['sha256']
  rows=json.loads(gzip.decompress(path.read_bytes()));chosen=[x for x in rows if x['promoted']]
  assert len(chosen)==row['accepted'];rates,probs,bad=sim.fixture(profile,scenario)
  processes={x['stream']:sim.gate.Process(m=m,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=x['stream']%9,declared_primary_discordance=reg['scope']['fixture_primary_discordance'][profile],scope_profile=profile,scope_evidence_sha256=sim.h(sim.OUT/'registration.json')) for x in chosen}
  rng=np.random.default_rng(reg['seeds'][seed]['main']);max_main=max(sum(x['counts']) for x in chosen)
  for step in range(max_main):
   u=rng.random((10000,4))
   for i,p in processes.items():
    if p.phase in ('risk','done'):continue
    s=p.next_stratum();j=sim.gate.STRATA.index(s)
    if s in sim.gate.SAFETY:c=b=True
    else:
     d=u[i,0]<rates[i,j];win=u[i,1]<probs[i,j];both=u[i,2]<.88;c=bool(win if d else both);b=bool(not win if d else both)
    p.update(item_id=str(p.items),stratum=s,candidate=c,incumbent=b,abstain=s in sim.gate.SAFETY)
  for x in chosen:
   p=processes[x['stream']]
   while p.next_stratum() is not None:
    assert p.phase=='risk';p.update(item_id=str(p.items),stratum=p.next_stratum(),candidate=True,incumbent=True,abstain=True)
   assert p.verdict=='promote_proposal' and p.items==x['items']
   assert [p.net[s] for s in sim.gate.STRATA]==x['net'] and [p.counts[s] for s in sim.gate.STRATA]==x['counts'] and [p.discordance[s] for s in sim.gate.STRATA]==x['discordance']
   audits.append({'cell':label,'simulated_stream':x['stream'],'matched':True,'verdict':p.verdict,'items':p.items,'net':p.net})
 report={'source_sha256':sim.h(sim.Path(__file__)),'registered_source_hashes_match':True,'harmful_promotions_expected':sum(x['accepted'] for k,x in result['results'].items() if k.endswith('-harmful')),'harmful_promotions_replayed':len(audits),'all_matched':True,'scope_admitted_public_Process_used':True,'scope_floor_boundary_checks_passed':2,'cases':audits,'model_calls':0}
 assert report['harmful_promotions_expected']==report['harmful_promotions_replayed']
 sim.write(sim.OUT/'harmful-promotion-scalar-audit.json',report);print(json.dumps({k:v for k,v in report.items() if k!='cases'}))
if __name__=='__main__':
 def deny(*a,**kw):raise RuntimeError('CPU replay only')
 with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):run()
