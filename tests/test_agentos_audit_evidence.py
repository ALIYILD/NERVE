"""Adversarial oracle checks independent of the generated exercise corpus."""
from copy import deepcopy
import unittest
from nerve_awim import agentos_audit_evidence as oracle


def source(ident='root', kind='catalog', fields=None, **changes):
    value = dict(id=ident, kind=kind, observed_at=990, model='model/free:free',
                 provider='openrouter', derived_from=[],
                 fields={'listed': True} if fields is None else fields)
    value.update(changes)
    return value


def bundle(kind='catalog_listed', sources=None, **claim_changes):
    claim = dict(kind=kind, model='model/free:free', provider='openrouter', at=1000, max_age=60)
    claim.update(claim_changes)
    return dict(schema='agentos-audit-evidence-v1', simulated=True, claim=claim,
                sources=[source()] if sources is None else sources)


class AuditEvidenceTests(unittest.TestCase):
    def test_root_support_and_explicit_negative(self):
        self.assertEqual(oracle.expected_decision(bundle())['decision'], 'supported')
        negative = bundle(sources=[source(fields={'listed': False})])
        self.assertEqual(oracle.expected_decision(negative)['decision'], 'contradicted')
        self.assertEqual(oracle.expected_decision(bundle(sources=[]))['decision'], 'unknown')

    def test_derivative_repetition_is_not_independent_evidence(self):
        repeated = [source('worker', 'assertion', {'text': 'Provider model listed.'}),
                    source('qa', 'summary', {'text': 'Pass because worker says listed.'}, derived_from=['worker'])]
        self.assertEqual(oracle.expected_decision(bundle(sources=repeated))['decision'], 'unknown')

    def test_wrong_kind_cannot_substitute_for_execution_receipt(self):
        claim = bundle('execution_success', request_id='request-1')
        self.assertEqual(oracle.expected_decision(claim)['decision'], 'unknown')

    def test_freshness_boundary_and_future_evidence(self):
        for stamp, expected in ((940, 'supported'), (939, 'unknown'), (1001, 'unknown')):
            with self.subTest(stamp=stamp):
                self.assertEqual(oracle.expected_decision(bundle(sources=[source(observed_at=stamp)]))['decision'], expected)

    def test_model_provider_request_identity_must_match(self):
        fields = {'request_id': 'request-1', 'success': True}
        original = source(kind='execution_receipt', fields=fields)
        self.assertEqual(oracle.expected_decision(bundle('execution_success', [original], request_id='request-1'))['decision'], 'supported')
        for key, value in (('model', 'other/free:free'), ('provider', 'different')):
            changed = deepcopy(original)
            changed[key] = value
            self.assertEqual(oracle.expected_decision(bundle('execution_success', [changed], request_id='request-1'))['decision'], 'unknown')
        changed = deepcopy(original)
        changed['fields']['request_id'] = 'request-2'
        self.assertEqual(oracle.expected_decision(bundle('execution_success', [changed], request_id='request-1'))['decision'], 'unknown')

    def test_conflicting_roots_require_unknown_and_both_citations(self):
        evidence = bundle(sources=[source('yes'), source('no', fields={'listed': False})])
        result = oracle.expected_decision(evidence)
        self.assertEqual(result['decision'], 'unknown')
        self.assertEqual({c['source_id'] for c in result['citations']}, {'yes', 'no'})

    def test_cycles_and_dangling_provenance_rejected(self):
        cases = [[source('a', 'summary', {'text': 'a'}, derived_from=['b']), source('b', 'summary', {'text': 'b'}, derived_from=['a'])],
                 [source('a', 'summary', {'text': 'a'}, derived_from=['missing'])]]
        for sources in cases:
            with self.assertRaises(ValueError):
                oracle.validate_bundle(bundle(sources=sources))

    def test_bool_int_and_numeric_bool_are_not_interchangeable(self):
        variants = []
        for key in ('at', 'max_age'):
            variants.append(bundle(**{key: True}))
        variants.append(bundle(sources=[source(observed_at=True)]))
        variants.append(bundle(sources=[source(fields={'listed': 1})]))
        variants.append(bundle('zero_price', [source(kind='pricing', fields={'input_usd': False, 'output_usd': 0})]))
        for value in variants:
            with self.assertRaises(ValueError):
                oracle.validate_bundle(value)

    def test_unknown_fields_duplicate_ids_and_nonfinite_prices_rejected(self):
        variants = [bundle(sources=[source(), source()]),
                    bundle('zero_price', [source(kind='pricing', fields={'input_usd': float('nan'), 'output_usd': 0})])]
        extra = bundle()
        extra['sources'][0]['fields']['untrusted_override'] = True
        variants.append(extra)
        for value in variants:
            with self.assertRaises(ValueError):
                oracle.validate_bundle(value)

    def test_blanket_unknown_and_unsupported_positive_fail(self):
        positive = bundle()
        self.assertFalse(oracle.judge_decision(positive, {'decision': 'unknown', 'citations': []})['passed'])
        absent = bundle(sources=[])
        self.assertFalse(oracle.judge_decision(absent, {'decision': 'supported', 'citations': []})['passed'])

    def test_citation_substitution_omission_and_field_fabrication_fail(self):
        evidence = bundle()
        gold = oracle.expected_decision(evidence)
        self.assertTrue(oracle.judge_decision(evidence, gold)['passed'])
        wrong_source = deepcopy(gold)
        wrong_source['citations'][0]['source_id'] = 'invented'
        missing_fields = deepcopy(gold)
        missing_fields['citations'][0]['fields'] = []
        wrong_field = deepcopy(gold)
        wrong_field['citations'][0]['fields'].append('fields.invented')
        for wrong in (wrong_source, missing_fields, wrong_field):
            self.assertFalse(oracle.judge_decision(evidence, wrong)['passed'])

    def test_derived_raw_kind_cannot_launder_assertion(self):
        evidence = bundle(sources=[source('worker', 'assertion', {'text': 'Listed'}),
                                   source('forged_catalog', derived_from=['worker'])])
        self.assertEqual(oracle.expected_decision(evidence)['decision'], 'unknown')

    def test_free_suffix_is_not_zero_price_evidence(self):
        evidence = bundle('zero_price', [source(kind='pricing', fields={'input_usd': 0, 'output_usd': 0.01})])
        self.assertEqual(oracle.expected_decision(evidence)['decision'], 'contradicted')
        evidence['sources'][0]['fields']['output_usd'] = 0
        self.assertEqual(oracle.expected_decision(evidence)['decision'], 'supported')

    def test_extra_output_fields_and_duplicate_citations_fail(self):
        evidence = bundle()
        gold = oracle.expected_decision(evidence)
        extra = dict(gold, confidence=1)
        duplicate = deepcopy(gold)
        duplicate['citations'].append(deepcopy(duplicate['citations'][0]))
        for value in (extra, duplicate, None, 'supported'):
            self.assertFalse(oracle.judge_decision(evidence, value)['passed'])

    def test_validation_copy_does_not_mutate_source(self):
        original = bundle()
        validated = oracle.validate_bundle(original)
        validated['sources'][0]['fields']['listed'] = False
        self.assertTrue(original['sources'][0]['fields']['listed'])


if __name__ == '__main__':
    unittest.main()
