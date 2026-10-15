import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
from nerve_awim.memory_gateway import scientific_task_bank_v3 as bank
from nerve_awim.memory_gateway import scientific_bank_v3_truth as truth
from nerve_awim.memory_gateway import scientific_family_b_adapter as adapter
from nerve_awim.memory_gateway import scientific_task_bank as oldbank
from nerve_awim.memory_gateway import scientific_candidate_v3 as old
from nerve_awim.memory_gateway.scientific_candidate_execution import FACT

class FamilyBTests(unittest.TestCase):
    def item(self,stratum='supported-measurement',i=0):return bank.item(bytes(32),'dev',stratum,i)
    def test_reproducible_truth_and_hardness_all_strata(self):
        counts=set()
        for st in bank.STRATA:
            for i in range(20):
                task=self.item(st,i);self.assertEqual(task,self.item(st,i));self.assertTrue(truth.validate(task));counts.add(len(task['evidence']))
                self.assertTrue(all(FACT.fullmatch(r['content']) is None for r in task['evidence']))
                prepared=adapter.prepare(task['query'],task['evidence'],'adapted_v1')
                self.assertEqual([r['source_id'] for r in prepared['records']],[r['source_id'] for r in task['evidence']])
                self.assertEqual(prepared['route']=='deterministic_abstention',task['expected']['status']=='abstain')
        self.assertEqual(counts,set(range(6,13)))
    def test_old_domain_eligibility_equivalence(self):
        for st in oldbank.STRATA:
            for i in range(5):
                task=oldbank._item(bytes(32),'dev',st,i)
                a=adapter.prepare(task['query'],task['evidence'],'adapted_v1');b=old.prepare(task['query'],task['evidence'])
                self.assertEqual(a['route'],b['route'])
    def test_shared_raw_facts_and_stale_preserved(self):
        task=self.item('stale-vs-current');a=adapter.prepare(task['query'],task['evidence'],'adapted_v1');b=adapter.prepare(task['query'],task['evidence'],'adapted_bootstrap')
        self.assertEqual(a['user'],b['user']);self.assertEqual(len(a['records']),len(task['evidence']));self.assertIn(False,[r['current'] for r in a['records']]);self.assertIn(task['expected']['entity'],a['user']);self.assertIn('lexicographically smallest',a['user'])
    def test_decode_does_not_repair_wrong_value_or_source(self):
        task=self.item();p=adapter.prepare(task['query'],task['evidence'],'adapted_v1');record=p['records'][-1]
        raw=json.dumps({'value':999.9,'unit':'mg','source_id':record['source_id']});decoded=adapter.decode(raw,p)
        self.assertEqual(decoded['value'],'999.9');self.assertEqual(decoded['source_id'],record['source_id']);self.assertEqual(decoded['entity'],record['entity'])
    def test_candidate_raw_abstain_is_format_error_on_model_route(self):
        task=self.item();p=adapter.prepare(task['query'],task['evidence'],'adapted_v1')
        with self.assertRaises(ValueError):adapter.decode('ABSTAIN',p)
    def test_full_twelfth_source_supported(self):
        task=next(self.item('multi-source-agreement',i) for i in range(100) if len(self.item('multi-source-agreement',i)['evidence'])==12)
        for arm in ('adapted_v1','adapted_bootstrap'):
            p=adapter.prepare(task['query'],task['evidence'],arm);source=p['records'][11]['source_id']
            raw=json.dumps({'value':12.3,'unit':'mg','source_id':source}) if arm=='adapted_v1' else '12.3|mg|'+source
            self.assertEqual(adapter.decode(raw,p)['source_id'],source)
    def test_independent_validator_rejects_wrong_truth(self):
        task=self.item();task['expected']['value']='777.7';task['content_sha256']=bank.digest({k:v for k,v in task.items() if k!='content_sha256'})
        with self.assertRaises(ValueError):truth.validate(task)
    def test_bank_sealed_and_partition_balanced(self):
        spec=importlib.util.spec_from_file_location('v3builder',Path(__file__).resolve().parents[1]/'scripts/build_scientific_task_bank_v3.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);protocol=root/'protocol.json';protocol.write_text('{}');directory=root/'bank';receipt=module.build(directory,protocol)
            self.assertTrue(receipt['sealed']);manifest=json.loads((directory/'manifest.json').read_text());self.assertEqual(manifest['total'],1200);self.assertEqual(manifest['split_counts'],{'dev':900,'holdout':300})
            for name in ('holdout.json','private-seed.json','slice1.json','slice2.json','slice3.json'):self.assertEqual(stat.S_IMODE((directory/name).stat().st_mode),0)
            self.assertTrue(all(s['count']==100 for s in manifest['slices']))
            # Dev access never opens the sealed files; hash-only manifest remains public.
            self.assertEqual(len(json.loads((directory/'dev.json').read_text())),900)

if __name__=='__main__':unittest.main()
