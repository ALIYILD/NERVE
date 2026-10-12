import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim import agentos_audit_evidence as oracle

spec=importlib.util.spec_from_file_location('audit_study_tests',Path(__file__).resolve().parents[1]/'scripts/agentos_audit_study.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PairedAuditStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.host=AgentOSLearning(Path(self.tmp.name)/'state')
        self.prompts=[]

    def fake(self,gain=False,drift=False):
        def native(host,profile,prompt,*,max_tokens,inspect=False):
            if inspect:
                return dict(ok=True,requested_model='fixed-model:free')
            host.reserve_calls('hermes-free',1,daily_limit=20)
            self.prompts.append(prompt)
            payload=json.loads(prompt.split('\n')[-1])
            if type(payload) is list:
                value=dict(lesson='Require evidence from the exact source and request.')
            else:
                value={row['id']:oracle.expected_decision(row['bundle']) for row in payload['tasks']}
                if gain and payload['advice'] is None:
                    for answer in value.values():
                        answer['decision']='contradicted' if answer['decision']=='supported' else 'supported'
            return dict(ok=True,requested_model='drifted' if drift else 'fixed-model:free',tools=0,max_tokens=max_tokens,max_iterations=2,timeout_seconds=90,value=value)
        return native

    def test_gain_is_shadow_only_and_training_feedback_excludes_holdouts(self):
        result=runner.study(self.host,self.fake(gain=True))
        self.assertEqual(result['status'],'shadow_accepted')
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(result['native_sessions'],8)
        self.assertEqual(runner.remaining(self.host),12)
        proposal=self.prompts[1]
        groups=runner.cohort.cohort()['splits']
        for phase in ('selection','retention','final'):
            for row in groups[phase]:
                self.assertNotIn(row['id'],proposal)
        with sqlite3.connect(runner.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT SUM(used) FROM slots').fetchone()[0],8)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],8)
            self.assertTrue(db.execute('SELECT lesson FROM studies').fetchone()[0])

    def test_tie_preserves_final_and_prepayment_is_not_refunded(self):
        result=runner.study(self.host,self.fake())
        self.assertEqual(result['status'],'no_gain')
        self.assertEqual(set(result['phases']),{'selection'})
        self.assertEqual(result['native_sessions'],4)
        self.assertEqual(runner.remaining(self.host),12)
        self.assertEqual(runner.study(self.host,self.fake())['status'],'no_fresh_tasks')
        self.assertEqual(runner.remaining(self.host),12)

    def test_budget_queue_never_calls_native_even_inspection(self):
        self.host.reserve_calls('hermes-free',20,daily_limit=20)
        def no_calls(*a,**kw):
            self.fail('budget queue invoked native')
        for _ in range(2):
            result=runner.study(self.host,no_calls)
            self.assertEqual(result['status'],'queued_budget')
        queued=json.loads((self.host.directory/'pending-audit-study.json').read_text())
        self.assertEqual(queued['required_sessions'],8)
        self.assertEqual(queued['remaining_sessions'],0)
        self.assertEqual(runner.status(self.host)['status'],'not_run')
        with sqlite3.connect(runner.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0],0)

    def test_drift_fails_durably_and_evidence_cannot_replay(self):
        result=runner.study(self.host,self.fake(drift=True))
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['native_sessions'],1)
        self.assertEqual(runner.status(self.host)['status'],'failed')
        self.assertEqual(runner.study(self.host,self.fake())['status'],'no_fresh_tasks')

    def test_double_prepaid_consumption_is_rejected(self):
        def native(host,profile,prompt,*,max_tokens,inspect=False):
            if inspect:
                return dict(ok=True,requested_model='fixed-model:free')
            host.reserve_calls('hermes-free',1,daily_limit=20)
            host.reserve_calls('hermes-free',1,daily_limit=20)
        result=runner.study(self.host,native)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(runner.remaining(self.host),12)
        with sqlite3.connect(runner.database(self.host)) as db:
            self.assertEqual(db.execute('SELECT SUM(used) FROM slots').fetchone()[0],1)

    def test_exception_after_reservation_and_interrupted_recovery_do_not_replay(self):
        def native(host,profile,prompt,*,max_tokens,inspect=False):
            if inspect:
                return dict(ok=True,requested_model='fixed-model:free')
            host.reserve_calls('hermes-free',1,daily_limit=20)
            raise RuntimeError('simulated native failure')
        self.assertEqual(runner.study(self.host,native)['status'],'failed')
        with sqlite3.connect(runner.database(self.host)) as db:
            db.execute("UPDATE studies SET status='running'")
        self.assertEqual(runner.status(self.host)['status'],'running')
        self.assertEqual(runner.study(self.host,self.fake())['status'],'no_fresh_tasks')
        self.assertEqual(runner.status(self.host)['status'],'failed')
        self.assertEqual(runner.remaining(self.host),12)

    def test_queue_binds_manifest_and_revision_before_retry(self):
        self.host.reserve_calls('hermes-free',20,daily_limit=20)
        runner.study(self.host,self.fake())
        pending=self.host.directory/'pending-audit-study.json'
        queued=json.loads(pending.read_text())
        self.assertIn('manifest_sha256',queued)
        self.assertIn('revision',queued)
        queued['revision']='changed'
        pending.write_text(json.dumps(queued))
        result=runner.study(self.host,self.fake())
        self.assertEqual(result['status'],'queued_revision_mismatch')
        self.assertEqual(self.prompts,[])

    def test_snapshots_precede_inspection_and_paid_model_rejected(self):
        def native(host,profile,prompt,*,max_tokens,inspect=False):
            self.assertTrue(inspect)
            folders=list((host.directory/'audit-study-snapshots').iterdir())
            self.assertEqual(len(folders),1)
            self.assertEqual({p.name for p in folders[0].iterdir()},{'cohort.json','scope.json','oracle.py','cohort.py','runner.py'})
            return dict(ok=True,requested_model='paid-model')
        result=runner.study(self.host,native)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['native_sessions'],0)

    def test_boolean_tools_metadata_rejected(self):
        good=self.fake()
        def native(*args,**kwargs):
            receipt=good(*args,**kwargs)
            if not kwargs.get('inspect'):
                receipt['tools']=False
            return receipt
        self.assertEqual(runner.study(self.host,native)['status'],'failed')

    def test_midnight_rollover_blocks_next_inference(self):
        good=self.fake()
        with patch.object(runner.time,'strftime',return_value='2026-10-12') as day:
            def native(*args,**kwargs):
                receipt=good(*args,**kwargs)
                if kwargs.get('inspect'):
                    day.return_value='2026-10-13'
                return receipt
            result=runner.study(self.host,native)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['native_sessions'],0)
        self.assertEqual(self.prompts,[])

    def test_missing_native_reservation_fails_instead_of_bypassing_budget(self):
        def native(host,profile,prompt,*,max_tokens,inspect=False):
            if inspect:
                return dict(ok=True,requested_model='fixed-model:free')
            return dict(ok=True,requested_model='fixed-model:free',tools=0,max_tokens=4096,max_iterations=2,timeout_seconds=90,value={})
        self.assertEqual(runner.study(self.host,native)['status'],'failed')


if __name__=='__main__':
    unittest.main()
