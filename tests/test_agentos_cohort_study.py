import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim import agentos_audit_evidence as oracle
from nerve_awim import agentos_audit_cohort as legacy

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import agentos_cohort_registry as registry
import agentos_cohort_study as runner


def fixture(host):
    # Test-only structural variations; never admitted to the live host registry.
    data=copy.deepcopy(legacy.cohort()); data['id']='test-cohort'
    for rows in data['splits'].values():
        for row in rows:
            row['family']='test-'+row['family']
            row['bundle']['sources'].append(dict(id='test-extra',kind='assertion',model='simulated/target:free',provider='simulated-provider',observed_at=1000,derived_from=[],fields={'text':'Synthetic test distractor'}))
    review=dict(manifest_sha256=registry.digest(data),reviewer='unit-test',method='test-only',checks=dict(gold=True,novelty=True,split_separation=True))
    return registry.admit(host,data,review)


class CohortStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.host=AgentOSLearning(Path(self.tmp.name)/'state')
        self.entry=fixture(self.host); self.prompts=[]

    def fake(self):
        def native(host,profile,prompt,*,max_tokens,inspect=False):
            if inspect:
                return dict(ok=True,requested_model='test:free')
            host.reserve_calls('hermes-free',1,daily_limit=20)
            self.prompts.append(prompt); payload=json.loads(prompt.split('\n')[-1])
            if type(payload) is list:
                value={'lesson':'Check source identity and independent provenance.'}
            else:
                value={r['id']:oracle.expected_decision(r['bundle']) for r in payload['tasks']}
                if payload['advice'] is None:
                    for answer in value.values():
                        answer['decision']='contradicted' if answer['decision']=='supported' else 'supported'
            return dict(ok=True,requested_model='test:free',tools=0,max_tokens=max_tokens,max_iterations=2,timeout_seconds=90,value=value)
        return native

    def test_receipt_verified_export_and_no_replay(self):
        result=runner.run(self.host,self.fake(),self.entry)
        self.assertEqual(result['status'],'shadow_accepted')
        verified=runner.candidate(self.host,result['study_id'])
        self.assertFalse(verified['activation_authorized'])
        self.assertEqual(verified['lesson'],'Check source identity and independent provenance.')
        self.assertTrue(runner.consumed(self.host,self.entry['id']))
        self.assertEqual(runner.run(self.host,self.fake(),self.entry)['status'],'no_fresh_tasks')
        self.assertEqual(runner.remaining(self.host),12)

    def test_untrusted_entry_payload_is_not_used(self):
        supplied=dict(self.entry,data={'tampered':True},profile='paid-profile')
        result=runner.run(self.host,self.fake(),supplied)
        self.assertEqual(result['status'],'shadow_accepted')
        self.assertEqual(result['profile'],'qa-release')

    def test_budget_queue_binds_runner_before_retry(self):
        self.host.reserve_calls('hermes-free',20,daily_limit=20)
        result=runner.run(self.host,self.fake(),self.entry)
        self.assertEqual(result['status'],'queued_budget')
        self.assertFalse(runner.consumed(self.host,self.entry['id']))
        with patch.object(runner,'current_revision',return_value='changed'):
            self.assertEqual(runner.run(self.host,self.fake(),self.entry)['status'],'queued_revision_mismatch')
        self.assertEqual(self.prompts,[])

    def test_snapshot_tampering_blocks_candidate(self):
        result=runner.run(self.host,self.fake(),self.entry)
        (self.host.directory/'cohort-study-snapshots'/result['study_id']/'runner.py').write_text('changed')
        with self.assertRaises(ValueError):
            runner.candidate(self.host,result['study_id'])

    def test_result_and_lesson_tampering_block_candidates(self):
        result=runner.run(self.host,self.fake(),self.entry)
        with sqlite3.connect(runner.database(self.host)) as db:
            db.execute("UPDATE studies SET lesson='forged'")
        with self.assertRaises(ValueError):
            runner.candidate(self.host,result['study_id'])

    def test_native_exception_records_request_and_consumes_evidence(self):
        def broken(host,profile,prompt,*,max_tokens,inspect=False):
            if inspect:
                return dict(ok=True,requested_model='test:free')
            host.reserve_calls('hermes-free',1,daily_limit=20)
            raise RuntimeError('test failure')
        result=runner.run(self.host,broken,self.entry)
        self.assertEqual(result['status'],'failed')
        with sqlite3.connect(runner.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],0)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM requests')
        self.assertTrue(runner.consumed(self.host,self.entry['id']))

    def test_wrong_citations_for_supported_answer_reject(self):
        good=self.fake()
        def native(*a,**kw):
            receipt=good(*a,**kw)
            if not kw.get('inspect'):
                for answer in receipt['value'].values():
                    if isinstance(answer,dict) and answer.get('decision')=='supported':
                        answer['citations']=[]
            return receipt
        self.assertEqual(runner.run(self.host,native,self.entry)['status'],'rejected')

    def test_snapshot_boolean_integer_confusion_rejected(self):
        result=runner.run(self.host,self.fake(),self.entry)
        snapshot=self.host.directory/'cohort-study-snapshots'/result['study_id']/'cohort.json'
        data=json.loads(snapshot.read_text())
        source=data['splits']['train'][0]['bundle']['sources'][0]
        source['fields']['present']=1
        snapshot.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            runner.candidate(self.host,result['study_id'])

    def test_invalid_candidate_path_rejected_before_io(self):
        with self.assertRaises(ValueError):
            runner.candidate(self.host,'../../outside')

    def test_recover_fails_running_without_replaying(self):
        result=runner.run(self.host,self.fake(),self.entry)
        with sqlite3.connect(runner.database(self.host)) as db:
            db.execute("UPDATE studies SET status='running'")
        self.assertEqual(runner.recover(self.host),1)
        self.assertEqual(runner.recover(self.host),0)
        self.assertTrue(runner.consumed(self.host,self.entry['id']))
        self.assertEqual(runner.status(self.host)['status'],'failed')
        self.assertEqual(runner.run(self.host,self.fake(),self.entry)['status'],'no_fresh_tasks')

    def test_existing_pending_legacy_study_untouched(self):
        pending=self.host.directory/'pending-audit-study.json'; pending.write_text('{"preserve":"exact"}')
        runner.run(self.host,self.fake(),self.entry)
        self.assertEqual(pending.read_text(),'{"preserve":"exact"}')


if __name__=='__main__':
    unittest.main()
