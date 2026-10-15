import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_scientific_runpod_robustness as r
from nerve_awim.memory_gateway.scientific_task_bank import _item

class RobustnessTests(unittest.TestCase):
    def tasks(self):return [_item(bytes(32),'dev',s,i) for s in r.bank.STRATA for i in range(100)]
    def test_crossed_reference_and_order_repeat(self):
        tasks=self.tasks();entries=r.entries(tasks)
        self.assertEqual(len(entries),2800)
        orders=[[t['task_id'] for rep,_,_,t in entries if rep==i] for i in range(4)]
        self.assertEqual(orders[0],orders[1]);self.assertEqual(orders[1],orders[2]);self.assertNotEqual(orders[0],orders[3]);self.assertEqual(set(orders[0]),set(orders[3]))
    def test_model_seed_explicit_and_prompts_frozen(self):
        task=_item(bytes(32),'dev','multi-source-agreement',0)
        p=r.payload(task,20261016);self.assertEqual(p['seed'],20261016)
        prepared=r.gate.prepared_for(task,'candidate');self.assertEqual(p['messages'][1]['content'],prepared['user']);self.assertEqual(p['response_format']['json_schema']['schema'],prepared['schema'])
    def test_seven_strata_route_coverage(self):
        tasks=self.tasks();self.assertEqual(sum(r.payload(t,20261015) is not None for t in tasks),500)
        self.assertEqual({t['stratum'] for t in tasks},set(r.bank.STRATA))
    def test_variance_and_paired_order_sensitivity(self):
        rows=[]
        for i,correct in enumerate((True,False,True,False)):
            for n in range(100):rows.append({'replicate':i,'stratum':'conflict','task_id':str(n),'model_calls':0,'usage':None,'score':{'strict_correct':correct,'answer_status':'abstain','format_valid':True}})
        reg={'identity':{},'hourly_usd':0.59,'cost_method':'test'}
        s=r.summary(reg,rows,1,0,0,False,None)['strata']['conflict']
        self.assertAlmostEqual(s['seed_sample_variance'],1/3);self.assertEqual(s['order_comparison'],{'paired_n':100,'gains':0,'losses':100,'flips':100})
