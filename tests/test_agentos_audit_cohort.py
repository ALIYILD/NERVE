"""Composition/gold integrity checks without model inference."""
from copy import deepcopy
import unittest

from nerve_awim import agentos_audit_cohort as module
from nerve_awim.agentos_audit_fixtures import development_cases


class AuditCohortTests(unittest.TestCase):
    def test_hand_authored_gold_and_disjoint_compositions_validate(self):
        value=module.validate_cohort()
        self.assertEqual({phase:len(rows) for phase,rows in value['splits'].items()},
                         {'train':2,'selection':4,'retention':4,'final':6})
        rows=[row for split in value['splits'].values() for row in split]
        self.assertTrue(all(row['bundle']['simulated'] is True for row in rows))
        self.assertTrue(all(len(row['bundle']['sources'])>=3 for row in rows))
        self.assertEqual(len({module.canonical_identity(row) for row in rows}),16)
        self.assertEqual({row['expected']['decision'] for row in rows},
                         {'supported','contradicted','unknown'})
        self.assertIn('share four predicates',value['limitation'])
        self.assertEqual(len(module.revision()),64)

    def test_cosmetic_case_source_model_and_provider_renames_preserve_identity(self):
        original=module.cohort()['splits']['train'][0]
        changed=deepcopy(original)
        changed['id']='renamed-case'
        changed['family']='renamed-family'
        bundle=changed['bundle']
        bundle['claim'].update(model='renamed-model',provider='renamed-provider',request_id='renamed-request',at=5000)
        mapping={source['id']:'new-'+source['id'] for source in bundle['sources']}
        for source in bundle['sources']:
            source['id']=mapping[source['id']]
            source['model']='renamed-model'
            source['provider']='renamed-provider'
            source['observed_at']+=4000
            source['derived_from']=[mapping[parent] for parent in source['derived_from']]
            if 'text' in source['fields']:
                source['fields']['text']='Different prose does not create independent evidence.'
        bundle['sources'].reverse()
        self.assertEqual(module.canonical_identity(original),module.canonical_identity(changed))

    def test_relabelled_public_development_case_rejected(self):
        value=module.cohort()
        recycled=development_cases()[0]
        recycled['id']='new-id'
        recycled['family']='new-family'
        value['splits']['train'][0]=recycled
        with self.assertRaisesRegex(ValueError,'reused'):
            module.validate_cohort(value)

    def test_cross_split_reuse_rejected_even_with_new_labels(self):
        value=module.cohort()
        reused=deepcopy(value['splits']['selection'][0])
        reused['id']='different-id'
        reused['family']='different-family'
        value['splits']['final'][0]=reused
        with self.assertRaisesRegex(ValueError,'reused'):
            module.validate_cohort(value)

    def test_duplicate_family_and_duplicate_id_rejected(self):
        for field in ('id','family'):
            value=module.cohort()
            value['splits']['final'][0][field]=value['splits']['train'][0][field]
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'duplicate'):
                module.validate_cohort(value)

    def test_gold_errors_are_detected_not_rewritten(self):
        value=module.cohort()
        row=value['splits']['selection'][0]
        row['expected']['citations']=[]
        snapshot=deepcopy(row)
        with self.assertRaisesRegex(ValueError,'gold disagrees'):
            module.validate_cohort(value)
        self.assertEqual(row,snapshot)

    def test_applicability_changes_are_not_cosmetic(self):
        original=module.cohort()['splits']['selection'][0]
        changed=deepcopy(original)
        changed['bundle']['sources'][0]['fields']['request_id']='another-request'
        self.assertNotEqual(module.canonical_identity(original),module.canonical_identity(changed))
        changed=deepcopy(original)
        changed['bundle']['sources'][0]['observed_at']=899
        self.assertNotEqual(module.canonical_identity(original),module.canonical_identity(changed))

    def test_source_provenance_changes_identity_and_cycles_fail_validation(self):
        original=module.cohort()['splits']['train'][0]
        changed=deepcopy(original)
        changed['bundle']['sources'][2]['derived_from']=[]
        self.assertNotEqual(module.canonical_identity(original),module.canonical_identity(changed))
        changed['bundle']['sources'][2]['derived_from']=['conclusion']
        with self.assertRaisesRegex(ValueError,'cycle'):
            module.canonical_identity(changed)

    def test_each_call_returns_independent_data(self):
        first=module.cohort()
        first['splits']['train'][0]['expected']['decision']='contradicted'
        self.assertEqual(module.cohort()['splits']['train'][0]['expected']['decision'],'unknown')
    def test_malformed_metadata_and_boolean_identity_rejected(self):
        for value in ([],{},dict(module.cohort(),limitation='Independent production benchmark')):
            with self.subTest(value=type(value)),self.assertRaises(ValueError):
                module.validate_cohort(value)
        value=module.cohort()
        value['splits']['train'][0]['id']=True
        with self.assertRaisesRegex(ValueError,'exact case fields'):
            module.validate_cohort(value)


if __name__=='__main__':
    unittest.main()
