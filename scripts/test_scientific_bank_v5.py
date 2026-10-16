import unittest,sys
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nerve_awim.memory_gateway import scientific_task_bank_v5 as new,scientific_task_bank_v3 as old,scientific_family_b_adapter as adapter
from nerve_awim.memory_gateway.scientific_bank_v3_truth import validate,facts
class Tests(unittest.TestCase):
 def test_empty_and_disabled_proposal_paths(self):
  self.assertEqual(new.propose([])['status'],'no_proposals')
  e=[dict(episode_id='test',stratum='multi-source-agreement',failure_class='wrong_provenance')]
  self.assertEqual(new.propose(e)['mode'],'deterministic_failure_rules')
  self.assertEqual(new.propose(e,research_enabled=False)['mode'],'enumeration_fallback')
 def test_other_seven_strata_exactly_preserved(self):
  for s in new.STRATA:
   if s in new.AGREEMENT:continue
   for i in range(8):self.assertEqual(new.item(bytes(32),'dev',s,i),old.item(bytes(32),'dev',s,i))
 def test_truth_bounds_and_agreement(self):
  for s in new.AGREEMENT:
   for i in range(100):
    t=new.item(bytes(32),'dev',s,i);self.assertTrue(validate(t));p=adapter.prepare(t['query'],t['evidence'],'adapted_v1');self.assertEqual(p['route'],'model')
    match=[r for r in facts(t) if r[0]==t['expected']['entity']];self.assertIn(len(match),(6,8,9));self.assertEqual(len({Decimal(r[2]) for r in match}),1)
    self.assertLessEqual(len(t['evidence']),12);self.assertLessEqual(len(p['user'].encode()),32768)
    self.assertEqual(t['evidence'][-1]['source_id'],t['expected']['source_id'])
    if s=='format-variant-agreement':self.assertGreater(len({r[2] for r in match}),1)
 def test_split_separation(self):
  for s in new.STRATA:self.assertNotEqual(new.item(bytes(32),'dev',s,0)['task_id'],new.item(bytes(32),'reserve',s,0)['task_id'])
if __name__=='__main__':unittest.main()
