import unittest
import numpy as np
import study_extended_coverage as x

class Tests(unittest.TestCase):
 def setUp(self):
  self.u=np.random.default_rng(19).random((400,120,4));self.p=np.full((120,9),.85)
  self.b=x.simulate(self.u,self.p)
 def test_primary_unchanged(self):
  b=x.prior.primary(self.u[:100],self.p,np.zeros(9))
  np.testing.assert_array_equal(self.b['accepted'],b['accepted'])
  np.testing.assert_array_equal(self.b['primary_items'],b['items'])
 def test_structural_ties_prevent_literal_coverage(self):
  for r in self.b['snapshots']['literal_all_nine'].values():
   self.assertFalse(r['done'].any())
   self.assertTrue((r['items'][self.b['accepted']]==400).all())
 def test_extension_cannot_resurrect_primary(self):
  for scope in self.b['snapshots']:
   r=x.evaluate(self.b,scope,4,2,np.ones(120),np.ones(120))
   self.assertLessEqual(r['accepted'],r['primary_accepts'])
 def test_tolerance_boundary(self):
  b={'accepted':np.ones(2,dtype=bool),'G1_primary':np.zeros(2,dtype=bool),'snapshots':{'a':{4:{'done':np.ones(2,dtype=bool),'safety':np.zeros(2,dtype=bool),'net':np.array([[-1]*9,[-2]*9]),'items':np.array([100,100])}}}}
  r=x.evaluate(b,'a',4,1,np.ones(2),np.ones(2));self.assertEqual(r['accepted'],1)
 def test_pending_cannot_promote_from_risk_followup(self):
  r=x.evaluate(self.b,'literal_all_nine',4,2,np.ones(120),np.ones(120));self.assertEqual(r['risk40']['accepted'],0)
 def test_safety_injection(self):
  rates=np.zeros(9);rates[x.prior.SAFE]=1
  b=x.simulate(self.u,self.p,rates);self.assertFalse(b['accepted'].any());self.assertTrue(b['G1_primary'].all())
 def test_no_risk_oracle(self):
  bad=np.ones(120,dtype=int);r=x.evaluate(self.b,'literal_all_nine',4,0,-np.ones(120),np.ones(120),bad)
  self.assertEqual(r['risk40']['marginal_catch_rate'],0)
 def test_cost_and_nested_coverage(self):
  r=x.evaluate(self.b,'diagnostic_six_answer',4,0,np.ones(120),np.ones(120))
  self.assertAlmostEqual(r['risk40']['expected_extra_items'],40*self.b['accepted'].mean())
  rows=self.b['snapshots']['diagnostic_six_answer'];self.assertTrue((rows[4]['items']<=rows[6]['items']).all());self.assertTrue((rows[6]['items']<=rows[8]['items']).all())
if __name__=='__main__':unittest.main()
