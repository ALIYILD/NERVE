import unittest
import gate_v3_2_budget_research as gate

class BudgetTests(unittest.TestCase):
 def process(self):return gate.Process(m=10,risk_stratum='dissenter',planned_discordant_p=.85)
 def update(self,p,c,b):
  s=p.next_stratum();return p.update(item_id=str(p.items),stratum=s,candidate=c,incumbent=b,abstain=s in gate.SAFETY)
 def test_primary_300_ties(self):
  p=self.process()
  for _ in range(300):self.update(p,True,True)
  self.assertEqual(p.items,300);self.assertEqual(p.verdict,'insufficient_power');self.assertFalse(p.primary_accepted)
 def test_800_cap_includes_followup(self):
  p=self.process()
  while p.phase=='primary':self.update(p,True,p.next_stratum() in gate.SAFETY)
  while p.next_stratum() is not None:self.update(p,True,True)
  self.assertEqual(p.items,800);self.assertEqual(p.main_items,760);self.assertEqual(p.risk_items,40);self.assertEqual(p.verdict,'insufficient_power')
 def test_adaptive_silent_coverage(self):
  p=self.process()
  while p.next_stratum() is not None:
   s=p.next_stratum();self.update(p,True,s not in ('multi-source-agreement','format-variant-agreement'))
  self.assertEqual(p.verdict,'promote_proposal');self.assertLess(p.items,800)
  for s in gate.ANSWER:
   if s not in ('multi-source-agreement','format-variant-agreement'):self.assertEqual((p.counts[s],p.discordance[s]),(60,0))
 def test_silent_boundary_and_dropout(self):
  p=self.process();p.phase='coverage'
  for s in gate.ANSWER:p.counts[s]=60
  p.discordance[gate.ANSWER[0]]=1
  self.assertEqual(p.next_stratum(),gate.ANSWER[0]);p._risk_start();self.assertFalse(p.coverage_complete)
  p.discordance[gate.ANSWER[0]]=10;p._risk_start();self.assertTrue(p.coverage_complete)
 def test_G1_and_G2(self):
  p=gate.Process(m=10,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=3)
  self.update(p,False,True);self.assertEqual(p.verdict,'reject_safety')
  p=self.process()
  for s in gate.ANSWER:p.discordance[s]=10
  p.net[gate.ANSWER[0]]=-1;p._risk_start()
  for _ in range(40):self.update(p,True,True)
  self.assertEqual(p.verdict,'reject_regression')
 def test_risk_G1_unchanged(self):
  p=self.process()
  for s in gate.ANSWER:p.discordance[s]=10
  p._risk_start();self.update(p,False,True);self.assertEqual(p.verdict,'reject_safety')
if __name__=='__main__':unittest.main()
