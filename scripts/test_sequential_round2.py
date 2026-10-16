"""CPU-only mathematical and allocation fixture tests; no research draws."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('r2',Path(__file__).with_name('study_sequential_round2.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class Round2Tests(unittest.TestCase):
 def test_impossible_before_twelve_discordances(self):
  for n in (5,10):
   x=r.exact_discordant(.95,n);self.assertEqual(x['terminal'],0);self.assertEqual(x['anytime'],0)
 def test_twelve_requires_all_wins(self):
  x=r.exact_discordant(.7,12);self.assertAlmostEqual(x['terminal'],.7**12);self.assertAlmostEqual(x['anytime'],.7**12)
 def test_ties_dilute_item_power(self):
  x=r.exact_item_power(.7,items=12);self.assertAlmostEqual(x['anytime_power'],(.25*.7)**12)
  self.assertAlmostEqual(x['anytime_power']+x['futility_probability']+x['budget_probability'],1)
 def test_terminal_does_not_exceed_anytime(self):
  x=r.exact_discordant(.6,25);self.assertLessEqual(x['terminal'],x['anytime'])
 def test_fresh_does_not_spend_or_earn(self):
  p=r.FreshReusePolicy();a=p.admit(['a']);self.assertEqual(a['alpha'],.05)
  p.settle('promote_proposal');self.assertEqual(p.investing.wealth,.05)
  p.admit(['b']);p.settle('retain_incumbent');self.assertEqual(p.investing.wealth,.05)
 def test_reuse_fails_closed_without_validity(self):
  p=r.FreshReusePolicy();p.admit(['a']);p.settle('retain_incumbent')
  with self.assertRaises(ValueError):p.admit(['a'])
  self.assertEqual(p.investing.wealth,.05)
 def test_certified_fixture_reuse_enters_investing(self):
  p=r.FreshReusePolicy();p.admit(['a']);p.settle('retain_incumbent')
  a=p.admit(['a'],conditional_null_verified=True);self.assertEqual(a['mode'],'reuse');self.assertAlmostEqual(a['alpha'],.005/1.005)
  p.settle('promote_proposal');self.assertAlmostEqual(p.investing.wealth,.1)
 def test_duplicates_and_concurrent_admission(self):
  p=r.FreshReusePolicy()
  with self.assertRaises(ValueError):p.admit(['a','a'])
  p.admit(['a'])
  with self.assertRaises(ValueError):p.admit(['b'])
 def test_fixture_pair_semantics(self):
  schedule=[{'stratum':'s','item_id':str(i)} for i in range(4)]
  rows=r.rows_from_uniforms([[.1,.1,.1,1,1],[.1,.1,.99,1,1],[.9,.1,.1,1,1],[.9,.99,.1,1,1]],.85,schedule)
  self.assertEqual([(x['candidate'],x['incumbent']) for x in rows],[(True,True),(False,False),(True,False),(False,True)])
if __name__=='__main__':unittest.main()
