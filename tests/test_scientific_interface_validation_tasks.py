from collections import Counter
from copy import deepcopy
import re
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_interface_validation_tasks as tasks
from nerve_awim.memory_gateway import scientific_interface_tasks as prior
from nerve_awim.memory_gateway import scientific_measurement_tasks as initial


class ScientificInterfaceValidationTasksTests(unittest.TestCase):
    def test_balanced_eight_tasks_and_fixed_strata(self):
        self.assertEqual(len(tasks.TASKS),8)
        self.assertEqual(Counter(tasks.STRATA.values()),{'measurement_decoy':2,'entity_decoy':2,'unit_mismatch':2,'conflict':2})
        self.assertEqual(sum(t['expected']=='ABSTAIN' for t in tasks.TASKS.values()),4)
        self.assertEqual(tasks.ARMS,('baseline_json','trusted_task'))
        supported=[t for t in tasks.TASKS.values() if t['expected']!='ABSTAIN']
        self.assertEqual(Counter(t['expected'].split('|')[1] for t in supported),{'mass':2,'volume':2})
        positions=[]
        for task in supported:
            positions.append([e['source_id'] for e in task['evidence']].index(task['expected'].split('|')[-1]))
        self.assertEqual(Counter(positions),{0:2,1:2})

    def test_names_values_and_sources_all_fresh(self):
        previous=[e for registry in (prior.TASKS,initial.TASKS) for t in registry.values() for e in t['evidence']]
        old_sources={e['source_id'] for e in previous}
        old_values={v for e in previous for v in re.findall(r'\d+(?:\.\d+)?',e['content'])}
        old_names={n for e in previous for n in re.findall(r'Sample ([A-Za-z]+)',e['content'])}
        new_sources=[]
        for task in tasks.TASKS.values():
            self.assertEqual(len(task['evidence']),2)
            for evidence in task['evidence']:
                new_sources.append(evidence['source_id'])
                self.assertNotIn(evidence['source_id'],old_sources)
                self.assertTrue(old_values.isdisjoint(re.findall(r'\d+(?:\.\d+)?',evidence['content'])))
                self.assertTrue(old_names.isdisjoint(re.findall(r'Sample ([A-Za-z]+)',evidence['content'])))
        self.assertEqual(len(set(new_sources)),16)

    def test_prompt_and_grammar_unchanged_and_no_answer_keys(self):
        self.assertEqual(tasks.DIRECT_PREFIX,prior.DIRECT_PREFIX)
        self.assertEqual(tasks.DIRECT_PREFIX,initial.STRATEGIES['direct'])
        self.assertEqual(tasks._TUPLE.pattern,prior._TUPLE.pattern)
        for identifier,task in tasks.TASKS.items():
            prompt=tasks.trusted_task(identifier)
            self.assertEqual(prompt,prior.DIRECT_PREFIX+'\n'+task['query'])
            self.assertNotIn(tasks.STRATA[identifier],task['query'])
            for evidence in task['evidence']:
                self.assertNotIn(evidence['source_id'],prompt)
                for value in re.findall(r'\d+(?:\.\d+)?',evidence['content']):self.assertNotIn(value,prompt)
            if task['expected']!='ABSTAIN':self.assertNotIn(task['expected'],prompt)

    def test_exact_answers_outer_whitespace_and_wrong_abstention(self):
        for identifier,task in tasks.TASKS.items():
            self.assertTrue(tasks.judge(task['expected'],identifier)['strict_correct'])
            self.assertTrue(tasks.judge(' \n'+task['expected']+'\t',identifier)['strict_correct'])
            self.assertFalse(tasks.judge('Answer: '+task['expected'],identifier)['strict_correct'])
            self.assertFalse(tasks.judge(True,identifier)['strict_correct'])
            self.assertFalse(tasks.judge(None,identifier)['strict_correct'])
        self.assertFalse(tasks.judge('ABSTAIN','entity_mass')['strict_correct'])
        self.assertFalse(tasks.judge('ABSTAIN','entity_mass')['non_abstaining_contract_failure'])

    def test_wrong_fields_and_conversion_conflicts_fail(self):
        expected=tasks.TASKS['entity_mass']['expected'].split('|')
        for index,value in enumerate(('Sequoia','volume','10.7','g','validation-e')):
            parts=list(expected);parts[index]=value
            self.assertEqual(tasks.judge('|'.join(parts),'entity_mass'),{'strict_correct':False,'format_failure':False,'non_abstaining_contract_failure':True})
        for identifier,value in (('unit_mass','Tamarack|mass|900|mg|validation-i'),
                                  ('unit_volume','Dogwood|volume|1400|mL|validation-l'),
                                  ('conflict_mass','Poplar|mass|20.1|mg|validation-m'),
                                  ('conflict_volume','Alder|volume|23.8|mL|validation-p')):
            self.assertFalse(tasks.judge(value,identifier)['strict_correct'])

    def test_registry_mutation_unknown_ids_and_prefix_changes_fail(self):
        altered=deepcopy(tasks.TASKS);altered['unit_mass']['expected']='fake'
        with patch.object(tasks,'TASKS',altered):
            with self.assertRaises(ValueError):tasks.judge('fake','unit_mass')
        with patch.object(tasks,'STRATA',{}):
            with self.assertRaises(ValueError):tasks.trusted_task('entity_mass')
        with patch.object(tasks,'DIRECT_PREFIX','caller override'):
            with self.assertRaises(ValueError):tasks.trusted_task('entity_mass')
        for value in (True,None,'unknown',{'task_id':'entity_mass'}):
            with self.assertRaises(ValueError):tasks.trusted_task(value)

    def test_malformed_correct_fact_is_not_called_semantically_unsupported(self):
        result=tasks.judge('Answer: '+tasks.TASKS['entity_mass']['expected'],'entity_mass')
        self.assertTrue(result['format_failure']);self.assertTrue(result['non_abstaining_contract_failure'])
        self.assertNotIn('unsupported_answer',result)
