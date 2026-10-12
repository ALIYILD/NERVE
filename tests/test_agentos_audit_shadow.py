import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim import agentos_audit_evidence as oracle

spec=importlib.util.spec_from_file_location('audit_shadow_tests',Path(__file__).resolve().parents[1]/'scripts/agentos_audit_shadow.py')
shadow=importlib.util.module_from_spec(spec)
spec.loader.exec_module(shadow)


class AuditShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.host=AgentOSLearning(Path(self.tmp.name)/'state')
        self.calls=0

    def seed(self):
        def fake(host,profile,prompt,*,max_tokens,inspect=False):
            if inspect:
                return dict(ok=True,requested_model='model:free')
            host.reserve_calls('hermes-free',1,daily_limit=20)
            payload=json.loads(prompt.split('\n')[-1])
            if type(payload) is list:
                value={'lesson':'Use source evidence.'}
            else:
                value={r['id']:oracle.expected_decision(r['bundle']) for r in payload['tasks']}
                if payload['advice'] is None:
                    for answer in value.values():
                        answer['decision']='contradicted' if answer['decision']=='supported' else 'supported'
            return dict(ok=True,requested_model='model:free',tools=0,max_tokens=4096,max_iterations=2,timeout_seconds=90,value=value)
        result=shadow.studies.study(self.host,fake)
        self.assertEqual(result['status'],'shadow_accepted')
        return result['study_id']

    def task(self):
        return dict(id='new-task',family='new-family',bundle=dict(schema=oracle.SCHEMA,simulated=True,
                    claim=dict(kind='catalog_listed',model='m',provider='p',at=100,max_age=10),
                    sources=[dict(id='s'+str(i),kind='catalog',model='m',provider='p',observed_at=100,derived_from=[],fields=dict(listed=True)) for i in range(7)]))

    def native(self,loss=False,crash=False):
        def fake(host,profile,prompt,*,max_tokens,inspect=False):
            if inspect:
                return dict(ok=True,requested_model='model:free')
            host.reserve_calls('hermes-free',1,daily_limit=20); self.calls+=1
            if crash:
                raise RuntimeError('fake crash')
            payload=json.loads(prompt.split('\n')[-1])
            value=oracle.expected_decision(payload['task']['bundle'])
            if loss and payload['advice']:
                value=dict(decision='unknown',citations=[])
            return dict(ok=True,requested_model='model:free',tools=0,max_tokens=4096,max_iterations=2,timeout_seconds=90,value=value)
        return fake

    def test_no_candidate_does_not_call_native(self):
        self.assertEqual(shadow.monitor(self.host,self.native(),self.task())['status'],'no_candidate')
        self.assertEqual(self.calls,0)
        self.assertEqual(shadow.status(self.host)['status'],'no_candidate')

    def test_pair_is_scoped_shadow_only_and_evidence_cannot_be_renamed(self):
        self.seed()
        result=shadow.monitor(self.host,self.native(),self.task())
        self.assertEqual(result['status'],'active')
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(shadow.studies.remaining(self.host),10)
        renamed=self.task(); renamed['id']='renamed'; renamed['family']='renamed'
        self.assertEqual(shadow.monitor(self.host,self.native(),renamed)['status'],'reused_evidence')
        self.assertEqual(self.calls,2)
        with sqlite3.connect(shadow.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],2)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM episodes')

    def test_loss_revokes_and_blocks_further_calls(self):
        self.seed()
        result=shadow.monitor(self.host,self.native(loss=True),self.task())
        self.assertEqual(result['status'],'revoked'); self.assertTrue(result['paired_loss'])
        self.assertEqual(shadow.monitor(self.host,self.native(),self.task())['status'],'revoked')
        self.assertEqual(self.calls,2)

    def test_supported_labels_with_bad_citations_revoke_even_without_paired_loss(self):
        self.seed()
        good=self.native()
        def native(*args,**kwargs):
            receipt=good(*args,**kwargs)
            if not kwargs.get('inspect'):
                receipt['value']['citations']=[]
            return receipt
        result=shadow.monitor(self.host,native,self.task())
        self.assertEqual(result['status'],'revoked')
        self.assertTrue(result['unsupported_positive'])
        self.assertFalse(result['paired_loss'])
        self.assertFalse(result['baseline_passed'])
        self.assertFalse(result['lesson_passed'])

    def test_budget_deferred_without_reserving_evidence(self):
        self.seed(); self.host.reserve_calls('hermes-free',11,daily_limit=20)
        result=shadow.monitor(self.host,self.native(),self.task())
        self.assertEqual(result['status'],'deferred_daily_budget')
        self.assertEqual(self.calls,0)
        with sqlite3.connect(shadow.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM episodes').fetchone()[0],0)

    def test_snapshot_tamper_blocks_candidate_without_call(self):
        sid=self.seed()
        (self.host.directory/'audit-study-snapshots'/sid/'oracle.py').write_text('changed')
        self.assertEqual(shadow.monitor(self.host,self.native(),self.task())['status'],'no_candidate')
        self.assertEqual(self.calls,0)

    def test_crash_consumes_identity_revokes_and_no_replay(self):
        self.seed()
        self.assertEqual(shadow.monitor(self.host,self.native(crash=True),self.task())['status'],'revoked')
        self.assertEqual(shadow.monitor(self.host,self.native(),self.task())['status'],'revoked')
        self.assertEqual(shadow.studies.remaining(self.host),10)
        self.assertEqual(self.calls,1)

    def test_thirty_day_expiry(self):
        sid=self.seed()
        with sqlite3.connect(self.host.directory/'audit-study.sqlite3') as db:
            db.execute('UPDATE studies SET created=? WHERE id=?',(int(shadow.time.time())-shadow.LIFETIME,sid))
        self.assertEqual(shadow.monitor(self.host,self.native(),self.task())['status'],'expired')
        self.assertEqual(self.calls,0)

    def test_lesson_mutation_cannot_import_untested_advice(self):
        sid=self.seed()
        self.assertEqual(shadow.status(self.host)['status'],'eligible_unmonitored')
        with sqlite3.connect(self.host.directory/'audit-study.sqlite3') as db:
            db.execute('UPDATE studies SET lesson=? WHERE id=?',('Untested replacement',sid))
        self.assertEqual(shadow.monitor(self.host,self.native(),self.task())['status'],'no_candidate')
        self.assertEqual(self.calls,0)

    def test_model_mutation_cannot_reuse_another_models_evidence(self):
        sid=self.seed()
        with sqlite3.connect(self.host.directory/'audit-study.sqlite3') as db:
            db.execute('UPDATE studies SET model=? WHERE id=?',('other-model:free',sid))
        self.assertEqual(shadow.monitor(self.host,self.native(),self.task())['status'],'no_candidate')
        self.assertEqual(self.calls,0)

    def test_active_status_rechecks_candidate_binding(self):
        sid=self.seed()
        self.assertEqual(shadow.monitor(self.host,self.native(),self.task())['status'],'active')
        with sqlite3.connect(self.host.directory/'audit-study.sqlite3') as db:
            db.execute('UPDATE studies SET lesson=? WHERE id=?',('Untested replacement',sid))
        self.assertEqual(shadow.status(self.host)['status'],'ineligible')

    def test_failed_call_keeps_request_before_response_exists(self):
        self.seed()
        shadow.monitor(self.host,self.native(crash=True),self.task())
        with sqlite3.connect(shadow.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],0)

    def test_benchmark_task_cannot_be_monitored_as_fresh(self):
        self.seed()
        old=shadow.cohort.cohort()['splits']['final'][0]
        task={key:old[key] for key in ('id','family','bundle')}
        self.assertEqual(shadow.monitor(self.host,self.native(),task)['status'],'reused_evidence')
        self.assertEqual(self.calls,0)


if __name__=='__main__':
    unittest.main()
