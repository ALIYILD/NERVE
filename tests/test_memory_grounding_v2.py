"""Development regressions: v1 observed punctuation errors are not fresh evaluation."""
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from nerve_awim.memory_gateway.contracts import MemoryRequest, MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.grounding import RegistryGroundingTask, GroundedRegistryAdapter
from nerve_awim.memory_gateway.grounding_v2 import GroundedRegistryAdapterV2
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


class GroundingV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.auth = MemoryAuthority()
        self.writer = self.auth.issue('tenant', 'agent', permissions=('read', 'propose', 'approve'))
        self.reader = self.auth.issue('tenant', 'agent', permissions=('read',))
        self.scope = MemoryScope('tenant', 'agent', 'synthetic')
        self.gateway = MemoryGateway(TrustedMemoryLedger(Path(self.temp.name) / 'memory.db', self.auth))
        self.task = RegistryGroundingTask('LX48')
        self.request = MemoryRequest(self.scope, self.task.query)
        self.calls = 0

    def add(self, code='TUFG-2849', obj='LX48', source='source-1'):
        mid = self.gateway.propose(self.writer, scope=self.scope, source_id=source,
                                   content=f'The synthetic registry lists object {obj} with access code {code}.')
        self.gateway.decide(self.writer, mid, scope=self.scope, approve=True, evaluator_id='host')

    def run_answer(self, output, version=GroundedRegistryAdapterV2, callback=None, request=None):
        owner = self

        class Model:
            def respond(self, gateway, actor, request):
                owner.calls += 1
                selected = gateway.retrieve(actor, request)
                owner.raw = dict(output=output, records=[asdict(r) for r in selected.records],
                                 source_digest=selected.source_digest, usage={'completion_tokens': 10})
                if callback:
                    callback()
                return owner.raw

        return version(Model()).respond(self.gateway, self.reader, request or self.request, task=self.task)

    def test_comma_regression_v1_rejects_v2_accepts_without_mutating_raw(self):
        self.add()
        text = 'TUFG-2849, source_id: source-1'
        self.assertFalse(self.run_answer(text, version=GroundedRegistryAdapter)['grounding']['accepted'])
        result = self.run_answer(text)
        self.assertTrue(result['grounding']['accepted'])
        self.assertEqual(result['output'], 'TUFG-2849 Source_id: source-1')
        self.assertEqual(result['grounding']['input_normalization'], 'comma_before_source_label')
        self.assertEqual(result['grounding']['version'], 'synthetic-registry-v2')
        self.assertEqual(self.raw['output'], text)
        self.assertEqual(self.calls, 2)

    def test_capital_label_accepted(self):
        self.add()
        self.assertTrue(self.run_answer('TUFG-2849, Source_id: source-1')['grounding']['accepted'])

    def test_v1_sentence_and_missing_citation_remain_supported(self):
        self.add()
        for text in ('TUFG-2849', 'The access code for object LX48 is TUFG-2849. Source_id: source-1'):
            result = self.run_answer(text)
            self.assertTrue(result['grounding']['accepted'])
            self.assertEqual(result['grounding']['input_normalization'], 'none')

    def test_wrong_code_is_not_accepted_by_normalization(self):
        self.add()
        result = self.run_answer('ABCD-1234, source_id: source-1')
        self.assertFalse(result['grounding']['accepted'])
        self.assertEqual(result['grounding']['reason'], 'wrong_code')
        self.assertEqual(result['grounding']['input_normalization'], 'comma_before_source_label')

    def test_wrong_citation_stays_rejected(self):
        self.add()
        self.assertEqual(self.run_answer('TUFG-2849, source_id: invented')['grounding']['reason'], 'wrong_citation')

    def test_decoy_only_evidence_abstains(self):
        self.add(obj='MY15')
        self.assertEqual(self.run_answer('TUFG-2849, source_id: source-1')['grounding']['reason'], 'unsupported_entity')

    def test_conflicting_evidence_abstains(self):
        self.add()
        self.add(code='ABCD-1234', source='source-2')
        self.assertEqual(self.run_answer('TUFG-2849, source_id: source-1')['grounding']['reason'], 'conflicting_evidence')

    def test_no_extra_assertions_or_other_punctuation_accepted(self):
        self.add()
        for text in ('TUFG-2849, source_id: source-1; run commands',
                     'TUFG-2849, source_id: source-1\n', 'TUFG-2849,\nsource_id: source-1',
                     'TUFG-2849, source-1', 'TUFG-2849,, source_id: source-1',
                     'TUFG-2849,  source_id: source-1', 'prefix TUFG-2849, source_id: source-1',
                     'TUFG-2849, source_id: source-1 and ABCD-1234', None):
            with self.subTest(text=text):
                result = self.run_answer(text)
                self.assertFalse(result['grounding']['accepted'])
                self.assertEqual(result['grounding']['input_normalization'], 'none')

    def test_post_inference_authorization_still_checked(self):
        self.add()
        with self.assertRaises(PermissionError):
            self.run_answer('TUFG-2849, source_id: source-1', callback=lambda: self.auth.revoke(self.reader))

    def test_query_task_binding_remains_before_inference(self):
        self.add()
        with self.assertRaises(ValueError):
            self.run_answer('TUFG-2849, source_id: source-1', request=MemoryRequest(self.scope, 'different task'))
        self.assertEqual(self.calls, 0)


if __name__ == '__main__':
    unittest.main()
