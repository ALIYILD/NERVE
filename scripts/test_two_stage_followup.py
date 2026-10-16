import importlib.util
from pathlib import Path
import unittest
import numpy as np
spec=importlib.util.spec_from_file_location('s',Path(__file__).with_name('study_two_stage_followup.py'));s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class TwoStageTests(unittest.TestCase):
 def test_pending_before_followup(self):self.assertEqual(s.followup_verdict(True,[True]),{'verdict':'candidate_requires_review','reason':'stratum_follow_up'})
 def test_only_complete_followup_clears(self):
  self.assertEqual(s.followup_verdict(True,[True],[0],[2])['verdict'],'promote_proposal')
  self.assertEqual(s.followup_verdict(True,[True],[0],[0])['verdict'],'candidate_requires_review')
 def test_loss_rejects_and_all_triggers_must_clear(self):self.assertEqual(s.followup_verdict(True,[True,True],[1,-1],[3,3])['verdict'],'reject_regression')
 def test_no_primary_resurrection(self):self.assertEqual(s.followup_verdict(False,[True],[10],[10])['verdict'],'insufficient_power')
 def test_reserve_shortfall_remains_review(self):self.assertEqual(s.followup_verdict(True,[True],[10],[10],reserve_ok=False)['reason'],'reserve_shortfall')
 def test_rule_misfire_detected(self):
  u=np.zeros((100,9,4));p=np.full((9,9),.85)
  out=s.primary(u,p,np.ones(9));self.assertTrue(out['G1_rejected'].all())
 def test_empirical_rule_profile_no_safety_false_veto(self):
  u=np.random.default_rng(1).random((100,30,4));p=np.full((30,9),.85)
  self.assertFalse(s.primary(u,p,np.zeros(9))['G1_rejected'].any())
 def test_fixture_source_bindings(self):self.assertTrue((s.fixture_rates()==0).all())
 def test_finish_counts_cost_and_catch(self):
  b={'trigger':np.array([[True,False],[False,False],[True,True]]),'accepted':np.array([True,True,True]),'G1_rejected':np.array([False]*3),'counts':np.array([[2,2]]*3),'items':np.array([20]*3)}
  net=np.array([[-1,0],[0,0],[1,1]]);d=np.array([[3,0],[0,0],[3,3]])
  out=s.finish(b,net,d,20,np.array([22,22]),bad=np.array([0,0,1]))
  self.assertEqual(out['accepted'],2);self.assertEqual(out['extra_items_full_funding'],60);self.assertEqual(out['bad_stratum_caught'],1)
 def test_followups_have_zero_discordance_on_safe_strata(self):
  u=np.zeros((40,3,9,2));net,d=s.followup_arrays(u,np.full((3,9),.85));self.assertTrue((d[:,:,s.SAFE]==0).all())
if __name__=='__main__':unittest.main()
