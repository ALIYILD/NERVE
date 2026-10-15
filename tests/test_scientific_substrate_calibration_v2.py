"""Real DEV bank/claims/authority with mocked local inference; no model calls."""
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_substrate_calibration_v2 as s

DIGEST='d'*64


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.root=self.base/'calibration';self.journal=self.base/'shared.sqlite';self.bank=self.base/'bank'
        self.pin=s.bank_module.build(self.bank,host_seed='a'*64)['manifest_sha256']
        original_read=s.bank_module._read
        def dev_only(path,limit):
            if Path(path).name=='holdout.json':raise AssertionError('holdout closed')
            return original_read(path,limit)
        p=patch.object(s.bank_module,'_read',side_effect=dev_only);p.start();self.addCleanup(p.stop)
        for name,value in [('metadata',{'model':s.pilot.MODEL,'digest':DIGEST}),('preload',{'wall_seconds':0.01}),('runtime_version','fixture-runtime')]:
            p=patch.object(s,name,return_value=value);setattr(self,name,p.start());self.addCleanup(p.stop)
        p=patch.object(s.transport,'run',side_effect=self.respond);self.model=p.start();self.addCleanup(p.stop)
        self.inputs=dict(bank_directory=self.bank,bank_manifest_sha256=self.pin)
        old=s.predecessor;previous=self.base/'v1';previous_journal=self.base/'v1-shared.sqlite'
        with patch.object(old,'metadata',return_value={'model':s.pilot.MODEL,'digest':DIGEST}),patch.object(old,'preload',return_value={'wall_seconds':0.01}),patch.object(old,'runtime_version',return_value='fixture-runtime'),patch.object(old.transport,'run',side_effect=TimeoutError('v1')):
            old.run(previous,DIGEST,previous_journal,**self.inputs)
        self.inputs.update(predecessor_directory=previous,predecessor_journal=previous_journal)

    def respond(self,prepared,*,authorize,timeout_seconds):
        with sqlite3.connect(self.root/'claim.sqlite') as db:
            count=db.execute('SELECT COUNT(*) FROM calls').fetchone()[0]
            status=db.execute('SELECT status FROM calls ORDER BY ordinal DESC LIMIT 1').fetchone()[0]
        self.assertEqual(count,self.model.call_count);self.assertEqual(status,'claimed')
        self.assertTrue((self.root/'preregistration.json').is_file());self.assertEqual(timeout_seconds,240)
        authorize();arm=prepared['arm'];compact=s.transport.compact.prepare(prepared['query'],prepared['evidence'])
        fact=compact['aliases']['A0']
        raw=('ABSTAIN' if arm=='compact' else json.dumps({'status':'abstain','entity':'nonempty'}) if arm=='original'
             else f"{fact['value']}|{fact['unit']}|A0")
        authorize()
        return dict(raw_output=raw,usage={'prompt_tokens':490 if arm=='original' else 81,'completion_tokens':8,'total_tokens':498 if arm=='original' else 89},
            finish_reason='stop',model=s.pilot.MODEL,origin=s.pilot.ORIGIN,model_sampling_seed=s.SEED,
            input_sha256=prepared['input_sha256'],model_calls=1,review_required=True,synthetic_only=True)

    def run_study(self):return s.run(self.root,DIGEST,self.journal,**self.inputs)

    def test_prepare_is_network_free_and_freezes_exact30_prompts(self):
        protocol=s.register(self.root,DIGEST,self.journal,**self.inputs)
        self.assertEqual(len(protocol['tasks']),10);self.assertEqual(len(protocol['schedule']),30);self.assertEqual(len(protocol['prompts']),30)
        self.assertTrue(all(t['split']=='dev' and t['stratum']=='supported-measurement' for t in protocol['tasks']))
        self.model.assert_not_called();self.metadata.assert_not_called();self.preload.assert_not_called()
        self.assertEqual(s.register(self.root,DIGEST,self.journal,**self.inputs),protocol)

    def test_real30_schedule_raw_results_ceiling_and_networkfree_resume(self):
        report=self.run_study();self.assertEqual(report['status'],'complete',report)
        self.assertEqual(self.model.call_count,30);self.assertEqual(report['summary']['verdict'],'1.5B model is the ceiling')
        self.assertFalse(report['holdout_accessed']);self.assertFalse(report['promotion_authorized'])
        arms={r['arm']:r for r in report['summary']['arms']}
        self.assertEqual(arms['original']['declared_abstention'],10);self.assertEqual(arms['original']['malformed'],10)
        self.assertEqual(arms['forced_answer']['strict_correct'],10);self.assertEqual(arms['compact']['valid_parsed_answer_rate'],0)
        paths=[self.root/'report.json',self.root/'claim.sqlite',self.root/'preregistration.json']
        before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
        self.assertEqual(self.run_study(),report);self.assertEqual(self.model.call_count,30)
        self.assertEqual({str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths},before)

    def test_consumed_timeout_never_retries(self):
        self.model.side_effect=TimeoutError('fixture')
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.assertEqual(report['model_attempts'],1)
        self.assertEqual(self.run_study(),report);self.assertEqual(self.model.call_count,1)

    def test_wall_budget_includes_preload(self):
        clock=[0.0]
        def preload():clock[0]=3601.0;return {'wall_seconds':0.01}
        with patch.object(s.time,'monotonic',side_effect=lambda:clock[0]),patch.object(s,'preload',side_effect=preload):
            report=self.run_study()
        self.assertEqual(report['status'],'failed_consumed');self.model.assert_not_called()

    def test_deleted_claim_or_shared_history_never_reset(self):
        s.register(self.root,DIGEST,self.journal,**self.inputs);(self.root/'claim.sqlite').unlink()
        with self.assertRaises(ValueError):self.run_study()
        self.assertFalse((self.root/'claim.sqlite').exists());self.model.assert_not_called()

    def test_different_directory_shared_claim_rejected(self):
        s.register(self.root,DIGEST,self.journal,**self.inputs)
        with self.assertRaises(sqlite3.IntegrityError):s.register(self.base/'other',DIGEST,self.journal,**self.inputs)
        self.model.assert_not_called()

    def test_tampered_completed_score_rejected_even_rehashed(self):
        report=self.run_study();report['rows'][0]['score']['strict_correct']=True
        encoded=s.canonical(report)
        with sqlite3.connect(self.root/'claim.sqlite') as db:db.execute('UPDATE calibration SET report=?,digest=?',(encoded,sha256(encoded.encode()).hexdigest()))
        with self.assertRaises(ValueError):self.run_study()
        self.assertEqual(self.model.call_count,30)

    def test_final_identity_failure_removes_summary_and_consumes(self):
        self.metadata.side_effect=[{'model':s.pilot.MODEL,'digest':DIGEST},{'model':s.pilot.MODEL,'digest':'f'*64}]
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.assertNotIn('summary',report)
        self.assertEqual(self.model.call_count,30)
        self.assertEqual(s.validate_receipt(self.root,DIGEST,self.journal,**self.inputs),report)

    def test_readonly_validator_never_initializes_or_dispatches(self):
        with self.assertRaises(OSError):s.validate_receipt(self.root,DIGEST,self.journal,**self.inputs)
        self.assertFalse(self.root.exists())
        s.register(self.root,DIGEST,self.journal,**self.inputs)
        with self.assertRaises(ValueError):s.validate_receipt(self.root,DIGEST,self.journal,**self.inputs)
        self.model.assert_not_called();self.metadata.assert_not_called()

    def test_invalid_preload_blocks_dispatch(self):
        self.preload.return_value={}
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.model.assert_not_called()

    def test_failed_summary_or_predispatch_tamper_rejected(self):
        self.model.side_effect=TimeoutError('fixture');original=self.run_study()
        for mutate in (lambda r:r.update(summary={'verdict':'improvement'}),lambda r:r.update(preload={}),lambda r:r['metadata_before'].update(digest='f'*64)):
            report=deepcopy(original);mutate(report);encoded=s.canonical(report)
            with sqlite3.connect(self.root/'claim.sqlite') as db:db.execute('UPDATE calibration SET report=?,digest=?',(encoded,sha256(encoded.encode()).hexdigest()))
            with self.assertRaises(ValueError):self.run_study()
        self.assertEqual(self.model.call_count,1)

    def test_original_exact_template_forced_only_changes_contract(self):
        task=s.selected(self.bank,self.pin)[0]
        compact=s.transport.prepare('compact',task['query'],task['evidence']);forced=s.transport.prepare('forced_answer',task['query'],task['evidence'])
        original=s.transport.prepare('original',task['query'],task['evidence'])
        self.assertEqual(compact['messages'][1],forced['messages'][1])
        self.assertEqual(forced['messages'][0]['content'],s.transport.FORCED_SYSTEM)
        old=s.transport.original.prepare(s.transport.original.candidates.SPACE['conflict_check'],task['query'],task['evidence'])
        self.assertEqual(original['messages'][0]['content'],old['system'])
        self.assertNotIn('response_format',original)

    def test_declared_abstention_is_independent_of_format(self):
        task=s.selected(self.bank,self.pin)[0]
        value=s.score('{"status":"abstain","entity":"nonempty"}','original',task)
        self.assertTrue(value['declared_abstention']);self.assertTrue(value['malformed']);self.assertFalse(value['strict_correct'])
        self.assertFalse(s.score('Maybe abstain?','original',task)['declared_abstention'])


    def test_condition_order_same_prior_inputs(self):
        p=s.register(self.root,DIGEST,self.journal,**self.inputs)
        old=json.loads((self.inputs['predecessor_directory']/'report.json').read_text())['protocol']
        self.assertEqual(p['tasks'],old['tasks']);self.assertEqual(p['prompts'],old['prompts'])
        self.assertEqual([a for _,a in p['schedule']],['compact']*10+['forced_answer']*10+['original']*10)

    def test_original_socket_timeout_retains_only_completed_conditions(self):
        def call(prepared,**kwargs):
            if prepared['arm']=='original':raise s.transport.TransportTimeout('socket')
            return self.respond(prepared,**kwargs)
        self.model.side_effect=call
        report=self.run_study();self.assertEqual(report['model_attempts'],21)
        self.assertEqual(report['partial_calibration']['infrastructure_finding'],'original prompt infeasible on this substrate')
        self.assertEqual([a['count'] for a in report['partial_calibration']['arms']],[10,10]);self.assertNotIn('summary',report)
        self.assertEqual(s.validate_receipt(self.root,DIGEST,self.journal,**self.inputs),report)
        self.assertEqual(self.run_study(),report);self.assertEqual(self.model.call_count,21)

    def test_original_deadline_is_not_socket_timeout_finding(self):
        def call(prepared,**kwargs):
            if prepared['arm']=='original':raise TimeoutError('wall_budget')
            return self.respond(prepared,**kwargs)
        self.model.side_effect=call
        report=self.run_study();self.assertEqual(report['model_attempts'],21)
        self.assertNotIn('partial_calibration',report);self.assertNotIn('summary',report)

    def test_predecessor_change_during_timeout_blocks_publication(self):
        def call(prepared,**kwargs):
            (self.inputs['predecessor_directory']/'report.json').write_text('{}')
            raise s.transport.TransportTimeout('socket')
        self.model.side_effect=call
        with self.assertRaises(ValueError):self.run_study()
        self.assertFalse((self.root/'report.json').exists())

    def test_predecessor_paths_are_preserved(self):
        with self.assertRaises(ValueError):s.register(self.inputs['predecessor_directory'],DIGEST,self.journal,**self.inputs)
        with self.assertRaises(ValueError):s.register(self.root,DIGEST,self.inputs['predecessor_journal'],**self.inputs)
        self.model.assert_not_called()

    def test_partial_requires_valid_post_identity(self):
        self.metadata.side_effect=[{'model':s.pilot.MODEL,'digest':DIGEST},{'model':s.pilot.MODEL,'digest':'f'*64}]
        def call(prepared,**kwargs):
            if prepared['arm']=='original':raise s.transport.TransportTimeout('socket')
            return self.respond(prepared,**kwargs)
        self.model.side_effect=call
        report=self.run_study();self.assertNotIn('partial_calibration',report);self.assertNotIn('summary',report)


class CalibrationTransportTests(unittest.TestCase):
    def test_constructor_cap_and_socket_vs_authorization_timeout(self):
        t=s.transport
        with patch.object(t,'LocalInferenceAdapter') as adapter:
            t._adapter(240)
            self.assertEqual(adapter.call_args.kwargs['timeout_seconds'],90)
        from nerve_awim.memory_gateway.scientific_candidate_transport_smoke import evidence,QUERY
        prepared=t.prepare('compact',QUERY,evidence())
        class Adapter:
            @property
            def _opener(self):return self
            def open(self,*args,**kwargs):raise TimeoutError('actualsocket')
        with patch.object(t,'_adapter',return_value=Adapter()):
            with self.assertRaises(t.TransportTimeout):t.run(prepared,authorize=lambda:None)
        def deadline():raise TimeoutError('deadline')
        with self.assertRaises(TimeoutError) as caught:t.run(prepared,authorize=deadline)
        self.assertNotIsInstance(caught.exception,t.TransportTimeout)

    def test_length_raw_retained_with_seed_and_equal_budget(self):
        from nerve_awim.memory_gateway.scientific_candidate_transport_smoke import evidence,QUERY
        t=s.transport;prepared=t.prepare('original',QUERY,evidence());seen=[]
        class Adapter:
            @property
            def _opener(self):return self
            def open(self,request,*,timeout):
                seen.append(json.loads(request.data));self_timeout=timeout
                if self_timeout!=240:raise AssertionError('actual socket timeout must be240')
                return io.BytesIO(json.dumps({'model':t.MODEL,'choices':[{'finish_reason':'length','message':{'role':'assistant','content':'{"status":'}}],
                    'usage':{'prompt_tokens':490,'completion_tokens':128,'total_tokens':618}}).encode())
        with patch.object(t,'_adapter',return_value=Adapter()):
            result=t.run(prepared,authorize=lambda:None,timeout_seconds=240)
        self.assertEqual(result['raw_output'],'{"status":');self.assertEqual(result['finish_reason'],'length')
        self.assertEqual(seen[0]['seed'],20261015);self.assertEqual(seen[0]['max_tokens'],128)
        calls=[0]
        def authorize():
            calls[0]+=1
            if calls[0]==2:raise TimeoutError('wall_budget_after_response')
        with patch.object(t,'_adapter',return_value=Adapter()):
            with self.assertRaises(TimeoutError) as caught:t.run(prepared,authorize=authorize)
        self.assertNotIsInstance(caught.exception,t.TransportTimeout)
        self.assertEqual(caught.exception.unscored_raw_response['raw_output'],'{"status":')


if __name__=='__main__':unittest.main()
