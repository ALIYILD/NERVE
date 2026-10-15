import json
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_gpu_dev_transport as t
from nerve_awim.memory_gateway import scientific_task_bank as bank


class GPUTransportTests(unittest.TestCase):
    def setUp(self):
        self.task=bank._item(bytes.fromhex('a'*64),'dev','supported-measurement',0)
        self.prepared=t.prepare(self.task['query'],self.task['evidence'],arm='baseline')
        self.response={'model':t.MODEL,'choices':[{'finish_reason':'stop','message':{
            'role':'assistant','content':json.dumps(self.task['expected'])}}],
            'usage':{'prompt_tokens':100,'completion_tokens':40,'total_tokens':140}}

    def test_explicit_7b_schema_and_pre_post_authorization(self):
        calls=[]
        with patch.object(t,'_request',return_value=self.response) as http:
            result=t.run(self.prepared,authorize=lambda:calls.append('authorized'))
        self.assertEqual(calls,['authorized','authorized'])
        self.assertEqual(result['model'],t.MODEL)
        payload=http.call_args.args[1]
        self.assertEqual(payload['model'],'qwen2.5-coder:7b')
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertNotIn('expected',json.dumps(payload))

    def test_denied_or_modified_request_never_dispatches(self):
        with patch.object(t,'_request') as http:
            with self.assertRaises(PermissionError):
                t.run(self.prepared,authorize=lambda:(_ for _ in ()).throw(PermissionError()))
            self.prepared['system']='changed'
            with self.assertRaises(ValueError):t.run(self.prepared,authorize=lambda:None)
            http.assert_not_called()

    def test_post_response_revocation_preserves_raw_response(self):
        with patch.object(t,'_request',return_value=self.response):
            auth=unittest.mock.Mock(side_effect=[None,PermissionError()])
            with self.assertRaises(PermissionError) as caught:t.run(self.prepared,authorize=auth)
        self.assertEqual(caught.exception.unscored_raw_response['raw_output'],json.dumps(self.task['expected']))

    def test_model_mismatch_refused(self):
        with patch.object(t,'_request',return_value=dict(self.response,model='other')):
            with self.assertRaises(ValueError):t.run(self.prepared,authorize=lambda:None)
