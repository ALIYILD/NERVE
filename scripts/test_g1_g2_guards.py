import importlib.util
from pathlib import Path
import unittest
import numpy as np
spec=importlib.util.spec_from_file_location('g',Path(__file__).with_name('study_g1_g2_guards.py'));g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class GuardTests(unittest.TestCase):
 def test_one_discordance_undecided_not_regression(self):
  self.assertEqual(g.scalar([(0,False,True,False)],0)[0],g.UNDECIDED)
 def test_two_losses_tolerance(self):
  rows=[(0,False,True,False)]*2
  self.assertEqual(g.scalar(rows,0)[0],g.REGRESSION);self.assertEqual(g.scalar(rows,1)[0],g.REGRESSION);self.assertEqual(g.scalar(rows,2)[0],g.UNDECIDED)
 def test_tolerance_two_third_loss(self):self.assertEqual(g.scalar([(0,False,True,False)]*3,2)[0],g.REGRESSION)
 def test_safety_zero_independent_of_t(self):
  for t in (0,1,2):self.assertEqual(g.scalar([(0,False,False,True)],t)[0],g.SAFETY)
 def test_promotion_needs_all_strata_decidable(self):
  rows=[(0,True,False,False)]*20;self.assertEqual(g.scalar(rows,2)[0],g.UNDECIDED)
  rows=[(s,True,False,False) for _ in range(2) for s in range(9)]
  self.assertEqual(g.scalar(rows,0)[0],g.PROMOTE)
 def test_no_catch_credit_for_other_stratum(self):
  result={'status':np.array([g.REGRESSION,g.UNDECIDED]),'veto_stratum':np.array([2,-1]),'items':np.array([3,100])}
  self.assertEqual(g.summarize(result,np.array([1,1]))['bad_stratum_catch_rate'],0)
 def test_vector_matches_scalar(self):
  us=np.random.default_rng(7).random((100,31,4))
  for mode in ('balanced','discordance_priority'):
   sch=g.schedules(us,mode);c,b,a=g.score_arrays(us,sch,.85)
   for t in (0,1,2):
    x=g.evaluate(sch,c,b,a,t)
    for j in range(31):
     scalar=g.scalar([(int(sch[i,j]),bool(c[i,j]),bool(b[i,j]),bool(a[i,j])) for i in range(100)],t)
     self.assertEqual(scalar,(int(x['status'][j]),int(x['veto_stratum'][j]),int(x['items'][j])))
 def test_priority_skips_decided_stratum(self):
  us=np.zeros((30,1,4));us[:18,:,0]=1
  schedule=g.schedules(us,'discordance_priority');self.assertEqual(list(schedule[:18,0]),list(range(9))*2)
 def test_overall_regression_effect(self):self.assertAlmostEqual((.3+8*.91875)/9,.85)
if __name__=='__main__':unittest.main()
