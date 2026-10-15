"""Mock transport; real authoritative memory and durable single-use claims."""
import io
import importlib.util
from contextlib import redirect_stdout
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from hashlib import sha256

from nerve_awim.memory_gateway import scientific_interface_validation as s
from nerve_awim.memory_gateway.inference import LocalInferenceAdapter

DIGEST='d'*64
ORIGINAL_MODEL_RESPONSE=LocalInferenceAdapter._model_response


class ScientificInterfaceValidationTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/'run';self.journal=Path(tmp.name)/'claims.sqlite';self.calls=[]
        for name,value in [('metadata',{'model':s.MODEL,'digest':DIGEST}),('preload',{'wall_seconds':.1})]:
            p=patch.object(s,name,return_value=value);setattr(self,name,p.start());self.addCleanup(p.stop)
        p=patch.object(LocalInferenceAdapter,'_model_response',autospec=True,side_effect=self.respond)
        self.transport=p.start();self.addCleanup(p.stop)

    def respond(self,adapter,query,context):
        task=next(t for t in s.tasks.TASKS if query.endswith(s.tasks.TASKS[t]['query']))
        arm='trusted_task' if isinstance(adapter,s.TrustedScientificTaskAdapter) else 'baseline_json'
        self.calls.append((task,arm,query,context))
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            count=db.execute('SELECT COUNT(*) FROM scientific_interface_attempts').fetchone()[0]
            report=json.loads(db.execute('SELECT report FROM scientific_interface_runs').fetchone()[0])
            status=db.execute('SELECT status FROM scientific_interface_attempts ORDER BY ordinal DESC LIMIT 1').fetchone()[0]
        self.assertEqual(count,len(self.calls));self.assertEqual(report['inference_attempts'],count)
        self.assertEqual(status,'claimed')
        return s.tasks.TASKS[task]['expected'],dict(prompt_tokens=80,completion_tokens=9,total_tokens=89)

    def run_study(self):return s.run(self.root,DIGEST,self.journal)

    def test_cli_exit_status_preserves_failure_json(self):
        spec=importlib.util.spec_from_file_location('interface_cli',s.pilot.ROOT/'scripts/run_scientific_interface_validation.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for status,expected in [('complete',0),('failed_consumed',1)]:
            output=io.StringIO()
            with patch.object(sys,'argv',['runner','--directory',str(self.root),'--expected-digest',DIGEST,'--journal',str(self.journal)]),patch.object(module,'run',return_value={'status':status}),redirect_stdout(output):
                self.assertEqual(module.main(),expected)
            self.assertEqual(json.loads(output.getvalue()),{'status':status})

    def test_fixed_pairs_claimed_before_call_and_no_feedback(self):
        report=self.run_study();self.assertEqual(report['status'],'complete',report)
        self.assertEqual([(t,a) for t,a,_,_ in self.calls],s.pairs())
        self.assertEqual(len(self.calls),16);self.assertEqual(self.metadata.call_count,2);self.preload.assert_called_once()
        for task in s.tasks.TASKS:
            pair=[r for r in report['rows'] if r['task_id']==task]
            self.assertEqual(pair[0]['evidence'],pair[1]['evidence'])
        self.assertFalse(report['feedback_learning']);self.assertFalse(report['promotion_authorized'])
        self.assertFalse(report['screen']['passed']);self.assertEqual(report['screen']['next_action'],'retain_baseline')
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM memory_utility').fetchone()[0],0)
        self.assertEqual([r['strict_correct'] for r in report['summary']['arms']],[8,8])

    def test_screen_requires_perfect_candidate_and_strict_improvement(self):
        rows=[]
        for task,arm in s.pairs():
            output=s.tasks.TASKS[task]['expected'] if arm=='trusted_task' else 'ABSTAIN'
            rows.append(dict(task_id=task,arm=arm,score=s.tasks.judge(output,task)))
        result=s.screen(rows)
        self.assertTrue(result['passed']);self.assertEqual(result['next_action'],'candidate_requires_review')
        candidate=next(r for r in rows if r['arm']=='trusted_task' and s.tasks.TASKS[r['task_id']]['expected']=='ABSTAIN')
        candidate['score']=s.tasks.judge('bad',candidate['task_id'])
        self.assertFalse(s.screen(rows)['passed'])
        self.assertTrue(s.screen(rows)['strictly_better_overall'])

    def test_validate_receipt_never_starts_missing_or_incomplete_run(self):
        with self.assertRaises(ValueError):s.validate_receipt(self.root,DIGEST,self.journal)
        self.transport.assert_not_called();self.metadata.assert_not_called()
        self.transport.side_effect=RuntimeError('failed')
        self.run_study()
        with self.assertRaises(ValueError):s.validate_receipt(self.root,DIGEST,self.journal)
        self.assertEqual(self.transport.call_count,1)

    def test_validation_payload_only_system_changes_and_wording_unchanged(self):
        # Real inherited payload generation, mocked HTTP opener rather than model method.
        self.transport.side_effect=None
        with patch.object(LocalInferenceAdapter,'_model_response',ORIGINAL_MODEL_RESPONSE):
            for task_id,task in s.tasks.TASKS.items():
                baseline=s.pilot.StrategyInference('direct');candidate=s.TrustedScientificTaskAdapter(task_id)
                captured=[]
                def reply(request,timeout):
                    captured.append(json.loads(request.data))
                    return io.BytesIO(json.dumps({'model':s.MODEL,'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'ABSTAIN'}}]}).encode())
                for adapter,delegate in [(baseline,baseline._opener),(candidate,candidate._opener.delegate)]:
                    with patch.object(delegate,'open',side_effect=reply):adapter._model_response(task['query'],'UNTRUSTED injected evidence')
                a,b=captured
                self.assertEqual(b['messages'][0]['content'],s._SAFETY+s.tasks.trusted_task(task_id))
                self.assertNotIn('UNTRUSTED',b['messages'][0]['content'])
                b['messages'][0]=a['messages'][0];self.assertEqual(a,b)

    def test_restart_no_network_and_fresh_process(self):
        report=self.run_study()
        with patch.object(s,'metadata',side_effect=AssertionError('no network')),patch.object(s,'preload',side_effect=AssertionError('no network')),patch.object(LocalInferenceAdapter,'_model_response',side_effect=AssertionError('no model')):
            self.assertEqual(s._json(self.run_study()),s._json(report))
        code='''import json,sys
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_interface_validation as s
with patch.object(s,'metadata',side_effect=AssertionError('network')),patch.object(s,'preload',side_effect=AssertionError('network')):
 print(json.dumps(s.run(sys.argv[1],sys.argv[2],sys.argv[3]),sort_keys=True))
'''
        result=subprocess.run([sys.executable,'-c',code,str(self.root),DIGEST,str(self.journal)],capture_output=True,text=True,timeout=20,check=True)
        self.assertEqual(s._json(json.loads(result.stdout)),s._json(report));self.assertEqual(len(self.calls),16)

    def test_failure_and_interrupt_are_consumed(self):
        self.transport.side_effect=RuntimeError('offline')
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.assertEqual(report['inference_attempts'],1)
        with self.assertRaisesRegex(ValueError,'consumed'):self.run_study()
        self.assertEqual(self.transport.call_count,1)

    def test_keyboard_interrupt_cannot_resume(self):
        self.transport.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.run_study()
        with self.assertRaisesRegex(ValueError,'consumed'):self.run_study()
        self.assertEqual(self.transport.call_count,1)

    def test_metadata_drift_invalidates_complete_attempts(self):
        self.metadata.side_effect=[{'model':s.MODEL,'digest':DIGEST},{'model':s.MODEL,'digest':'e'*64}]
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.assertEqual(len(self.calls),16)
        with self.assertRaises(ValueError):self.run_study()

    def test_external_claim_tampered_during_calls_prevents_complete(self):
        original=self.respond
        def tamper(adapter,query,context):
            output=original(adapter,query,context)
            if len(self.calls)==16:
                with sqlite3.connect(self.journal) as db:db.execute("UPDATE local_model_studies SET status='reset'")
            return output
        self.transport.side_effect=tamper
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(len(self.calls),16)
        with self.assertRaisesRegex(ValueError,'external_claim'):self.run_study()

    def test_wrong_model_stops_before_dispatch(self):
        self.metadata.return_value={'model':s.MODEL,'digest':'e'*64}
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.transport.assert_not_called();self.preload.assert_not_called()

    def test_protocol_and_sources_change_rejected_without_calls(self):
        self.run_study();count=len(self.calls)
        with self.assertRaisesRegex(ValueError,'protocol'):s.run(self.root,'e'*64,self.journal)
        with patch.object(s,'sources',return_value={'changed':'source'}):
            with self.assertRaisesRegex(ValueError,'protocol'):self.run_study()
        self.assertEqual(len(self.calls),count)

    def test_source_change_during_execution_stops_consumed(self):
        original=s.sources();calls=0
        def pins():
            nonlocal calls
            calls+=1
            return original if calls<=2 else {'changed':'source'}
        with patch.object(s,'sources',side_effect=pins):report=self.run_study()
        self.assertEqual(report['status'],'failed_consumed');self.assertEqual(len(self.calls),1)

    def test_new_directory_cannot_replay_claimed_dataset(self):
        self.run_study()
        with self.assertRaisesRegex(ValueError,'consumed'):s.run(self.root.parent/'other',DIGEST,self.journal)
        self.assertEqual(len(self.calls),16)

    def mutate_report(self,fn):
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            report=json.loads(db.execute('SELECT report FROM scientific_interface_runs').fetchone()[0]);fn(report)
            encoded=s._json(report)
            db.execute('UPDATE scientific_interface_runs SET report=?,digest=?',(encoded,sha256(encoded.encode()).hexdigest()))

    def test_raw_score_tampering_even_with_rehashed_receipt_rejected(self):
        self.run_study();self.mutate_report(lambda r:r['rows'][0]['score'].update(strict_correct=1))
        with self.assertRaises(ValueError):self.run_study()
        self.assertEqual(len(self.calls),16)

    def test_claim_corruption_rejected(self):
        self.run_study()
        with sqlite3.connect(self.root/'memory.sqlite') as db:db.execute("UPDATE scientific_interface_attempts SET status='claimed' WHERE ordinal=0")
        with self.assertRaisesRegex(ValueError,'claims'):self.run_study()
        self.assertEqual(len(self.calls),16)

    def test_partial_local_claim_and_external_claim_change_fail_closed(self):
        self.run_study()
        with sqlite3.connect(self.root/'memory.sqlite') as db:db.execute('UPDATE scientific_interface_runs SET report=NULL,digest=NULL')
        with self.assertRaisesRegex(ValueError,'consumed'):self.run_study()
        with sqlite3.connect(self.journal) as db:db.execute("UPDATE local_model_studies SET status='reset'")
        with self.assertRaisesRegex(ValueError,'external_claim'):self.run_study()
        self.assertEqual(len(self.calls),16)


if __name__=='__main__':unittest.main()
