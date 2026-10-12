"""Trusted fake adapters exercise durable queues; no live inference/evidence."""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim.cue_engine import ModelProfile
from nerve_awim.cue_evaluation import ModelParity
from nerve_awim.cue_cycle import DiscoveryReceipt
from nerve_awim.cue_host import CueHost

_spec = importlib.util.spec_from_file_location('cue_jobs_test', Path(__file__).resolve().parents[1]/'scripts/agentos_cue_jobs.py')
jobs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jobs)


class CueJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.host = AgentOSLearning(Path(self.temp.name)/'state')
        self.profile = ModelProfile('fixture','model','revision-1','tok','tok-1',('instruction',),'template-1')
        self.configure()
        model = ModelParity('fixture','model','revision-1','tok','tok-1','template-hash','sampling-hash',0,100,'context-hash',self.profile.key)
        data = {'schema_version':2,'dataset_id':'dataset-v1','source':{'uri':'fixture:local','revision':'rev1'},
                'splits':{split:[{'task_id':split+str(i),'family_id':split+'family'+str(i),
                                  'instruction':'private-question-'+split+str(i),'expected':'private-answer'}
                                 for i in range(30 if split=='holdout' else 1)]
                          for split in ('discovery','selection','holdout','regression')}}
        self.spec = {'job_id':'job1','profile':'worker','dataset':data,'model':asdict(model),
            'generator_id':'generator','evaluator_id':'independent','adapter_id':'trusted-fixture','adapter_revision':'r1',
            'max_calls':65,'max_cost_usd':1,'discovery_cost_cap_usd':.1,'per_call_cost_cap_usd':.01,'permission_granted':True}
        self.discovery = Mock(return_value=DiscoveryReceipt({'candidates':[]},.01,False))
        self.provider, self.judge = Mock(), Mock()
        self.preflight = Mock(return_value=True)
        self.adapters = {'trusted-fixture': {'revision':'r1','discovery_execute':self.discovery,
                        'provider':self.provider,'judge':self.judge,'preflight':self.preflight}}

    def configure(self, enabled=True):
        (self.host.directory/'cce-config.json').write_text(json.dumps({'enabled':enabled,'profiles':{
            'worker':{'model_profile':asdict(self.profile),'task_type':'handoff'}}}))

    def enable_autoresearch(self, enabled=True):
        with sqlite3.connect(self.host.directory/'autoresearch.sqlite3') as db:
            db.execute('CREATE TABLE IF NOT EXISTS config(id INTEGER PRIMARY KEY,enabled INTEGER,profile TEXT)')
            db.execute('INSERT OR REPLACE INTO config VALUES(1,?,?)',(int(enabled),'worker'))

    def submit(self):
        return jobs.submit(self.host,self.spec)

    def test_status_absent_readonly_and_redacted_submission(self):
        path = self.host.directory/'autoresearch.sqlite3'
        self.assertEqual(jobs.status(self.host)['jobs'],[])
        self.assertFalse(path.exists())
        self.assertEqual(self.submit()['status'],'queued')
        self.assertEqual(jobs.status(self.host)['counts'],{'pending':1})
        self.assertNotIn('private-',str(jobs.status(self.host)))
        self.discovery.assert_not_called()

    def test_strict_admission_rejects_missing_regression_model_permission_and_budgets(self):
        for key,value in (('max_calls',64),('max_cost_usd',.01),('permission_granted',1),
                          ('evaluator_id','generator'),('unexpected','import:module')):
            bad=deepcopy(self.spec); bad[key]=value
            with self.assertRaises(ValueError):jobs.submit(self.host,bad)
        bad=deepcopy(self.spec); bad['model']['profile_key']='wrong'
        with self.assertRaises(ValueError):jobs.submit(self.host,bad)
        bad=deepcopy(self.spec); bad['dataset']['schema_version']=1; bad['dataset']['splits'].pop('regression')
        with self.assertRaises(ValueError):jobs.submit(self.host,bad)
        self.assertEqual(jobs.status(self.host)['jobs'],[])

    def test_paused_disabled_missing_adapter_revision_and_budget_wait_without_claim(self):
        self.submit()
        self.assertEqual(jobs.tick(self.host,self.adapters)['status'],'disabled')
        self.enable_autoresearch()
        self.configure(False)
        self.assertEqual(jobs.tick(self.host,self.adapters)['status'],'disabled')
        self.configure()
        self.assertEqual(jobs.tick(self.host)['status'],'waiting_for_adapter')
        self.adapters['trusted-fixture']['revision']='other'
        self.assertEqual(jobs.tick(self.host,self.adapters)['status'],'waiting_for_adapter_revision')
        self.adapters['trusted-fixture']['revision']='r1'
        self.preflight.return_value=1
        self.assertEqual(jobs.tick(self.host,self.adapters)['status'],'waiting_for_budget')
        self.assertEqual(jobs.status(self.host)['jobs'][0]['waiting_reason'],'waiting_for_budget')
        self.assertNotIn('private-',str(self.preflight.call_args))
        self.assertEqual(jobs.status(self.host)['counts'],{'pending':1})
        self.discovery.assert_not_called();self.provider.assert_not_called()

    def test_real_host_cycle_committed_claim_before_discovery_then_terminal_once(self):
        self.submit();self.enable_autoresearch()
        def discovery(*args,**kwargs):
            self.assertEqual(jobs.status(self.host)['counts'],{'running':1})
            self.assertEqual(kwargs['tenant'],'agentos-local')
            self.assertEqual(kwargs['agent'],'worker')
            return DiscoveryReceipt({'candidates':[]},.01,False)
        self.discovery.side_effect=discovery
        result=jobs.tick(self.host,self.adapters)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['result']['reason'],'no_candidate')
        self.assertFalse(result['activation_authorized'])
        self.assertEqual(self.discovery.call_count,1)
        self.assertIsNone(jobs.tick(self.host,self.adapters))
        self.provider.assert_not_called();self.judge.assert_not_called()
        status=jobs.status(self.host)
        self.assertEqual(status['jobs'][0]['outcome']['result']['reason'],'no_candidate')
        self.assertNotIn('private-',str(status))
        with sqlite3.connect(self.host.directory/'autoresearch.sqlite3') as db:
            self.assertGreaterEqual(db.execute("SELECT COUNT(*) FROM events WHERE kind='cce_job'").fetchone()[0],3)

    def test_model_config_drift_waits_without_preflight_or_dispatch(self):
        self.submit();self.enable_autoresearch()
        self.profile=ModelProfile('fixture','changed','revision-1','tok','tok-1',('instruction',),'template-1')
        self.configure()
        self.assertEqual(jobs.tick(self.host,self.adapters)['status'],'waiting_for_profile')
        self.preflight.assert_not_called();self.discovery.assert_not_called()

    def test_duplicate_id_and_dataset_stay_consumed_after_cancel(self):
        self.submit()
        self.assertEqual(self.submit()['status'],'already_submitted')
        bad=dict(self.spec,adapter_revision='r2')
        with self.assertRaises(ValueError):jobs.submit(self.host,bad)
        self.assertEqual(jobs.cancel(self.host,'job1')['status'],'cancelled')
        self.assertEqual(jobs.submit(self.host,dict(self.spec,job_id='other'))['status'],'reused_dataset')
        self.assertIsNone(jobs.tick(self.host,self.adapters))
        with self.assertRaises(ValueError):jobs.cancel(self.host,'job1')
        with sqlite3.connect(self.host.directory/'autoresearch.sqlite3') as db:
            with self.assertRaises(sqlite3.IntegrityError):db.execute("DELETE FROM cce_jobs")
            with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE cce_jobs SET spec='{}'")
            with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE cce_jobs SET state='pending'")

    def test_explicit_recovery_abandons_running_without_replay_or_cancellation(self):
        self.submit();self.enable_autoresearch()
        with sqlite3.connect(self.host.directory/'autoresearch.sqlite3') as db:
            db.execute("UPDATE cce_jobs SET state='running'")
        self.assertIsNone(jobs.tick(self.host,self.adapters))
        with self.assertRaises(ValueError):jobs.cancel(self.host,'job1')
        self.assertEqual(jobs.recover(self.host)['abandoned'],['job1'])
        self.assertEqual(jobs.recover(self.host)['abandoned'],[])
        self.assertIsNone(jobs.tick(self.host,self.adapters))
        self.discovery.assert_not_called()

    def test_callback_failure_persisted_redacted_and_never_retried(self):
        self.submit();self.enable_autoresearch()
        with patch.object(CueHost,'run_dataset_cycle',side_effect=RuntimeError('private raw exception')) as run:
            result=jobs.tick(self.host,self.adapters)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['error_category'],'RuntimeError')
        self.assertNotIn('private',str(jobs.status(self.host)))
        self.assertIsNone(jobs.tick(self.host,self.adapters))
        self.assertEqual(run.call_count,1)
        self.assertEqual(jobs.submit(self.host,dict(self.spec,job_id='retry'))['status'],'reused_dataset')

    def test_atomic_claim_prevents_duplicate_dispatch(self):
        self.submit();self.enable_autoresearch()
        entered=threading.Event();release=threading.Event();results=[]
        def discovery(*args,**kwargs):
            entered.set()
            self.assertTrue(release.wait(5))
            return DiscoveryReceipt({'candidates':[]},.01,False)
        self.discovery.side_effect=discovery
        thread=threading.Thread(target=lambda:results.append(jobs.tick(self.host,self.adapters)))
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertIsNone(jobs.tick(self.host,self.adapters))
        finally:
            release.set();thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.discovery.call_count,1)
        self.assertEqual(results[0]['status'],'completed')

    def test_load_spec_rejects_duplicates_nonfinite_oversize_and_fifo(self):
        path=Path(self.temp.name)/'spec.json'
        path.write_text(json.dumps(self.spec))
        self.assertEqual(jobs.load_spec(path),self.spec)
        for raw in ('{"job_id":"x","job_id":"y"}','{"x":NaN}', '[]'):
            path.write_text(raw)
            with self.assertRaises(ValueError):jobs.load_spec(path)
        path.write_bytes(b'x'*(jobs.MAX_SPEC_BYTES+1))
        with self.assertRaises(ValueError):jobs.load_spec(path)
        import os
        fifo=Path(self.temp.name)/'fifo';os.mkfifo(fifo)
        with self.assertRaises(ValueError):jobs.load_spec(fifo)


if __name__=='__main__':unittest.main()
