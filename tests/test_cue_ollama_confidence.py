"""Protocol tests use synthetic artifacts and HTTP doubles, never actual inference."""
from dataclasses import replace
from hashlib import sha256
import json
import unittest

from nerve_awim.cue_ollama import (HANDOFF_PROMPT_TEMPLATE, HANDOFF_RENDERER,
    HANDOFF_RESPONSE_CONTRACT, PROMPT_TEMPLATE, OllamaCueError)
import test_cue_ollama as fixtures


class OllamaConfidenceTests(unittest.TestCase):
    setUp = fixtures.OllamaCueTests.setUp
    adapter = fixtures.OllamaCueTests.adapter
    request = fixtures.OllamaCueTests.request

    def configured(self, **changes):
        adapter=self.adapter(response_contract=HANDOFF_RESPONSE_CONTRACT,**changes)
        adapter.inspect()
        return adapter

    def response(self, confidence=.37, **changes):
        value={'status':'done','passed':True,'memory_saved':False,'confidence':confidence}
        value.update(changes)
        self.transport.generation_changes={'response':json.dumps(value)}

    def test_optional_protocol_binds_renderer_template_profile_and_inference_identity(self):
        ordinary=self.adapter(); ordinary_report=ordinary.inspect()
        protocol=self.configured(); report=protocol.inspect()
        self.assertEqual(ordinary.profile.template_revision,sha256(PROMPT_TEMPLATE.encode()).hexdigest())
        self.assertEqual(protocol.profile.template_revision,sha256(HANDOFF_PROMPT_TEMPLATE.encode()).hexdigest())
        self.assertNotEqual(ordinary.profile.key,protocol.profile.key)
        self.assertNotEqual(ordinary.model_config.context_digest,protocol.model_config.context_digest)
        self.assertEqual(report['renderer'],HANDOFF_RENDERER)
        self.assertEqual(report['confidence_source'],'model_self_report')
        self.assertFalse(report['confidence_calibrated'])
        self.assertNotIn('response_contract',ordinary_report)
        self.assertEqual(self.transport.generated,0)
        with self.assertRaises(ValueError):self.adapter(response_contract='unrecognized')

    def test_model_confidence_extracted_unchanged_without_grader_or_expected_answer(self):
        adapter=self.configured();self.response(.37)
        task=json.dumps({'id':'case','exit_code':0,'artifact_exists':True,'qa_passed':True,'memory_written':False})
        receipt=adapter(replace(self.request(adapter),instruction=task))
        self.assertFalse(receipt.error)
        self.assertFalse(receipt.synthetic)
        self.assertEqual(receipt.confidence,.37)
        self.assertEqual(receipt.output,'{"memory_saved":false,"passed":true,"status":"done"}')
        self.assertEqual((receipt.input_tokens,receipt.output_tokens,receipt.cost_usd),(12,3,0.))
        body=next(body for path,body in self.transport.calls if path=='/api/generate')
        self.assertEqual(body['prompt'],HANDOFF_PROMPT_TEMPLATE.format(cue='',instruction=task))
        self.assertNotIn('expected',body['prompt'])
        self.assertIn('otherwise unknown if any of exit_code, artifact_exists, qa_passed is null',body['prompt'])
        self.assertIn('your own probability',body['prompt'])
        self.assertTrue(adapter.summary()['confidence_available'])
        self.assertFalse(adapter.summary()['confidence_calibrated'])

    def test_probability_is_not_inferred_from_status_or_passed(self):
        adapter=self.configured()
        self.response(.9,status='failed',passed=False,memory_saved=True)
        failure=adapter(self.request(adapter))
        self.response(.2,status='done',passed=True)
        success=adapter(self.request(adapter))
        self.assertEqual(failure.confidence,.9)
        self.assertEqual(success.confidence,.2)
        self.assertFalse(failure.error)
        self.assertEqual(json.loads(failure.output)['status'],'failed')

    def test_malformed_model_json_is_measured_error_with_no_fabricated_confidence(self):
        valid={'status':'done','passed':True,'memory_saved':False,'confidence':.5}
        malformed=['not JSON','```json\n'+json.dumps(valid)+'\n```',
                   '{"status":"done","status":"failed","passed":true,"memory_saved":false,"confidence":0.5}',
                   json.dumps(dict(valid,confidence=True)),json.dumps(dict(valid,confidence=2)),
                   json.dumps(dict(valid,confidence=-.1)),json.dumps(dict(valid,confidence=float('nan'))),
                   json.dumps(dict(valid,passed=1)),json.dumps(dict(valid,status='success')),
                   json.dumps(dict(valid,extra='private text')),json.dumps({key:value for key,value in valid.items() if key!='confidence'}),
                   ' '*4097+json.dumps(valid)]
        for raw in malformed:
            with self.subTest(index=malformed.index(raw)):
                adapter=self.configured()
                self.transport.generation_changes={'response':raw}
                receipt=adapter(self.request(adapter))
                self.assertTrue(receipt.error)
                self.assertIsNone(receipt.confidence)
                self.assertEqual(receipt.output,'')
                self.assertEqual((receipt.input_tokens,receipt.output_tokens),(12,3))
                summary=adapter.summary()
                self.assertEqual(summary['measured_receipts'],1)
                self.assertEqual(summary['unmeasured_calls'],0)
                self.assertEqual(summary['errors'],1)
                self.assertEqual(summary['last_error'],'handoff_response_invalid')
                self.assertNotIn('private text',json.dumps(summary))

    def test_truncated_json_never_uses_even_a_present_valid_probability(self):
        adapter=self.configured();self.response(.99)
        self.transport.done_reason='length'
        receipt=adapter(self.request(adapter))
        self.assertTrue(receipt.error)
        self.assertIsNone(receipt.confidence)
        self.assertEqual(receipt.output,'')
        self.assertEqual(adapter.summary()['truncations'],1)
        self.assertEqual(adapter.summary()['last_error'],'handoff_response_truncated')

    def test_protocol_mutation_after_inspection_rejected_before_dispatch(self):
        adapter=self.configured();adapter.response_contract=None
        calls=len(self.transport.calls)
        with self.assertRaisesRegex(OllamaCueError,'configuration_changed'):
            adapter(self.request(adapter))
        self.assertEqual(len(self.transport.calls),calls)
        self.assertEqual(self.transport.generated,0)


if __name__=='__main__':unittest.main()
