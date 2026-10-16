import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nerve_awim.memory_gateway.scientific_promotion_gate_v3 import Process,promotion_authority
class GateV3Tests(unittest.TestCase):
 def test_below_mde_is_insufficient_without_consumption(self):
  for effect in (.5,.65,.8,.8499):
   p=Process(strata=['a'],planned_discordant_p=effect);self.assertEqual(p.verdict,'insufficient_power');self.assertEqual(p.items,0);self.assertIn('power_100_items/0',p.report()['power_citation'])
 def test_no_true_effect_or_observed_p_oracle(self):
  p=Process(strata=['a'],planned_discordant_p=.85)
  for i in range(12):p.update(item_id=str(i),stratum='a',candidate=True,incumbent=False,abstain=False)
  self.assertEqual(p.verdict,'promote_proposal')
 def test_regression_blocks_crossing(self):
  p=Process(strata=['a','b'],planned_discordant_p=.85)
  p.update(item_id='loss',stratum='b',candidate=False,incumbent=True,abstain=False)
  for i in range(15):p.update(item_id=str(i),stratum='a',candidate=True,incumbent=False,abstain=False)
  self.assertGreater(p.log_e,3);self.assertEqual(p.verdict,'running');self.assertFalse(p.guard())
  p.update(item_id='recover',stratum='b',candidate=True,incumbent=False,abstain=False)
  self.assertEqual(p.verdict,'promote_proposal')
 def test_zero_tolerance_at_budget(self):
  p=Process(strata=['a','b'],planned_discordant_p=.85)
  p.update(item_id='0',stratum='b',candidate=False,incumbent=True,abstain=False)
  for i in range(1,100):p.update(item_id=str(i),stratum='a',candidate=True,incumbent=True,abstain=False)
  self.assertEqual(p.verdict,'reject_regression')
 def test_no_evidence_is_insufficient_not_retain(self):
  p=Process(strata=['a'],planned_discordant_p=.85)
  for i in range(100):p.update(item_id=str(i),stratum='a',candidate=True,incumbent=True,abstain=False)
  self.assertEqual(p.verdict,'insufficient_power')
 def test_futility_is_insufficient(self):
  p=Process(strata=['a'],planned_discordant_p=.85)
  for i in range(20):
   if p.verdict!='running':break
   p.update(item_id=str(i),stratum='a',candidate=False,incumbent=True,abstain=False)
  self.assertEqual(p.verdict,'insufficient_power')
 def test_domain_rejection_is_separate(self):
  p=Process(strata=['a'],planned_discordant_p=.85);p.update(item_id='0',stratum='a',candidate=True,incumbent=False,abstain=False,domain_violation=True)
  self.assertEqual(p.verdict,'reject_domain')
 def test_uncovered_and_duplicate(self):
  p=Process(strata=['a','b'],planned_discordant_p=.85);p.update(item_id='0',stratum='a',candidate=True,incumbent=True,abstain=False)
  with self.assertRaises(ValueError):p.update(item_id='0',stratum='a',candidate=True,incumbent=True,abstain=False)
  for i in range(1,100):p.update(item_id=str(i),stratum='a',candidate=True,incumbent=True,abstain=False)
  self.assertEqual(p.verdict,'incomplete_infrastructure')
 def test_abstain_guard(self):
  p=Process(strata=['a'],planned_discordant_p=.85);p.update(item_id='0',stratum='a',candidate=False,incumbent=False,abstain=True);self.assertFalse(p.guard())
 def test_v2_authority_retired_only_on_verified_v3_activation(self):
  self.assertFalse(promotion_authority('v3'));self.assertFalse(promotion_authority('v2',signature_verified=True,active_version='v3'));self.assertTrue(promotion_authority('v3',signature_verified=True,active_version='v3'))
if __name__=='__main__':unittest.main()
