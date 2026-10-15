"""Mock transport with real scoped evidence and durable claims; no model calls."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_candidate_format_study as s

DIGEST='d'*64


class CandidateFormatStudyTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)/'study';self.journal=Path(tmp.name)/'claims.sqlite';self.calls=[]
        for name,value in [('metadata',{'model':s.pilot.MODEL,'digest':DIGEST}),('preload',{'elapsed_seconds':.1}),('runtime_version','0.9.1')]:
            p=patch.object(s,name,return_value=value);setattr(self,name,p.start());self.addCleanup(p.stop)
        p=patch.object(s.transport,'run',side_effect=self.respond);self.transport=p.start();self.addCleanup(p.stop)

    def respond(self,config,query,evidence,*,authorize,constrained):
        authorize();task_id=next(k for k,v in s.tasks().items() if v['query']==query)
        self.calls.append((task_id,constrained))
        with sqlite3.connect(self.root/'claim.sqlite') as db:
            report=json.loads(db.execute('SELECT report FROM study').fetchone()[0])
            claims=db.execute('SELECT ordinal,status FROM calls ORDER BY ordinal').fetchall()
        self.assertEqual(report['model_attempts'],len(self.calls));self.assertEqual(claims[-1],(len(self.calls)-1,'claimed'))
        self.assertNotIn('expected',evidence[0]);self.assertNotIn('stratum',evidence[0])
        p=s.execution.prepare(config,query,evidence)
        authorize()
        return dict(raw_output=s.canonical(s.tasks()[task_id]['expected']) if constrained else 'unformatted response',
            route='model',model_calls=1,usage=dict(prompt_tokens=80,completion_tokens=12,total_tokens=92),
            model=s.pilot.MODEL,origin=s.pilot.ORIGIN,constrained=constrained,review_required=True,synthetic_only=True,
            model_weights_trained=False,**{k:p[k] for k in ('config_sha256','input_sha256','evidence_ids','scanned_current_ids')})

    def run_study(self):return s.run(self.root,DIGEST,self.journal)

    def test_four_counterbalanced_claimed_calls_raw_scores_and_no_promotion(self):
        report=self.run_study();self.assertEqual(report['status'],'complete',report)
        self.assertEqual(self.calls,list(s.PAIRS));self.assertEqual(self.calls[0],('supported',True))
        self.assertEqual(self.metadata.call_count,2);self.assertEqual(self.runtime_version.call_count,2);self.preload.assert_called_once()
        self.assertEqual([r['strict_correct'] for r in report['summary']['arms']],[0,2])
        self.assertFalse(report['efficacy_established']);self.assertEqual(report['rejection_receipts_created'],0)
        self.assertNotEqual(report['protocol']['arm_config_sha256']['True'],report['protocol']['arm_config_sha256']['False'])
        for task in s.tasks():
            pair=[r['response'] for r in report['rows'] if r['task_id']==task]
            for key in ('config_sha256','input_sha256','evidence_ids'):self.assertEqual(pair[0][key],pair[1][key])

    def test_terminal_restart_fresh_process_no_network_and_stable_file(self):
        report=self.run_study();path=self.root/'report.json';before=path.read_bytes();mtime=path.stat().st_mtime_ns
        with patch.object(s.transport,'run',side_effect=AssertionError('no dispatch')),patch.object(s,'metadata',side_effect=AssertionError('no metadata')):
            self.assertEqual(s.canonical(s.validate_receipt(self.root,DIGEST,self.journal)),s.canonical(report))
        self.assertEqual(before,path.read_bytes());self.assertEqual(mtime,path.stat().st_mtime_ns)
        code='''import json,sys
from unittest.mock import patch
from nerve_awim.memory_gateway import scientific_candidate_format_study as s
with patch.object(s.transport,'run',side_effect=AssertionError('no model')),patch.object(s,'metadata',side_effect=AssertionError('no metadata')):
 print(json.dumps(s.validate_receipt(sys.argv[1],sys.argv[2],sys.argv[3]),sort_keys=True))
'''
        process=subprocess.run([sys.executable,'-c',code,str(self.root),DIGEST,str(self.journal)],check=True,capture_output=True,text=True,timeout=20)
        self.assertEqual(s.canonical(json.loads(process.stdout)),s.canonical(report))

    def test_partial_failure_consumes_remaining_and_failed_resume_checks_rows(self):
        original=self.respond
        def fail(*args,**kwargs):
            if self.calls:raise RuntimeError('transport failed')
            return original(*args,**kwargs)
        self.transport.side_effect=fail
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.assertEqual(report['model_attempts'],2)
        self.assertEqual(len(report['rows']),1)
        self.assertEqual(s.canonical(self.run_study()),s.canonical(report));self.assertEqual(self.transport.call_count,2)
        self.mutate(lambda r:r['rows'][0]['score'].update(strict_correct=False))
        with self.assertRaises(ValueError):s.validate_receipt(self.root,DIGEST,self.journal)

    def test_transport_failure_preserves_only_bounded_reason_and_detail(self):
        self.transport.side_effect=s.transport.InferenceUnavailable('invalid_response','output_limit')
        report=self.run_study()
        self.assertEqual(report['failure_reason'],'invalid_response')
        self.assertEqual(report['failure_detail'],'output_limit')
        self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(s.canonical(s.validate_receipt(self.root,DIGEST,self.journal)),s.canonical(report))

    def test_interrupt_consumed_no_retries(self):
        self.transport.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.run_study()
        report=s.validate_receipt(self.root,DIGEST,self.journal)
        self.assertEqual(report['status'],'failed_consumed');self.assertEqual(self.transport.call_count,1)

    def mutate(self,fn):
        with sqlite3.connect(self.root/'claim.sqlite') as db:
            report=json.loads(db.execute('SELECT report FROM study').fetchone()[0]);fn(report);encoded=s.canonical(report)
            db.execute('UPDATE study SET report=?,digest=?',(encoded,sha256(encoded.encode()).hexdigest()))

    def test_null_or_missing_local_claim_never_dispatches(self):
        with self.assertRaises(ValueError):s.validate_receipt(self.root,DIGEST,self.journal)
        self.transport.assert_not_called();self.run_study()
        with sqlite3.connect(self.root/'claim.sqlite') as db:db.execute('UPDATE study SET report=NULL,digest=NULL')
        with self.assertRaisesRegex(ValueError,'consumed'):self.run_study()
        self.assertEqual(self.transport.call_count,4)

    def test_external_anti_replay_and_claim_tamper(self):
        self.run_study()
        with self.assertRaises((ValueError,sqlite3.IntegrityError)):s.run(self.root.parent/'other',DIGEST,self.journal)
        with sqlite3.connect(self.journal) as db:db.execute("UPDATE format_claims SET status='reset'")
        with self.assertRaises(ValueError):s.validate_receipt(self.root,DIGEST,self.journal)
        self.assertEqual(self.transport.call_count,4)

    def test_wrong_digest_blocks_and_runtime_drift_invalidates(self):
        self.metadata.return_value={'model':s.pilot.MODEL,'digest':'e'*64}
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.transport.assert_not_called()

    def test_post_metadata_or_version_drift_is_failed_not_complete(self):
        self.runtime_version.side_effect=['0.9.1','0.9.2']
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.assertEqual(len(report['rows']),4)
        self.assertEqual(s.canonical(self.run_study()),s.canonical(report))

    def test_changed_sources_protocol_or_attempt_journal_refused(self):
        self.run_study()
        with patch.object(s,'sources',return_value={'changed':'source'}):
            with self.assertRaises(ValueError):s.validate_receipt(self.root,DIGEST,self.journal)
        with sqlite3.connect(self.root/'claim.sqlite') as db:db.execute("UPDATE calls SET status='claimed' WHERE ordinal=0")
        with self.assertRaises(ValueError):self.run_study()

    def test_auth_failure_during_callback_consumes_attempt(self):
        def denied(*args,**kwargs):raise PermissionError('revoked')
        self.transport.side_effect=denied
        report=self.run_study();self.assertEqual(report['status'],'failed_consumed');self.assertEqual(report['model_attempts'],1)
        self.assertEqual(report['failure'],'PermissionError')

    def test_unknown_answers_separate_shape_format_and_exact(self):
        task='unit_mismatch';wrong=dict(s.tasks()['supported']['expected'])
        self.assertEqual(s.score(s.canonical(wrong),task),dict(schema_valid=True,format_valid=True,strict_correct=False))
        wrong['status']='abstain'
        self.assertEqual(s.score(s.canonical(wrong),task),dict(schema_valid=True,format_valid=False,strict_correct=False))
        self.assertEqual(s.score('ABSTAIN',task),dict(schema_valid=False,format_valid=False,strict_correct=False))


if __name__=='__main__':unittest.main()
