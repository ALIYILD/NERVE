import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import scientific_structured_preflight as s


VERSION_FUNCTION=s.runtime_version


class StructuredPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'run';self.journal=Path(self.tmp.name)/'claims.sqlite'
        self.digest='a'*64;self.count=0
        self.meta=patch.object(s,'metadata',return_value={'model':s.MODEL,'digest':self.digest}).start()
        self.version=patch.object(s,'runtime_version',return_value='0.13.0').start()
        self.preload=patch.object(s,'preload',return_value={'wall_seconds':0.1}).start()
        outer=self
        def response(adapter,query,context):
            with sqlite3.connect(outer.root/'memory.sqlite') as db:
                claims=db.execute('select ordinal,status from scientific_interface_attempts order by ordinal').fetchall()
            outer.assertEqual(claims[-1],(outer.count,'claimed'));outer.count+=1
            task=s.tasks._task(adapter.task_id)
            outer.assertEqual(query,task['query'])
            for fact in task['evidence']:outer.assertIn(fact['content'],context)
            return json.dumps(task['expected']),{'prompt_tokens':50,'completion_tokens':30,'total_tokens':80}
        self.call=patch.object(s.StructuredScientificInference,'_model_response',autospec=True,side_effect=response).start()
        self.addCleanup(patch.stopall)

    def run_probe(self):return s.run(self.root,self.digest,self.journal)

    def test_fixed_calls_claimed_real_scopes_scores_no_feedback(self):
        report=self.run_probe();self.assertEqual(report['status'],'complete');self.assertEqual(self.call.call_count,4)
        self.assertEqual(self.meta.call_count,2);self.assertEqual(self.version.call_count,2);self.preload.assert_called_once()
        self.assertFalse(report['improvement_established']);self.assertFalse(report['promotion_authorized'])
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            self.assertEqual(db.execute('select count(*) from memory_utility').fetchone()[0],0)
        for arm in report['summary']['arms']:
            self.assertEqual(arm['strict_correct'],2);self.assertEqual(arm['schema_valid'],2)

    def test_resume_no_calls_and_same_claims(self):
        original=self.run_probe()
        self.meta.reset_mock();self.version.reset_mock();self.preload.reset_mock();self.call.reset_mock()
        self.assertEqual(self.run_probe(),original)
        for mock in (self.meta,self.version,self.preload,self.call):mock.assert_not_called()

    def test_claim_prevents_new_directory_replay(self):
        self.run_probe();self.root=self.root.parent/'different'
        with self.assertRaises(ValueError):self.run_probe()
        self.assertEqual(self.call.call_count,4)

    def test_version_drift_invalidates(self):
        self.version.side_effect=['0.13.0','0.13.1']
        self.assertEqual(self.run_probe()['status'],'failed_consumed')
        with self.assertRaises(ValueError):self.run_probe()
        self.assertEqual(self.call.call_count,4)

    def test_wrong_model_no_inference(self):
        self.meta.return_value={'model':s.MODEL,'digest':'b'*64}
        self.assertEqual(self.run_probe()['status'],'failed_consumed');self.call.assert_not_called()
        self.preload.assert_not_called()

    def test_failure_and_interrupt_never_retry(self):
        self.call.side_effect=KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):self.run_probe()
        with self.assertRaises(ValueError):self.run_probe()
        self.assertEqual(self.call.call_count,1)

    def test_format_success_not_factual_success(self):
        bad={'status':'answer','entity':'Buckeye','measurement':'mass','value':'29.2','unit':'mg','source_id':'structured-c'}
        self.call.side_effect=lambda *args:(json.dumps(bad),{'prompt_tokens':50,'completion_tokens':30,'total_tokens':80})
        report=self.run_probe();self.assertEqual(report['status'],'complete')
        for row in report['rows']:
            self.assertTrue(row['score']['schema_valid']);self.assertFalse(row['score']['strict_correct'])
        self.assertEqual(sum(r['score']['unsupported_selection'] for r in report['rows']),2)
        self.assertFalse(report['improvement_established'])

    def test_corrupt_score_even_rehashed_is_rejected(self):
        self.run_probe()
        with sqlite3.connect(self.root/'memory.sqlite') as db:
            report=json.loads(db.execute('select report from scientific_interface_runs').fetchone()[0]);report['rows'][0]['score']['strict_correct']=False
            raw=s._json(report);db.execute('update scientific_interface_runs set report=?,digest=?',(raw,s.sha256(raw.encode()).hexdigest()))
        with self.assertRaises(ValueError):self.run_probe()
        self.assertEqual(self.call.call_count,4)

    def test_final_shared_claim_check(self):
        def metadata():
            if self.count==4:
                with sqlite3.connect(self.journal) as db:db.execute("update local_model_studies set status='tampered'")
            return {'model':s.MODEL,'digest':self.digest}
        self.meta.side_effect=metadata
        self.assertEqual(self.run_probe()['status'],'failed_consumed')

    def test_source_change_stops_before_calls(self):
        pins=s.sources();changed=dict(pins,extra='changed')
        with patch.object(s,'sources',side_effect=[pins,changed,changed]):
            self.assertEqual(self.run_probe()['status'],'failed_consumed')
        self.call.assert_not_called()

    def test_transport_failure_keeps_sanitized_reason_and_no_retry(self):
        self.call.side_effect=s.InferenceUnavailable('timeout')
        report=self.run_probe()
        self.assertEqual(report['status'],'failed_consumed')
        self.assertEqual(report['failure_reason'],'timeout')
        self.assertIsNone(report['failure_detail'])
        self.assertEqual(self.call.call_count,1)
        with self.assertRaises(ValueError):self.run_probe()

    def test_version_response_bounded_and_typed(self):
        import io
        with patch.object(s,'build_opener') as opener:
            for raw in (b' '*4097,b'{"version":true}',b'{"version":"bad version"}'):
                opener.return_value.open.return_value=io.BytesIO(raw)
                with self.assertRaises(ValueError):VERSION_FUNCTION()
            opener.return_value.open.return_value=io.BytesIO(b'{"version":"0.13.0"}')
            self.assertEqual(VERSION_FUNCTION(),'0.13.0')



if __name__=='__main__':unittest.main()
