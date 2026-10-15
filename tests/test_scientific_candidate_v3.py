import io
import json
import unittest
from unittest.mock import Mock,patch
from nerve_awim.memory_gateway import scientific_candidate_v3 as v

Q="What is sample N1122334455667788's mass in mg?"

def fact(content,source='source1',current=True):
    row=dict(content=content,source_id=source,version=1,current=current,timestamp='2026-10-15T00:00:00Z')
    row['content_sha256']=v.grammar.candidates._hash(row)
    return row

GOOD=fact('Sample N1122334455667788 has mass 12.3 mg.')
DECOY=fact('Sample N9988776655443322 has mass 77.4 mg.','source2')

class V3Tests(unittest.TestCase):
    def test_matching_target_with_decoys_proceeds_all_aliases_visible(self):
        prepared=v.prepare(Q,[GOOD,DECOY])
        self.assertEqual(prepared['route'],'model');self.assertEqual(len(prepared['aliases']),2)
        self.assertIn('77.4',prepared['user']);self.assertEqual(prepared['schema']['properties']['source_id']['enum'],['A0','A1'])
        self.assertNotIn('expected',json.dumps(prepared));self.assertNotIn('12.3',prepared['system'])

    def test_gate_rejections_zero_calls(self):
        cases=[[],[DECOY],[fact('Sample N1122334455667788 has mass 1.8 g.')],
               [GOOD,fact('Sample N1122334455667788 has mass 14.2 mg.','other')]]
        with patch.object(v.calibration,'_adapter') as adapter:
            for evidence in cases:
                output=v.run(v.prepare(Q,evidence),authorize=lambda:None)
                self.assertEqual(output['model_calls'],0);self.assertIsNone(output['usage'])
                self.assertEqual(output['raw_output'],'ABSTAIN')
            adapter.assert_not_called()

    def test_stale_and_different_entity_unit_do_not_create_conflict(self):
        records=[GOOD,DECOY,fact('Sample N1122334455667788 has temperature 99 C.','temperature'),fact('Sample N1122334455667788 has mass 999 mg.','stale',False),
                 fact('Sample N1122334455667788 has mass 9 g.','wrongunit')]
        prepared=v.prepare(Q,records);self.assertEqual(prepared['route'],'model')
        self.assertEqual(len(prepared['aliases']),4);self.assertIn('9 g',prepared['user'])
        self.assertEqual(prepared['schema']['properties']['unit']['enum'],['C','g','mg'])
        self.assertTrue(v.gate(Q,[GOOD,fact('Sample N1122334455667788 has mass 12.300 mg.','same')])['eligible'])

    def test_decode_strict_numeric_alias_no_semantic_repair(self):
        prepared=v.prepare(Q,[GOOD,DECOY])
        out=v.decode('{"value":77.4,"unit":"mg","source_id":"A1"}',prepared)
        self.assertEqual(out['entity'],'N9988776655443322');self.assertEqual(out['value'],'77.4')
        for raw in ('ABSTAIN','{"value":"12.3","unit":"mg","source_id":"A0"}',
                    '{"value":12.3,"unit":"mg","source_id":"A9"}',
                    '{"value":1e999999,"unit":"mg","source_id":"A0"}',
                    '{"value":12.3,"value":77,"unit":"mg","source_id":"A0"}'):
            with self.assertRaises(ValueError):v.decode(raw,prepared)

    def response(self,finish='stop'):
        return dict(model=v.MODEL,choices=[dict(finish_reason=finish,message=dict(role='assistant',content='{"value":12.3,"unit":"mg","source_id":"A0"}'))],
                    usage=dict(prompt_tokens=90,completion_tokens=15,total_tokens=105))

    def test_payload_schema_seed_budget_timeout_and_length_raw_preserved(self):
        seen=[]
        def open_(request,timeout):
            seen.append((json.loads(request.data),timeout));return io.BytesIO(json.dumps(self.response('length')).encode())
        adapter=Mock();adapter._opener.open.side_effect=open_
        with patch.object(v.calibration,'_adapter',return_value=adapter):
            for arm in ('candidate','baseline'):
                result=v.run(v.prepare(Q,[GOOD,DECOY],arm=arm),authorize=lambda:None)
                self.assertEqual(result['finish_reason'],'length');self.assertEqual(result['model_calls'],1)
        self.assertIn('response_format',seen[0][0]);self.assertNotIn('response_format',seen[1][0])
        self.assertEqual(seen[0][0]['messages'][1],seen[1][0]['messages'][1])
        self.assertTrue(all(p['max_tokens']==128 and p['seed']==20261015 and t==30.0 for p,t in seen))

    def test_authorization_and_mutations_discard_response(self):
        prepared=v.prepare(Q,[GOOD]);auth=Mock(side_effect=[None,PermissionError('revoked')])
        adapter=Mock();adapter._opener.open.return_value=io.BytesIO(json.dumps(self.response()).encode())
        with patch.object(v.calibration,'_adapter',return_value=adapter):
            with self.assertRaises(PermissionError) as caught:v.run(prepared,authorize=auth)
            diagnostic=caught.exception.unscored_raw_response
            self.assertEqual(diagnostic['raw_output'],self.response()['choices'][0]['message']['content'])
            self.assertEqual(diagnostic['usage'],self.response()['usage'])
            self.assertEqual(diagnostic['reason'],'post_response_authorization_failed')
            self.assertNotIn('score',diagnostic)
        def mutate():prepared['system']='changed'
        with self.assertRaises(ValueError):v.run(prepared,authorize=mutate)

    def test_schema_mutation_and_schema_validity(self):
        prepared=v.prepare(Q,[GOOD])
        self.assertTrue(v.schema_valid('{"value":12.3,"unit":"mg","source_id":"A0"}',prepared))
        self.assertFalse(v.schema_valid('ABSTAIN',prepared))
        self.assertIsNone(v.schema_valid('ABSTAIN',v.prepare(Q,[])))
        def mutate():prepared['schema']['properties']['source_id']['enum'].append('A9')
        with patch.object(v.calibration,'_adapter') as adapter:
            with self.assertRaises(ValueError):v.run(prepared,authorize=mutate)
            adapter.assert_not_called()

    def test_wrong_identity_and_tool_calls_fail_without_retry(self):
        for change in ('model','tool'):
            response=self.response()
            if change=='model':response['model']='wrong'
            else:response['choices'][0]['message']['tool_calls']=[{}]
            adapter=Mock();adapter._opener.open.return_value=io.BytesIO(json.dumps(response).encode())
            with patch.object(v.calibration,'_adapter',return_value=adapter):
                with self.assertRaises(ValueError):v.run(v.prepare(Q,[GOOD]),authorize=lambda:None)
                adapter._opener.open.assert_called_once()

    def test_labels_in_evidence_rejected_and_timeout_fixed(self):
        row=dict(GOOD,expected='12.3')
        with self.assertRaises(ValueError):v.prepare(Q,[row])
        with self.assertRaises(ValueError):v.run(v.prepare(Q,[GOOD]),authorize=lambda:None,timeout_seconds=90)
        with patch.object(v,'SYSTEM','changed'):
            with self.assertRaises(ValueError):v.prepare(Q,[GOOD])

if __name__=='__main__':unittest.main()
