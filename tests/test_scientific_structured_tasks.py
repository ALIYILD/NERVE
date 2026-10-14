from copy import deepcopy
import json
import re
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_structured_tasks as tasks
from nerve_awim.memory_gateway import scientific_measurement_tasks as initial
from nerve_awim.memory_gateway import scientific_interface_tasks as development
from nerve_awim.memory_gateway import scientific_interface_validation_tasks as validation


class ScientificStructuredTasksTests(unittest.TestCase):
    def test_two_fresh_tasks_and_generic_schema(self):
        self.assertEqual(len(tasks.TASKS),2)
        self.assertEqual(tasks.ARMS,('unrestricted_json','schema_json'))
        self.assertEqual(tasks.SCHEMA['properties']['status']['enum'],['answer','abstain'])
        self.assertIs(tasks.SCHEMA['additionalProperties'],False)
        self.assertEqual(set(tasks.SCHEMA['required']),{'status','entity','measurement','value','unit','source_id'})
        for name,schema in tasks.SCHEMA['properties'].items():
            if name!='status':self.assertEqual(schema,{'type':'string'})
        old=[e for module in (initial,development,validation) for t in module.TASKS.values() for e in t['evidence']]
        old_names={n for e in old for n in re.findall(r'Sample ([A-Za-z]+)',e['content'])}
        old_values={v for e in old for v in re.findall(r'\d+(?:\.\d+)?',e['content'])}
        old_sources={e['source_id'] for e in old}
        for task in tasks.TASKS.values():
            self.assertEqual(len(task['evidence']),2)
            for evidence in task['evidence']:
                self.assertTrue(old_names.isdisjoint(re.findall(r'Sample ([A-Za-z]+)',evidence['content'])))
                self.assertTrue(old_values.isdisjoint(re.findall(r'\d+(?:\.\d+)?',evidence['content'])))
                self.assertNotIn(evidence['source_id'],old_sources)

    def test_keys_never_encoded_in_schema_or_task_instruction(self):
        schema=json.dumps(tasks.SCHEMA)
        for task_id,task in tasks.TASKS.items():
            prompt=tasks.trusted_task(task_id)
            self.assertEqual(prompt,tasks.INSTRUCTION+'\n'+task['query']+'\nOutput schema: '+json.dumps(tasks.SCHEMA,sort_keys=True,separators=(',',':')))
            for evidence in task['evidence']:
                self.assertNotIn(evidence['source_id'],prompt);self.assertNotIn(evidence['source_id'],schema)
                for number in re.findall(r'\d+(?:\.\d+)?',evidence['content']):
                    self.assertNotIn(number,prompt);self.assertNotIn(number,schema)
                for name in re.findall(r'Sample ([A-Za-z]+)',evidence['content']):self.assertNotIn(name,schema)

    def test_exact_supported_and_empty_abstention(self):
        for task_id,task in tasks.TASKS.items():
            output=json.dumps(task['expected'])
            self.assertEqual(tasks.judge(output,task_id),{'schema_valid':True,'format_valid':True,'strict_correct':True,'unsupported_selection':False})
            self.assertTrue(tasks.judge(' \n'+output+'\t',task_id)['strict_correct'])
        answer=deepcopy(tasks.TASKS['supported_mass']['expected']);answer['entity']='Sample Magnolia'
        self.assertFalse(tasks.judge(json.dumps(answer),'supported_mass')['strict_correct'])

    def test_duplicate_nonfinite_extra_missing_wrongtype_and_prose_rejected(self):
        expected=tasks.TASKS['supported_mass']['expected']
        variants=[True,None,42,'[]','{}','```'+json.dumps(expected)+'```','Answer: '+json.dumps(expected),
                  json.dumps(expected)[:-1]+',"status":"answer"}',
                  json.dumps({**expected,'extra':'key'}),json.dumps({k:v for k,v in expected.items() if k!='unit'}),
                  json.dumps({**expected,'value':26.5}),json.dumps({**expected,'value':True}),
                  json.dumps({**expected,'value':float('nan')}),json.dumps({**expected,'value':float('inf')}),
                  json.dumps({**expected,'status':'unknown'})]
        for output in variants:
            with self.subTest(output=output):
                self.assertEqual(tasks.judge(output,'supported_mass'),{'schema_valid':False,'format_valid':False,'strict_correct':False,'unsupported_selection':False})

    def test_abstain_requires_every_other_field_empty(self):
        expected=tasks.TASKS['conflicting_mass']['expected']
        for name in ('entity','measurement','value','unit','source_id'):
            bad={**expected,name:'nonempty'}
            output=json.dumps(bad)
            self.assertEqual(tasks.parse_shape(output),bad)
            with self.assertRaises(ValueError):tasks.parse(output)
            self.assertEqual(tasks.judge(output,'conflicting_mass'),{'schema_valid':True,'format_valid':False,'strict_correct':False,'unsupported_selection':False})

    def test_unsupported_selection_is_narrow_parsed_conflict_answer(self):
        answer={'status':'answer','entity':'Buckeye','measurement':'mass','value':'29.2','unit':'mg','source_id':'structured-c'}
        self.assertEqual(tasks.judge(json.dumps(answer),'conflicting_mass'),{'schema_valid':True,'format_valid':True,'strict_correct':False,'unsupported_selection':True})
        malformed='The value is 29.2 mg.'
        self.assertFalse(tasks.judge(malformed,'conflicting_mass')['unsupported_selection'])
        wrong={**tasks.TASKS['supported_mass']['expected'],'unit':'g'}
        self.assertEqual(tasks.judge(json.dumps(wrong),'supported_mass'),{'schema_valid':True,'format_valid':True,'strict_correct':False,'unsupported_selection':False})

    def test_frozen_registry_schema_instruction_and_ids(self):
        for name,value in (('TASKS',{}),('SCHEMA',{}),('INSTRUCTION','caller task'),('ARMS',('other',))):
            with patch.object(tasks,name,value):
                with self.assertRaises(ValueError):tasks.trusted_task('supported_mass')
        altered=deepcopy(tasks.SCHEMA);altered['additionalProperties']=0
        with patch.object(tasks,'SCHEMA',altered):
            with self.assertRaises(ValueError):tasks.trusted_task('supported_mass')
        for task_id in (True,None,'unknown',{'task_id':'supported_mass'}):
            with self.assertRaises(ValueError):tasks.trusted_task(task_id)
