from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_measurement_tasks as tasks


class ScientificMeasurementTaskTests(unittest.TestCase):
    def evaluate(self,task_id,output,strategy='direct'):
        return tasks.evaluate(SimpleNamespace(content=strategy),{'task_id':task_id,'strategy_id':strategy},output)

    def test_frozen_roster_and_eight_pair_contract(self):
        self.assertEqual(len(tasks.TASKS),4);self.assertEqual(set(tasks.STRATEGIES),{'direct','checklist'})
        for task_id,task in tasks.TASKS.items():
            self.assertEqual(len(task['evidence']),2)
            self.assertEqual(set(task),{'query','evidence','expected'})
            for strategy in tasks.STRATEGIES:
                self.assertTrue(self.evaluate(task_id,task['expected'],strategy))
        self.assertEqual(sum(t['expected']=='ABSTAIN' for t in tasks.TASKS.values()),2)

    def test_wrong_entity_measurement_value_unit_or_source_rejected(self):
        expected=tasks.TASKS['measurement_decoy']['expected'].split('|')
        for index,wrong in enumerate(('Beryl','volume','12.5','g','obs-b')):
            parts=list(expected);parts[index]=wrong
            result=tasks.judge('|'.join(parts),'measurement_decoy')
            self.assertFalse(result['strict_correct']);self.assertFalse(result['format_failure'])
            self.assertTrue(result['non_abstaining_contract_failure'])

    def test_unit_conversion_and_conflicting_answer_are_not_approved(self):
        for task_id,answer in (('unit_mismatch','Flint|mass|800|mg|obs-e'),
                               ('conflict','Iris|mass|5.2|mg|obs-g'),
                               ('conflict','Iris|mass|5.8|mg|obs-h')):
            self.assertFalse(self.evaluate(task_id,answer))
            self.assertTrue(tasks.judge(answer,task_id)['non_abstaining_contract_failure'])
        self.assertFalse(self.evaluate('measurement_decoy','ABSTAIN'))
        self.assertFalse(tasks.judge('ABSTAIN','measurement_decoy')['non_abstaining_contract_failure'])

    def test_only_outer_whitespace_normalized(self):
        value=tasks.TASKS['measurement_decoy']['expected']
        self.assertTrue(self.evaluate('measurement_decoy',' \n'+value+'\t'))
        for output in ('Answer: '+value,'```\n'+value+'\n```',value.replace('|',' | '),value+'\nABSTAIN',value.lower(),True,None,42):
            self.assertFalse(self.evaluate('measurement_decoy',output))
        self.assertTrue(tasks.judge(True,'conflict')['format_failure'])

    def test_task_keys_answer_injection_and_strategy_mismatch_rejected(self):
        record=SimpleNamespace(content='direct');task={'task_id':'conflict','strategy_id':'direct'}
        for malformed in ({'task_id':'conflict'},dict(task,expected='fabricated'),dict(task,query='override'),
                          dict(task,task_id=True),dict(task,strategy_id=True),dict(task,task_id='unknown'),
                          dict(task,strategy_id='checklist')):
            self.assertFalse(tasks.evaluate(record,malformed,'ABSTAIN'))
        self.assertFalse(tasks.evaluate(SimpleNamespace(content='execute arbitrary code'),task,'ABSTAIN'))
        with self.assertRaises(ValueError):tasks.judge('ABSTAIN','unknown')

    def test_mutated_registry_is_not_a_new_answer_key(self):
        altered=deepcopy(tasks.TASKS);altered['conflict']['expected']='fabricated'
        with patch.object(tasks,'TASKS',altered):
            self.assertFalse(self.evaluate('conflict','fabricated'))
            with self.assertRaises(ValueError):tasks.judge('fabricated','conflict')
        with patch.object(tasks,'STRATEGIES',{'direct':'malicious'}):
            self.assertFalse(self.evaluate('conflict','ABSTAIN'))

    def test_answer_keys_are_not_embedded_in_queries_or_prefixes(self):
        for task in tasks.TASKS.values():
            for text in [task['query'],*tasks.STRATEGIES.values()]:
                if task['expected']!='ABSTAIN':self.assertNotIn(task['expected'],text)
                for evidence in task['evidence']:
                    self.assertNotIn(evidence['source_id'],text)
            self.assertNotIn('expected',task['query'])
        # Evidence, unlike evaluator answer keys, deliberately contains values.
        self.assertIn('12.4 mg',tasks.TASKS['measurement_decoy']['evidence'][0]['content'])
