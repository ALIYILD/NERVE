"""Fake local opener; never contacts Ollama or modifies its fixed origin."""
import io
import json
import unittest
from unittest.mock import Mock,patch
from urllib.error import HTTPError
from urllib.request import Request
from nerve_awim.memory_gateway import scientific_candidate_transport as s

QUERY="What is sample N0123456789abcdef's mass in mg?"


def fact(source,value='1.2'):
    row=dict(content=f'Sample N0123456789abcdef has mass {value} mg.',source_id=source,version=1,
             current=True,timestamp='2026-01-02T00:00:00Z')
    row['content_sha256']=s.execution.candidates._hash(row);return row


class CandidateTransportTests(unittest.TestCase):
    def setUp(self):
        self.adapter=s._LocalTransport()
        p=patch.object(s,'_INSTANCE',self.adapter);p.start();self.addCleanup(p.stop)
        self.config=s.execution.candidates.SPACE['format_contract'];self.evidence=[fact('source-a')]
        self.captured=[]

    def response(self,**changes):
        result=dict(model=s.MODEL,choices=[dict(finish_reason='stop',message=dict(role='assistant',content=' raw output '))],
                    usage=dict(prompt_tokens=80,completion_tokens=7,total_tokens=87))
        result.update(changes);return result

    def opener(self,value=None):
        def opened(request,timeout):
            self.captured.append((request,timeout))
            return io.BytesIO(json.dumps(self.response() if value is None else value).encode())
        return patch.object(self.adapter._opener.delegate,'open',side_effect=opened)

    def run_model(self,**kwargs):return s.run(self.config,QUERY,self.evidence,authorize=lambda:None,**kwargs)

    def test_exact_payload_preserves_limits_and_actual_usage(self):
        with self.opener():result=self.run_model()
        self.assertEqual(result['raw_output'],' raw output ');self.assertEqual(result['usage'],dict(prompt_tokens=80,completion_tokens=7,total_tokens=87))
        self.assertEqual(result['model_calls'],1)
        request,timeout=self.captured[0];payload=json.loads(request.data)
        expected=s.execution.prepare(self.config,QUERY,self.evidence)
        self.assertEqual(payload['messages'][0]['content'],expected['system'])
        user=json.loads(payload['messages'][1]['content'])
        self.assertEqual(user['query'],QUERY)
        self.assertEqual([json.loads(line) for line in user['evidence_jsonl'].splitlines()],expected['evidence'])
        self.assertEqual(request.full_url,s.ORIGIN+'/v1/chat/completions');self.assertEqual(timeout,90)
        self.assertEqual(payload['max_tokens'],128);self.assertEqual(payload['temperature'],0)
        self.assertNotIn('response_format',payload)

    def test_constrained_diff_only_response_format(self):
        with self.opener():self.run_model();self.run_model(constrained=True)
        first,second=[json.loads(request.data) for request,_ in self.captured]
        self.assertEqual(second.pop('response_format'),dict(type='json_schema',json_schema=dict(name='scientific_measurement',strict=True,schema=s.execution.SCHEMA)))
        self.assertEqual(first,second)

    def test_deterministic_conflict_never_initializes_or_calls_transport(self):
        with patch.object(s,'_transport',side_effect=AssertionError('no network')):
            result=s.run(s.execution.candidates.SPACE['conflict_check'],QUERY,[fact('a'),fact('b','2.3')],authorize=lambda:None)
        self.assertEqual(result['model_calls'],0);self.assertIsNone(result['usage'])

    def test_wrong_model_tool_size_finish_usage_rejected(self):
        cases=[self.response(model='wrong'),self.response(choices=[dict(finish_reason='length',message=dict(role='assistant',content='answer'))]),
            self.response(choices=[dict(finish_reason='stop',message=dict(role='assistant',content='answer',tool_calls=[{}]))]),
            self.response(choices=[dict(finish_reason='stop',message=dict(role='assistant',content='x'*70000))]),
            self.response(usage={'completion_tokens':7}),self.response(usage=dict(prompt_tokens=80,completion_tokens=7,total_tokens=1))]
        for case in cases:
            self.adapter._failures=0;self.adapter._opened_at=None
            with self.opener(case):
                with self.assertRaises((s.InferenceUnavailable,ValueError)):self.run_model()
            self.assertIsNone(self.adapter._binding)
        self.assertEqual(len(self.captured),len(cases))

    def test_parent_contract_drift_rejected_before_delegate(self):
        prepared=s.execution.prepare(self.config,QUERY,self.evidence)
        payload={k:prepared[k] for k in ('system','query','evidence')}
        self.adapter._binding=s._canonical([payload,False])
        request=Request(s.ORIGIN+'/v1/chat/completions',data=b'{}',method='POST',headers={'Content-Type':'application/json','Accept':'application/json'})
        with patch.object(self.adapter._opener.delegate,'open') as call:
            with self.assertRaises(ValueError):self.adapter._opener.open(request,timeout=90.0)
            request.full_url='http://127.0.0.1:9999/v1/chat/completions'
            with self.assertRaises(ValueError):self.adapter._opener.open(request,timeout=90.0)
            call.assert_not_called()
        self.adapter._binding=None

    def test_unsupported_constraint_no_retry_or_plain_fallback(self):
        with patch.object(self.adapter._opener.delegate,'open',side_effect=HTTPError(self.adapter.url,400,'unsupported schema',{},None)) as call:
            with self.assertRaises(s.InferenceUnavailable):self.run_model(constrained=True)
            call.assert_called_once();self.assertIn('response_format',json.loads(call.call_args.args[0].data))

    def test_revoked_before_or_after_response_never_exposes_output(self):
        with self.opener():
            with self.assertRaises(PermissionError):s.run(self.config,QUERY,self.evidence,authorize=Mock(side_effect=PermissionError('denied')))
        self.assertEqual(self.captured,[])
        authorize=Mock(side_effect=[None,None,PermissionError('revoked')])
        with self.opener():
            with self.assertRaises(PermissionError):s.run(self.config,QUERY,self.evidence,authorize=authorize)
        self.assertEqual(len(self.captured),1)

    def test_binding_slot_and_shared_circuit_prevent_mixing_or_retry_storm(self):
        self.adapter._call_slot.acquire()
        with self.opener():
            with self.assertRaises(s.InferenceUnavailable) as error:self.run_model()
            self.assertEqual(error.exception.reason,'capacity')
        self.adapter._call_slot.release();self.assertEqual(self.captured,[])
        with self.opener({'model':'wrong'}):
            for _ in range(3):
                with self.assertRaises(s.InferenceUnavailable):self.run_model()
            with self.assertRaises(s.InferenceUnavailable) as error:self.run_model()
            self.assertEqual(error.exception.reason,'circuit_open')
        self.assertEqual(len(self.captured),3)


if __name__=='__main__':unittest.main()
