import math,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nerve_awim.memory_gateway import scientific_promotion_gate_v3 as gate
import confirm_gate_v3 as study

class Tests(unittest.TestCase):
 def process(self,**kwargs):return gate.Process(m=kwargs.pop('m',8),risk_stratum=kwargs.pop('risk_stratum','dissenter'),planned_discordant_p=kwargs.pop('planned_discordant_p',.85),**kwargs)
 def feed(self,p,c=True,b=False):
  s=p.next_stratum();safe=s in gate.SAFETY
  return p.update(item_id=str(p.items),stratum=s,candidate=True if safe else c,incumbent=True if safe else b,abstain=safe)
 def test_scalar_vector_parity_all_scenarios(self):
  for scenario in study.DESIGN['scenarios']:
   u,probs,bad,base,risk=study.raw(45,scenario,8841,8842)
   for m in study.MS:
    accepts=0;total=0;identified=0;veto=0
    for j in range(45):
     p=self.process(m=m,order_offset=j%9)
     while p.phase!='done':
      s=p.next_stratum();k=gate.STRATA.index(s)
      if p.phase=='risk' or s in gate.SAFETY:c=b=True
      else:
       z=u[p.main_items,j];d=z[0]<.375;w=z[1]<probs[j,k];both=z[2]<.88;c=bool(w if d else both);b=bool(not w if d else both)
      p.update(item_id=str(p.items),stratum=s,candidate=c,incumbent=b,abstain=s in gate.SAFETY)
     accepts+=p.verdict=='promote_proposal';veto+=p.verdict in ('reject_regression','reject_safety');total+=p.items
     if bad is not None:identified+=gate.STRATA[bad[j]] in p.regressed_strata
    x=study.measure(base,m,bad,risk)
    self.assertEqual(accepts,x['accepted'],(scenario,m));self.assertEqual(total,x['total_items'],(scenario,m));self.assertAlmostEqual(veto/45,x['false_veto_rate'])
    if bad is not None:self.assertEqual(identified,x['identified'])
 def test_safety_failure(self):
  p=self.process(order_offset=3);self.assertEqual(p.update(item_id='s',stratum='unit-mismatch',candidate=False,incumbent=True,abstain=True),'reject_safety')
 def test_all_tie_risk_completes(self):
  p=self.process()
  while p.phase not in ('risk','done'):self.feed(p)
  self.assertEqual(p.phase,'risk');self.assertEqual(p.verdict,'candidate_requires_review')
  frozen=p.log_e
  for _ in range(40):self.feed(p)
  self.assertEqual(p.verdict,'promote_proposal');self.assertEqual(p.risk_items,40);self.assertEqual(p.log_e,frozen)
 def test_500_includes_followup_and_no_resurrection(self):
  p=self.process()
  while p.phase!='done':
   s=p.next_stratum();self.feed(p,c=True,b=s=='entity-decoy')
  self.assertEqual(p.items,500);self.assertEqual(p.verdict,'insufficient_power');self.assertEqual(p.risk_items,40)
 def test_primary_cap(self):
  p=self.process()
  while p.phase!='done':self.feed(p,c=True,b=True)
  self.assertEqual(p.items,100);self.assertEqual(p.risk_items,0);self.assertFalse(p.primary_accepted)
 def test_risk_failure(self):
  p=self.process()
  while p.phase!='risk':self.feed(p)
  self.assertEqual(p.update(item_id='risk-error',stratum='dissenter',candidate=False,incumbent=True,abstain=True),'reject_safety')
 def test_fresh_schedule_and_scores(self):
  p=self.process();self.feed(p)
  with self.assertRaises(ValueError):p.update(item_id='0',stratum=p.next_stratum(),candidate=True,incumbent=False,abstain=False)
  with self.assertRaises(ValueError):p.update(item_id='x',stratum='dissenter',candidate=True,incumbent=True,abstain=True)
  with self.assertRaises(ValueError):self.process(fresh_items=False)
 def test_effect_and_authority(self):
  self.assertEqual(self.process(planned_discordant_p=.65).verdict,'insufficient_power')
  self.assertFalse(gate.promotion_authority('v3'));self.assertFalse(self.process().report()['installed'])
 def test_g2_single_terminal_guard(self):
  p=self.process()
  while p.phase not in ('risk','done'):
   s=p.next_stratum();self.feed(p,c=s!='entity-decoy',b=s=='entity-decoy')
  self.assertEqual(p.phase,'risk');self.assertIn('entity-decoy',p.regressed_strata)
  for _ in range(40):self.feed(p)
  self.assertEqual(p.verdict,'reject_regression')
if __name__=='__main__':unittest.main()
