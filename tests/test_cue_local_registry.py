"""Local scheduling adapters: no network, isolated durable budget evidence."""
from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.agentos_learning import AgentOSLearning, expected_handoff
from nerve_awim.cue_engine import ModelProfile
from nerve_awim.cue_evaluation import ModelParity
from nerve_awim.cue_experiment import ProviderRequest, ProviderReceipt

SPEC=importlib.util.spec_from_file_location('cue_local_registry',Path(__file__).resolve().parents[1]/'scripts/agentos_cue_local.py')
local=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(local)


class FakeAdapter:
    instances=[]
    def __init__(self,model,digest,**kwargs):
        self.options=kwargs; self.calls=0; self.inspections=0; self.fail=False; self.timeout=kwargs['timeout']
        self.requests=[]; self.answer=None
        self.profile=ModelProfile('ollama',model,digest,'gguf','tokenizer-v1',('instruction',),kwargs['response_contract'] or 'raw-v1')
        self.model_config=ModelParity('ollama',model,digest,'gguf','tokenizer-v1',self.profile.template_revision,'sampling-v1',0.,kwargs['max_output_tokens'],'context-v1',self.profile.key)
        self.instances.append(self)
    def inspect(self):
        self.inspections+=1
        return {'profile_key':self.profile.key}
    def __call__(self,request):
        self.calls+=1; self.requests.append(request)
        if self.fail: raise RuntimeError('sensitive task failure')
        if self.options['response_contract'] is None:
            output='Check each supplied evidence field before concluding.'; confidence=None
        else:
            output=self.answer or local._canonical({'status':'done','passed':True,'memory_saved':True}); confidence=.73
        return ProviderReceipt(output,confidence,request.model,0.,f'local-{self.calls}',False,False,request.cue_digest,request.arm,30,12)
    def summary(self):
        return {'calls':self.calls,'input_tokens':self.calls*30,'output_tokens':self.calls*12}


class LocalRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.host=AgentOSLearning(Path(self.tmp.name)); FakeAdapter.instances=[]
        self.patch=patch.object(local,'OllamaCueAdapter',FakeAdapter); self.patch.start(); self.addCleanup(self.patch.stop)
        self.config={'enabled':True,'model':'qwen2.5:3b','model_digest':'a'*64}
        self.write_config()
    def write_config(self):
        (self.host.directory/'cce-local-research.json').write_text(json.dumps(self.config))
    def admission(self,cap=77):
        binding=local.inspect_binding(self.host)
        (self.host.directory/'cce-config.json').write_text(json.dumps({'enabled':True,'profiles':{'qa-release':{'model_profile':binding['profile'],'task_type':'handoff'}}}))
        return {key:binding[key] for key in ('adapter_id','adapter_revision','generator_id','evaluator_id','model')}|{'job_id':'job1','profile':'qa-release','max_calls':cap}
    def ready(self,cap=77):
        admission=self.admission(cap)
        adapter=local.adapters_for(self.host)[local.ADAPTER_ID]
        self.assertTrue(adapter['preflight'](self.host,admission))
        return adapter
    def request(self,adapter,**facts):
        job=adapter['provider'].__self__
        evidence={'id':'task1','exit_code':0,'artifact_exists':True,'qa_passed':True,'memory_written':True}|facts
        return ProviderRequest('task1',local._canonical(evidence),'','','','baseline',job.evaluation.model_config,0.),local._canonical(expected_handoff(evidence))
    def test_factory_disabled_invalid_missing_is_inert(self):
        path=self.host.directory/'cce-local-research.json'
        for text in ('{}','{"enabled":true,"enabled":false}','null',json.dumps(self.config|{'extra':1}),json.dumps(self.config|{'enabled':False})):
            path.write_text(text); self.assertEqual(local.adapters_for(self.host),{})
        path.unlink(); self.assertEqual(local.adapters_for(self.host),{})
        self.assertEqual(FakeAdapter.instances,[])
    def test_factory_lazy_and_metadata_inspection_never_generates(self):
        self.assertIn(local.ADAPTER_ID,local.adapters_for(self.host)); self.assertEqual(FakeAdapter.instances,[])
        binding=local.inspect_binding(self.host)
        self.assertEqual(binding['max_job_calls'],77); self.assertFalse(binding['activation_authorized'])
        self.assertEqual(FakeAdapter.instances[0].calls,0)
    def test_preflight_exact_identity_and_budget(self):
        admission=self.admission()
        for field in ('generator_id','evaluator_id','adapter_revision','adapter_id'):
            registry=local.adapters_for(self.host)[local.ADAPTER_ID]
            self.assertFalse(registry['preflight'](self.host,admission|{field:'wrong'}))
        registry=local.adapters_for(self.host)[local.ADAPTER_ID]
        wrong=admission|{'model':admission['model']|{'temperature':.5}}
        self.assertFalse(registry['preflight'](self.host,wrong))
        self.assertFalse(registry['preflight'](self.host,admission|{'max_calls':81}))
        self.assertTrue(registry['preflight'](self.host,admission))
        self.assertFalse(registry['preflight'](self.host,admission))
        self.assertTrue(all(a.calls==0 for a in FakeAdapter.instances))
    def test_measured_receipt_confidence_preserved_independent_judge(self):
        adapter=self.ready(); request,expected=self.request(adapter)
        receipt=adapter['provider'](request)
        self.assertEqual(receipt.confidence,.73)
        self.assertTrue(adapter['judge'](output=receipt.output,expected=expected).correct)
        job=adapter['provider'].__self__
        self.assertEqual(job.evaluation.requests,[request])
        self.assertNotIn(expected,request.instruction)
        self.assertEqual(local._used(self.host),1)
        snapshot=(self.host.directory/'cce-local-last-run.json').read_text()
        self.assertNotIn('artifact_exists',snapshot); self.assertNotIn('memory_saved',snapshot)
        self.assertFalse(json.loads(snapshot)['activation_authorized'])
    def test_wrong_dataset_expected_rejected_and_judge_one_shot(self):
        adapter=self.ready(); request,expected=self.request(adapter)
        receipt=adapter['provider'](request)
        with self.assertRaises(ValueError): adapter['judge'](output=receipt.output,expected='{}')
        with self.assertRaises(ValueError): adapter['judge'](output=receipt.output,expected=expected)
    def test_wrong_model_answer_does_not_change_confidence(self):
        adapter=self.ready(); request,expected=self.request(adapter,exit_code=1)
        receipt=adapter['provider'](request)
        verdict=adapter['judge'](output=receipt.output,expected=expected)
        self.assertFalse(verdict.correct); self.assertTrue(verdict.safe); self.assertEqual(receipt.confidence,.73)
    def test_failed_generation_burns_durable_call_without_raw_error(self):
        adapter=self.ready(); request,_=self.request(adapter)
        adapter['provider'].__self__.evaluation.fail=True
        with self.assertRaises(RuntimeError): adapter['provider'](request)
        self.assertEqual(local._used(AgentOSLearning(self.host.directory)),1)
        snapshot=(self.host.directory/'cce-local-last-run.json').read_text()
        self.assertIn('RuntimeError',snapshot); self.assertNotIn('sensitive',snapshot)
        with sqlite3.connect(self.host.path) as db:
            with self.assertRaises(sqlite3.IntegrityError): db.execute('DELETE FROM cce_local_calls')
    def test_daily_limit_and_remaining_job_budget(self):
        admission=self.admission()
        for n in range(4): local._reserve(self.host,str(n),'evaluation')
        self.assertFalse(local.adapters_for(self.host)[local.ADAPTER_ID]['preflight'](self.host,admission))
        for n in range(76): local._reserve(self.host,str(n),'evaluation')
        with self.assertRaises(PermissionError): local._reserve(self.host,'overflow','evaluation')
        self.assertEqual(local._used(self.host),80)
    def test_job_cap_deadline_and_config_revocation(self):
        adapter=self.ready(cap=1); request,_=self.request(adapter)
        adapter['provider'](request)
        with self.assertRaises(PermissionError): adapter['provider'](request)
        self.assertEqual(local._used(self.host),1)
        job=adapter['provider'].__self__; job.calls=0; job.started-=601
        with self.assertRaises(PermissionError): adapter['provider'](request)
        job.started+=601; self.config['enabled']=False; self.write_config()
        with self.assertRaises(PermissionError): adapter['provider'](request)
        self.assertEqual(local._used(self.host),1)
    def test_discovery_existing_research_callback_and_bounded_raw_adapter(self):
        adapter=self.ready()
        receipt=adapter['discovery_execute']('research',{'max_candidates':1},tenant='agentos-local',agent='qa-release',cost_cap_usd=0.)
        self.assertFalse(receipt.synthetic); self.assertEqual(len(receipt.result['candidates']),1)
        job=adapter['provider'].__self__
        self.assertIsNone(job.discovery.options['response_contract']); self.assertEqual(job.discovery.options['max_calls'],1)
        self.assertEqual(job.evaluation.options['max_calls'],76)
        self.assertEqual(local._used(self.host),1)
    def test_noncanonical_task_fails_before_serving_but_burns_reservation(self):
        adapter=self.ready(); request,_=self.request(adapter)
        with self.assertRaises(ValueError): adapter['provider'](replace(request,instruction=' '+request.instruction))
        self.assertEqual(adapter['provider'].__self__.evaluation.calls,0)
        self.assertEqual(local._used(self.host),1)

if __name__=='__main__': unittest.main()
