"""CPU fixture checks before study draws; no empirical tuning."""
import importlib.util
import math
from pathlib import Path
import random
import unittest
p=Path(__file__).with_name('study_sequential_investing.py')
spec=importlib.util.spec_from_file_location('research',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class InvestingStudyTests(unittest.TestCase):
 def test_fixed_process_matches_original(self):
  for seed in range(20):
   rng=random.Random(seed);g=m.gate_config();rows=[]
   for i in range(100):rows.append(dict(stratum=g['strata'][i%5],candidate=rng.random()<.6,incumbent=rng.random()<.5,always_abstain=rng.random()<.2))
   p=m.Process(g)
   for row in rows:
    if p.verdict!='running':break
    p.update(candidate=row['candidate'],incumbent=row['incumbent'],abstain=row['always_abstain'],stratum=row['stratum'])
   actual=m.run_rows(rows,g);expected=p.report()
   for key in actual:self.assertEqual(actual[key],expected[key])
 def test_wallet_debit_reward_once(self):
  w=m.Investing();a=w.start();self.assertAlmostEqual(a['spend'],.005);self.assertAlmostEqual(a['alpha'],.005/1.005)
  with self.assertRaises(ValueError):w.start()
  row=w.settle('promote_proposal');self.assertAlmostEqual(row['wealth_after'],.1)
  with self.assertRaises(ValueError):w.settle('promote_proposal')
 def test_no_reward_for_failure(self):
  w=m.Investing();a=w.start();row=w.settle('insufficient_power');self.assertEqual(row['reward'],0);self.assertAlmostEqual(w.wealth,.045)
 def test_cap_and_nonnegative_wealth(self):
  w=m.Investing()
  for _ in range(200):
   a=w.start();self.assertLessEqual(a['alpha'],.05);w.settle('promote_proposal')
  w=m.Investing()
  for _ in range(200):w.start();w.settle('retain_incumbent');self.assertGreater(w.wealth,0)
 def test_wallet_off_leaves_veto_alpha_fixed(self):
  g=m.gate_config(**m.DESIGN['variants']['wallet_off']);self.assertEqual(g['alpha'],.05);self.assertEqual(g['veto_alpha'],.00025)
 def test_ablation_flags_isolate_components(self):
  for name,change in m.DESIGN['variants'].items():self.assertLessEqual(len(change),1)
 def test_veto_and_plateau_switches(self):
  g=m.gate_config(alpha=.05,bet=.9,strata=['s'],minimum_net_wins=100)
  rows=[dict(stratum='s',candidate=True,incumbent=False,always_abstain=False) for _ in range(20)]
  self.assertNotEqual(m.run_rows(rows,g)['verdict'],'promote_proposal')
  self.assertEqual(m.run_rows(rows,dict(g,minimum_net_wins=0))['verdict'],'promote_proposal')
  rows=[dict(stratum='s',candidate=False,incumbent=False,always_abstain=True) for _ in range(100)]
  g=m.gate_config(strata=['s'])
  self.assertEqual(m.run_rows(rows,g)['reason'],'domain_or_stratum_veto')
  self.assertEqual(m.run_rows(rows,dict(g,veto_enabled=False))['reason'],'item_budget')
 def test_promotion_requires_strata_coverage(self):
  rows=[dict(stratum=m.gate_config()['strata'][0],candidate=True,incumbent=False,always_abstain=False) for _ in range(100)]
  self.assertNotEqual(m.run_rows(rows,m.gate_config())['verdict'],'promote_proposal')
if __name__=='__main__':unittest.main()
