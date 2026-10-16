import unittest
import gate_v3_2_research as gate

class ProposalTests(unittest.TestCase):
 def process(self):return gate.Process(m=10,risk_stratum='dissenter',planned_discordant_p=.85)
 def test_silent_boundary(self):
  p=self.process()
  for s in gate.ANSWER:p.counts[s]=60
  p._risk_start();self.assertTrue(p.coverage_complete)
  p.counts[gate.ANSWER[0]]=59;p._risk_start();self.assertFalse(p.coverage_complete)
  p.counts[gate.ANSWER[0]]=60;p.discordance[gate.ANSWER[0]]=1;p._risk_start();self.assertFalse(p.coverage_complete)
  p.discordance[gate.ANSWER[0]]=10;p._risk_start();self.assertTrue(p.coverage_complete)
 def test_cap_obstruction(self):
  for offset in range(9):
   counts=[sum((offset+i)%9==j for i in range(460)) for j in range(9)]
   self.assertLessEqual(max(counts),52)
 def test_G1_zero_tolerance(self):
  p=gate.Process(m=10,risk_stratum='dissenter',planned_discordant_p=.85,order_offset=3)
  p.update(item_id='1',stratum='unit-mismatch',candidate=False,incumbent=True,abstain=True)
  self.assertEqual(p.verdict,'reject_safety')
 def test_G2_and_risk_unchanged(self):
  p=self.process()
  for s in gate.ANSWER:p.discordance[s]=10
  p.net[gate.ANSWER[0]]=-1;p._risk_start()
  for i in range(40):p.update(item_id=str(i),stratum='dissenter',candidate=True,incumbent=True,abstain=True)
  self.assertEqual(p.verdict,'reject_regression')
if __name__=='__main__':unittest.main()
