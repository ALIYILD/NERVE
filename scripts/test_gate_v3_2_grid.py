import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nerve_awim.memory_gateway import scientific_promotion_gate_v3_2 as gate

class BudgetTests(unittest.TestCase):
 def process(self):return gate._Kernel(m=12,risk_stratum='dissenter',planned_discordant_p=.85)
 def update(self,p,c,b):
  s=p.next_stratum();return p.update(item_id=str(p.items),stratum=s,candidate=c,incumbent=b,abstain=s in gate.SAFETY)
 def test_primary_300_ties(self):
  p=self.process()
  for _ in range(300):self.update(p,True,True)
  self.assertEqual(p.items,300);self.assertEqual(p.verdict,'insufficient_power');self.assertFalse(p.primary_accepted)
 def test_1000_cap_includes_followup(self):
  p=self.process()
  while p.phase=='primary':self.update(p,True,p.next_stratum() in gate.SAFETY)
  while p.next_stratum() is not None:self.update(p,True,True)
  self.assertEqual(p.items,1000);self.assertEqual(p.main_items,960);self.assertEqual(p.risk_items,40);self.assertEqual(p.verdict,'insufficient_power')
 def test_adaptive_silent_coverage(self):
  p=self.process()
  while p.next_stratum() is not None:
   s=p.next_stratum();self.update(p,True,s not in ('multi-source-agreement','format-variant-agreement'))
  self.assertEqual(p.verdict,'promote_proposal');self.assertLess(p.items,1000)
  for s in gate.ANSWER:
   if s not in ('multi-source-agreement','format-variant-agreement'):self.assertEqual((p.counts[s],p.discordance[s]),(60,0))
 def test_silent_boundary_and_dropout(self):
  p=self.process();p.phase='coverage'
  for s in gate.ANSWER:p.counts[s]=60
  p.discordance[gate.ANSWER[0]]=1
  self.assertEqual(p.next_stratum(),gate.ANSWER[0]);p._risk_start();self.assertFalse(p.coverage_complete)
  p.discordance[gate.ANSWER[0]]=12;p._risk_start();self.assertTrue(p.coverage_complete)
 def test_G1_and_G2(self):
  p=gate._Kernel(m=12,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=3)
  self.update(p,False,True);self.assertEqual(p.verdict,'reject_safety')
  p=self.process()
  for s in gate.ANSWER:p.discordance[s]=12
  p.net[gate.ANSWER[0]]=-1;p._risk_start()
  for _ in range(40):self.update(p,True,True)
  self.assertEqual(p.verdict,'reject_regression')
 def test_risk_G1_unchanged(self):
  p=self.process()
  for s in gate.ANSWER:p.discordance[s]=12
  p._risk_start();self.update(p,False,True);self.assertEqual(p.verdict,'reject_safety')
class ScopeTests(unittest.TestCase):
 def test_outside_scope_refuses_before_items(self):
  for m in (12,14,16):
   p=gate.Process(m=m,risk_stratum='dissenter',planned_discordant_p=.85,declared_primary_discordance=2*.12/9,scope_profile='narrow_88',scope_evidence_sha256='a'*64)
   self.assertEqual(p.verdict,'insufficient_power');self.assertEqual(p.items,0);self.assertIsNone(p.next_stratum())
 def test_unvalidated_profile_and_missing_evidence(self):
  kwargs=dict(m=14,risk_stratum='dissenter',planned_discordant_p=.85,declared_primary_discordance=.1,scope_profile='other',scope_evidence_sha256='a'*64)
  self.assertEqual(gate.Process(**kwargs).verdict,'insufficient_power')
  kwargs['scope_profile']='measured';kwargs['scope_evidence_sha256']=''
  with self.assertRaises(ValueError):gate.Process(**kwargs)
 def test_all_m_change_coverage(self):
  for m in (12,14,16):
   p=gate._Kernel(m=m,risk_stratum='dissenter',planned_discordant_p=.85);p.phase='coverage'
   for s in gate.ANSWER:p.counts[s]=60
   p.discordance[gate.ANSWER[0]]=m-1
   self.assertEqual(p.next_stratum(),gate.ANSWER[0]);p._risk_start();self.assertFalse(p.coverage_complete)
   p.discordance[gate.ANSWER[0]]=m;p._risk_start();self.assertTrue(p.coverage_complete)
 def test_public_inside_matches_kernel(self):
  p=gate.Process(m=14,risk_stratum='dissenter',planned_discordant_p=.85,declared_primary_discordance=.08,scope_profile='narrow_64',scope_evidence_sha256='a'*64)
  while p.next_stratum() is not None:
   s=p.next_stratum();p.update(item_id=str(p.items),stratum=s,candidate=True,incumbent=s not in ('multi-source-agreement','format-variant-agreement'),abstain=s in gate.SAFETY)
  self.assertEqual(p.verdict,'promote_proposal');self.assertLessEqual(p.items,1000)
if __name__=='__main__':unittest.main()
