"""The registered runner teaches output structure without providing gold answers."""
import copy
import json
import unittest
from unittest.mock import patch

import test_agentos_cohort_study as fixtures

runner=fixtures.runner
oracle=fixtures.oracle


class CohortPromptTests(unittest.TestCase):
    def test_explicit_citation_schema_same_for_every_phase_and_arm(self):
        groups=fixtures.legacy.cohort()['splits']
        prefixes=set()
        for phase in ('train','selection','retention','final'):
            for advice in (None,'Check provenance.'):
                with patch.object(oracle,'expected_decision',side_effect=AssertionError('gold accessed')):
                    prompt=runner.prediction_prompt(groups,phase,advice)
                prefix,payload=prompt.rsplit('\n',1)
                prefixes.add(prefix)
                self.assertIn('exactly "source_id" and "fields"',prefix)
                self.assertIn('array of unique field-name strings, not an object or field values',prefix)
                self.assertIn('"fields.KEY" for every key',prefix)
                decoded=json.loads(payload)
                self.assertEqual(decoded,dict(tasks=[dict(id=r['id'],bundle=r['bundle']) for r in groups[phase]],advice=advice))
                self.assertNotIn('expected',decoded)
        self.assertEqual(len(prefixes),1)

    def test_structural_example_is_not_task_specific_gold(self):
        groups=fixtures.legacy.cohort()['splits']
        prefix=runner.prediction_prompt(groups,'train').rsplit('\n',1)[0]
        example=prefix.split('Citation structure example only: ',1)[1].split('. Replace placeholders',1)[0]
        self.assertEqual(json.loads(example),dict(source_id='<source id>',fields=['model','provider','observed_at','fields.<key>']))

    def test_grader_still_rejects_copied_source_records_and_object_fields(self):
        rows=fixtures.legacy.cohort()['splits']['train']
        row=next(r for r in rows if oracle.expected_decision(r['bundle'])['citations'])
        correct=oracle.expected_decision(row['bundle'])
        self.assertTrue(oracle.judge_decision(row['bundle'],correct)['passed'])
        source=next(s for s in row['bundle']['sources'] if s['id']==correct['citations'][0]['source_id'])
        copied=copy.deepcopy(correct);copied['citations']=[copy.deepcopy(source)]
        object_fields=copy.deepcopy(correct);object_fields['citations'][0]['fields']=copy.deepcopy(source['fields'])
        for malformed in (copied,object_fields):
            judged=oracle.judge_decision(row['bundle'],malformed)
            self.assertFalse(judged['passed'])
            self.assertEqual(judged['category'],'invalid_output')


if __name__=='__main__':
    unittest.main()
