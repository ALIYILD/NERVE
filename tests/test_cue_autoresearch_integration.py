"""Existing scheduler owns CCE dispatch; waiting jobs never trigger audit calls."""
from contextlib import redirect_stdout
from dataclasses import asdict
import importlib.util
import io
import json
from pathlib import Path
import sys
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim.cue_engine import ModelProfile
from nerve_awim.cue_evaluation import ModelParity

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('cue_autoresearch_integration',ROOT/'scripts/agentos_autoresearch.py')
loop=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loop)
SPEC=importlib.util.spec_from_file_location('cue_job_bridge_integration',ROOT/'scripts/agentos_bridge.py')
bridge=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class CueAutoresearchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.host=AgentOSLearning(Path(self.temp.name)/'state')
        self.native=Mock(side_effect=AssertionError('unexpected provider dispatch'))

    def test_paused_scheduler_never_recovers_or_dispatches_jobs(self):
        with patch.object(loop.cue_jobs,'recover') as recover, patch.object(loop.cue_jobs,'tick') as tick:
            result=loop.tick(self.host,self.native,cue_adapters={'registered':object()})
        self.assertEqual(result['status'],'paused')
        recover.assert_not_called();tick.assert_not_called();self.native.assert_not_called()

    def test_job_status_published_without_dispatch(self):
        sentinel={'counts':{'pending':2},'jobs':[],'activation_authorized':False}
        with patch.object(loop.cue_jobs,'status',return_value=sentinel), patch.object(loop.cue_jobs,'tick') as tick:
            self.assertEqual(loop.status(self.host)['cce_jobs'],sentinel)
        tick.assert_not_called();self.native.assert_not_called()

    def test_recovery_stops_tick_before_work(self):
        loop.configure(self.host,True)
        with patch.object(loop.cue_jobs,'recover',return_value={'status':'recovered','abandoned':['job-1']}), \
             patch.object(loop.cue_jobs,'tick') as tick, patch.object(loop.studies,'study') as audit:
            result=loop.tick(self.host,self.native)
        self.assertEqual(result['kind'],'cce_recovery')
        self.assertEqual(result['result']['jobs'],['job-1'])
        tick.assert_not_called();audit.assert_not_called();self.native.assert_not_called()

    def test_waiting_job_has_priority_and_builtin_adapter_registry_is_empty(self):
        loop.configure(self.host,True)
        waiting={'status':'waiting_for_adapter','job_id':'job-1','activation_authorized':False}
        with patch.object(loop.cue_jobs,'tick',return_value=waiting) as tick, \
             patch.object(loop.studies,'study') as audit, patch.object(loop.shadow,'_candidate') as shadow:
            result=loop.tick(self.host,self.native)
        tick.assert_called_once_with(self.host,adapters=None)
        self.assertEqual(result['kind'],'cce_job');self.assertEqual(result['outcome'],'wait')
        self.assertFalse(result['activation_authorized'])
        audit.assert_not_called();shadow.assert_not_called();self.native.assert_not_called()

    def test_exactly_one_job_with_injected_adapters_and_no_auto_activation(self):
        loop.configure(self.host,True)
        adapters={'reviewed-adapter':object()}
        completed={'status':'completed','job_id':'job-1',
                   'result':{'state':'awaiting_approval','activated':False},'activation_authorized':False}
        with patch.object(loop.cue_jobs,'tick',return_value=completed) as tick, patch.object(loop.studies,'study') as audit:
            result=loop.tick(self.host,self.native,cue_adapters=adapters)
        tick.assert_called_once_with(self.host,adapters=adapters)
        self.assertEqual(result['outcome'],'keep')
        self.assertFalse(result['activation_authorized'])
        audit.assert_not_called();self.native.assert_not_called()

    def test_no_jobs_preserves_existing_audit_path(self):
        loop.configure(self.host,True)
        with patch.object(loop.cue_jobs,'tick',return_value=None), \
             patch.object(loop.studies,'study',return_value={'status':'rejected'}) as audit:
            result=loop.tick(self.host,self.native)
        audit.assert_called_once_with(self.host,self.native,profile='qa-release')
        self.assertEqual(result['kind'],'study');self.native.assert_not_called()

    def test_interrupted_audit_recovers_before_queued_job_dispatch(self):
        loop.configure(self.host,True)
        with patch.object(loop.studies,'status',return_value={'status':'running'}), \
             patch.object(loop.cue_jobs,'tick') as tick:
            result=loop.tick(self.host,self.native)
        self.assertEqual(result['kind'],'recovery')
        tick.assert_not_called();self.native.assert_not_called()

    def job_spec(self):
        profile=ModelProfile('fixture','model','v1','tok','t1',('instruction',),'template')
        model=ModelParity('fixture','model','v1','tok','t1','template-digest','sampling',0,128,'context',profile.key)
        (self.host.directory/'cce-config.json').write_text(json.dumps({'enabled':True,
            'profiles':{'worker':{'model_profile':asdict(profile),'task_type':'handoff'}}}))
        dataset={'schema_version':2,'dataset_id':'queued-data','source':{'uri':'fixture:job','revision':'v1'},
            'splits':{split:[{'task_id':split+str(i),'family_id':split+str(i),
                'instruction':'private-question-'+split+str(i),'expected':'private-answer'}
                for i in range(30 if split=='holdout' else 1)]
                for split in ('discovery','selection','regression','holdout')}}
        spec={'job_id':'queued-cue','profile':'worker','dataset':dataset,'model':asdict(model),
              'generator_id':'generator','evaluator_id':'judge','adapter_id':'missing-adapter',
              'adapter_revision':'v1','max_calls':65,'max_cost_usd':1.,
              'discovery_cost_cap_usd':.1,'per_call_cost_cap_usd':.01,'permission_granted':True}
        return spec

    def test_real_running_job_is_untouched_while_paused_then_abandoned_without_dispatch(self):
        loop.cue_jobs.submit(self.host,self.job_spec())
        with sqlite3.connect(self.host.directory/'autoresearch.sqlite3') as db:
            db.execute("UPDATE cce_jobs SET state='running' WHERE job_id='queued-cue'")
        self.assertEqual(loop.tick(self.host,self.native)['status'],'paused')
        self.assertEqual(loop.cue_jobs.status(self.host)['counts'],{'running':1})
        loop.configure(self.host,True)
        with patch.object(loop.studies,'study') as audit:
            result=loop.tick(self.host,self.native)
        self.assertEqual(result['kind'],'cce_recovery')
        self.assertEqual(loop.cue_jobs.status(self.host)['counts'],{'abandoned':1})
        audit.assert_not_called();self.native.assert_not_called()

    def test_real_queue_waits_without_adapters_then_cancel_allows_audit(self):
        loop.cue_jobs.submit(self.host,self.job_spec())
        self.assertFalse(loop.status(self.host)['enabled'])
        self.assertEqual(loop.tick(self.host,self.native)['status'],'paused')
        loop.configure(self.host,True)
        result=loop.tick(self.host,self.native)
        self.assertEqual(result['result']['status'],'waiting_for_adapter')
        state=loop.status(self.host)
        self.assertEqual(state['cce_jobs']['counts'],{'pending':1})
        self.assertNotIn('private-question',json.dumps(state))
        self.assertNotIn('private-answer',json.dumps(state))
        loop.cue_jobs.cancel(self.host,'queued-cue')
        with patch.object(loop.studies,'study',return_value={'status':'rejected'}) as audit:
            resumed=loop.tick(self.host,self.native)
        self.assertEqual(resumed['kind'],'study');audit.assert_called_once()
        self.native.assert_not_called()

    def invoke_bridge(self,*args):
        output=io.StringIO()
        with patch.object(sys,'argv',['agentos_bridge.py',*args,'--state',str(self.host.directory)]),redirect_stdout(output):
            bridge.main()
        return json.loads(output.getvalue())

    def test_bridge_job_submit_uses_bounded_loader_without_enabling_scheduler(self):
        spec={'schema':'test'}
        with patch.object(loop.cue_jobs,'load_spec',return_value=spec) as load, \
             patch.object(loop.cue_jobs,'submit',return_value={'status':'queued'}) as submit, \
             patch.object(bridge,'native') as native:
            result=self.invoke_bridge('cce-job-submit','--task',str(Path(self.temp.name)/'job.json'))
        self.assertEqual(result['status'],'queued')
        load.assert_called_once();self.assertEqual(submit.call_args.args[1],spec)
        native.assert_not_called();self.assertFalse(loop.status(self.host)['enabled'])

    def test_bridge_cancel_and_status_have_no_tick_bypass(self):
        with patch.object(loop.cue_jobs,'cancel',return_value={'status':'cancelled'}) as cancel, \
             patch.object(loop.cue_jobs,'tick') as tick:
            result=self.invoke_bridge('cce-job-cancel','--cue-job','job-1')
            self.assertEqual(result['status'],'cancelled')
            self.assertEqual(cancel.call_args.args[1],'job-1')
            self.invoke_bridge('cce-job-status')
        tick.assert_not_called()
        with patch.object(sys,'argv',['agentos_bridge.py','cce-job-tick']),patch('sys.stderr',io.StringIO()):
            with self.assertRaises(SystemExit):bridge.main()


if __name__=='__main__':unittest.main()
