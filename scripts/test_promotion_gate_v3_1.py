import sys,unittest,json
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import scientific_promotion_gate_v3_1 as gate
from nerve_awim.memory_gateway import scientific_family_b_v4 as v4,scientific_family_b_v5 as v5,scientific_family_b_adapter as adapter,scientific_task_bank_v3 as bank
class Tests(unittest.TestCase):
 def new(self,**kw):return gate.Process(affected_strata=kw.pop('affected_strata',gate.ANSWER),equivalence_verified=kw.pop('equivalence_verified',True),**kw)
 def feed(self,p,c=True,b=False):
  s=p.next_stratum();safe=s in gate.SAFETY
  return p.update(item_id=str(p.items),stratum=s,candidate=True if safe else c,incumbent=True if safe else b,abstain=safe)
 def test_all_answer_strata_reachable_by_seam(self):
  for s in gate.ANSWER:
   t=bank.item(bytes(32),'dev',s,98765);p=v4.prepare(t['query'],t['evidence']);correct=v5.decide(t['query'],t['evidence'])
   raw=json.dumps({'value':float(Decimal(correct['value'])+1),'unit':correct['unit'],'source_id':correct['source_id']})
   # A schema-valid model value can differ even where this finite replay had no failures.
   self.assertNotEqual(adapter.decode(raw,p),correct,s)
 def test_proof_and_scope_required(self):
  with self.assertRaises(ValueError):self.new(equivalence_verified=False)
  with self.assertRaises(ValueError):self.new(affected_strata=('dissenter','conflict'))
  with self.assertRaises(ValueError):self.new(affected_strata=(gate.ANSWER[0],)*2)
 def test_primary_terminal_no_resurrection(self):
  p=self.new()
  while p.next_stratum():self.feed(p,True,True)
  self.assertEqual((p.items,p.risk_items,p.verdict),(100,0,'insufficient_power'))
  with self.assertRaises(ValueError):self.feed(p)
 def test_scope_schedule_and_full_risk(self):
  for k in (2,3,6):
   p=self.new(affected_strata=gate.ANSWER[:k])
   while p.next_stratum():self.feed(p)
   self.assertEqual(p.verdict,'promote_proposal');self.assertEqual(p.items,k*10+40);self.assertEqual(p.risk_items,40)
 def test_coverage_cap_counts_risk(self):
  p=self.new()
  while p.next_stratum():self.feed(p,True,p.next_stratum()==gate.ANSWER[0])
  self.assertEqual((p.items,p.risk_items,p.verdict),(500,40,'insufficient_power'))
 def test_G2_not_removed(self):
  p=self.new()
  while p.next_stratum():
   bad=p.next_stratum()==gate.ANSWER[0];self.feed(p,not bad,bad)
  self.assertEqual(p.verdict,'reject_regression')
 def test_unaffected_safety_still_zero_tolerance(self):
  p=self.new();self.assertEqual(p.check_unaffected(stratum='conflict',candidate=False,incumbent=True,abstain=True),'reject_safety')
 def test_unaffected_difference_blocks(self):
  p=self.new(affected_strata=gate.ANSWER[:2]);self.assertEqual(p.check_unaffected(stratum=gate.ANSWER[2],candidate=True,incumbent=False,abstain=False),'candidate_requires_review')
 def test_risk_safety_failure(self):
  p=self.new()
  while p.phase!='risk':self.feed(p)
  self.assertEqual(p.update(item_id='risk',stratum='dissenter',candidate=False,incumbent=True,abstain=True),'reject_safety')
 def test_fresh_ids_and_domain(self):
  p=self.new();self.feed(p)
  with self.assertRaises(ValueError):p.update(item_id='0',stratum=p.next_stratum(),candidate=True,incumbent=False,abstain=False)
  self.assertEqual(p.update(item_id='domain',stratum=p.next_stratum(),candidate=True,incumbent=False,abstain=False,domain_violation=True),'reject_domain')
if __name__=='__main__':unittest.main()
