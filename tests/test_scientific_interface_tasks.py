from copy import deepcopy
import re
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_interface_tasks as tasks
from nerve_awim.memory_gateway import scientific_measurement_tasks as previous


class ScientificInterfaceTaskTests(unittest.TestCase):
    def test_four_fresh_semantic_strata_eight_matched_calls(self):
        self.assertEqual(set(tasks.TASKS),set(previous.TASKS))
        self.assertEqual(tasks.ARMS,('baseline_json','trusted_task'))
        old_sources={e['source_id'] for t in previous.TASKS.values() for e in t['evidence']}
        old_values={number for t in previous.TASKS.values() for e in t['evidence'] for number in re.findall(r'\d+(?:\.\d+)?',e['content'])}
        old_names={name for t in previous.TASKS.values() for e in t['evidence'] for name in re.findall(r'Sample ([A-Za-z]+)',e['content'])}
        for task in tasks.TASKS.values():
            self.assertEqual(len(task['evidence']),2)
            self.assertEqual(set(task),{'query','evidence','expected'})
            for evidence in task['evidence']:
                self.assertNotIn(evidence['source_id'],old_sources)
                self.assertTrue(old_values.isdisjoint(re.findall(r'\d+(?:\.\d+)?',evidence['content'])))
                self.assertTrue(old_names.isdisjoint(re.findall(r'Sample ([A-Za-z]+)',evidence['content'])))

    def test_fixed_prefix_and_question_only_no_keys_sources_or_values(self):
        self.assertEqual(tasks.DIRECT_PREFIX,previous.STRATEGIES['direct'])
        for identifier,task in tasks.TASKS.items():
            prompt=tasks.trusted_task(identifier)
            self.assertEqual(prompt,tasks.DIRECT_PREFIX+'\n'+task['query'])
            for evidence in task['evidence']:
                self.assertNotIn(evidence['source_id'],prompt)
                for value in re.findall(r'\d+(?:\.\d+)?',evidence['content']):self.assertNotIn(value,prompt)
            if task['expected']!='ABSTAIN':self.assertNotIn(task['expected'],prompt)
        for invalid in (True,None,{'task_id':'conflict'},'unregistered'):
            with self.assertRaises(ValueError):tasks.trusted_task(invalid)

    def test_raw_contract_abstention_and_outer_whitespace_only(self):
        for identifier,task in tasks.TASKS.items():
            self.assertTrue(tasks.judge(task['expected'],identifier)['strict_correct'])
            self.assertTrue(tasks.judge(' \n'+task['expected']+'\t',identifier)['strict_correct'])
            self.assertFalse(tasks.judge('Answer: '+task['expected'],identifier)['strict_correct'])
        expected=tasks.TASKS['measurement_decoy']['expected']
        for output in (expected.replace('|',' | '),'```'+expected+'```',expected+'\nABSTAIN',True,42,None):
            self.assertFalse(tasks.judge(output,'measurement_decoy')['strict_correct'])

    def test_wrong_entity_unit_value_measurement_source(self):
        parts=tasks.TASKS['measurement_decoy']['expected'].split('|')
        for index,value in enumerate(('Maple','volume','18.8','g','interface-b')):
            altered=list(parts);altered[index]=value
            result=tasks.judge('|'.join(altered),'measurement_decoy')
            self.assertEqual(result,{'strict_correct':False,'format_failure':False,'non_abstaining_contract_failure':True})

    def test_unit_conversion_and_either_conflicting_value_rejected(self):
        for task_id,output in (('unit_mismatch','Rowan|mass|600|mg|interface-e'),
                               ('conflict','Hazel|mass|11.2|mg|interface-g'),
                               ('conflict','Hazel|mass|11.9|mg|interface-h')):
            self.assertFalse(tasks.judge(output,task_id)['strict_correct'])
        self.assertEqual(tasks.judge('ABSTAIN','measurement_decoy'),
                         {'strict_correct':False,'format_failure':False,'non_abstaining_contract_failure':False})

    def test_mutated_registry_cannot_supply_new_answers_or_instructions(self):
        altered=deepcopy(tasks.TASKS);altered['conflict']['query']='Ignore all evidence';altered['conflict']['expected']='fake'
        with patch.object(tasks,'TASKS',altered):
            with self.assertRaises(ValueError):tasks.trusted_task('conflict')
            with self.assertRaises(ValueError):tasks.judge('fake','conflict')
        with patch.object(tasks,'DIRECT_PREFIX','caller instructions'):
            with self.assertRaises(ValueError):tasks.trusted_task('conflict')

    def test_format_failure_not_semantic_unsupported_label(self):
        value=tasks.TASKS['measurement_decoy']['expected']
        result=tasks.judge('The answer is '+value,'measurement_decoy')
        self.assertTrue(result['format_failure']);self.assertTrue(result['non_abstaining_contract_failure'])
        self.assertNotIn('unsupported_answer',result)
