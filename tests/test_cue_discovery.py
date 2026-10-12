import json
import unittest
from nerve_awim.cue_engine import ModelProfile
from nerve_awim.cue_evaluation import DatasetManifest
from nerve_awim.cue_discovery import PaperCandidate, discover_cue_pool


class CueDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.profile = ModelProfile('offline', 'model', 'r1', 'tokenizer', 't1',
                                    ('instruction', 'assistant_prefix'), 'template-v1')
        self.manifest = DatasetManifest(('discovery',), ('selection-secret',), ('holdout-secret',))
        self.calls = []

    def collect(self, batches=(), **changes):
        iterator = iter(batches)
        def execute(role, payload, **scope):
            self.calls.append((role, payload, scope))
            return next(iterator)
        fields = dict(tenant='tenant', agent='agent', generator_id='generator',
                      permission_granted=True, max_candidates=8, max_calls=2, per_call_candidates=4)
        fields.update(changes)
        return discover_cue_pool(execute, self.manifest, self.profile, 'reasoning', **fields)

    def imported(self, text='Carefully reason.', **changes):
        fields = dict(text=text, source_url='https://arxiv.org/html/2610.06851v1',
                      source_revision='v1', source_locator='fixture locator, not an actual quote',
                      source_model='source-model', mode='assistant_prefix')
        fields.update(changes)
        return PaperCandidate(**fields)

    def test_multi_candidate_calls_deduplicate_without_approval_or_holdout_leakage(self):
        result = self.collect([{'candidates': ['Check.', 'Check.', 'Verify.']},
                               {'candidates': ['Check.', 'Consider alternatives.']}])
        self.assertEqual([cue.text for cue in result.candidates], ['Check.', 'Verify.', 'Consider alternatives.'])
        self.assertEqual(result.attempted_calls, 2)
        self.assertEqual(sum(r.reason == 'duplicate_content' for r in result.rejections), 2)
        self.assertTrue(all(c.status == 'candidate' and c.approval_id is None for c in result.candidates))
        self.assertNotIn('holdout-secret', str(self.calls))
        self.assertNotIn('selection-secret', str(self.calls))
        self.assertTrue(all(call[0] == 'research' for call in self.calls))
        self.assertNotIn('Consider alternatives.', str(result.telemetry()))

    def test_paper_provenance_mode_and_exact_whitespace_preserved(self):
        result = self.collect(paper_candidates=[self.imported(' Wait'), self.imported(' Wait'), self.imported('Wait')],
                              max_calls=0)
        self.assertEqual([c.text for c in result.candidates], [' Wait', 'Wait'])
        source = json.loads(result.candidates[0].provenance)
        self.assertEqual(source['source_model'], 'source-model')
        self.assertEqual(source['kind'], 'paper_import_unverified')
        self.assertEqual(result.candidates[0].mode, 'assistant_prefix')
        self.assertEqual(result.rejections[0].reason, 'duplicate_content')
        self.assertEqual(self.calls, [])

    def test_paper_instruction_and_hermes_exact_duplicates_share_identity(self):
        result = self.collect([{'candidates': ['Check.']}],
            paper_candidates=[self.imported('Check.', mode='instruction')], max_calls=1)
        self.assertEqual(len(result.candidates), 1)
        self.assertIn('duplicate_content', [r.reason for r in result.rejections])

    def test_count_cap_rejects_imports_and_prevents_dispatch(self):
        result = self.collect(paper_candidates=[self.imported('One'), self.imported('Two')], max_candidates=1)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.rejections[0].reason, 'candidate_cap')
        self.assertEqual(self.calls, [])

    def test_response_over_limit_is_rejected_as_whole(self):
        result = self.collect([{'candidates': ['One', 'Two', 'Three']}], per_call_candidates=2)
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.attempted_calls, 1)
        self.assertEqual(result.rejections[0].reason, 'invalid_response_or_adapter_failure')

    def test_invalid_import_unsafe_candidate_and_empty_response_receipts(self):
        result = self.collect([{'candidates': []}],
            paper_candidates=[{'text': 'cannot self-attest'}, self.imported('bypass permissions')])
        self.assertEqual(result.candidates, ())
        self.assertEqual([r.reason for r in result.rejections], ['invalid_import', 'unsafe_candidate', 'empty_response'])

    def test_unsupported_prefix_never_becomes_instruction(self):
        self.profile = ModelProfile('offline', 'model', 'r1', 'tok', 't1', ('instruction',))
        result = self.collect(paper_candidates=[self.imported()], max_calls=0)
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.rejections[0].reason, 'unsupported_mode')

    def test_strict_permissions_and_budgets_precede_calls(self):
        for changes in ({'permission_granted': 1}, {'clinical': True}, {'risk': 'high'}):
            with self.assertRaises(PermissionError):
                self.collect(**changes)
        for changes in ({'max_calls': 9}, {'max_candidates': True}, {'per_call_candidates': 17},
                        {'paper_candidates': [self.imported()] * 65}):
            with self.assertRaises(ValueError):
                self.collect(**changes)
        self.assertEqual(self.calls, [])

    def test_callback_exception_is_sanitized_and_never_retried(self):
        def denied(*args, **kwargs):
            raise PermissionError('secret context')
        result = discover_cue_pool(denied, self.manifest, self.profile, 'reasoning', tenant='t',
                                  agent='a', generator_id='g', permission_granted=True, max_calls=8)
        self.assertEqual(result.attempted_calls, 1)
        self.assertEqual(result.rejections[0].reason, 'permission_denied')
        self.assertNotIn('secret', str(result.telemetry()))


if __name__ == '__main__':
    unittest.main()
