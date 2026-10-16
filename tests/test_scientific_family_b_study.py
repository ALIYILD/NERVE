from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('family_study',ROOT/'scripts/run_scientific_family_b_study.py');study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)

class FixedClock(datetime):
    @classmethod
    def now(cls,tz=None):return datetime(2026,10,15,23,0,tzinfo=timezone.utc)

class FamilyStudyTests(unittest.TestCase):
    def setUp(self):
        clock=patch.object(study,'datetime',FixedClock);clock.start();self.addCleanup(clock.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.root=self.base/'study';self.budget=self.base/'budget'
        self.identity=patch.object(study.transport,'identity',return_value={'pod_id':study.transport.POD,'gpu':'NVIDIA A40','model':study.transport.MODEL,'model_digest':study.transport.DIGEST,'runtime':{'version':'0.40.5'}});self.identity.start();self.addCleanup(self.identity.stop)
    def register(self):return study.register(self.root,'calibration',None,ROOT/'docs/galahad/evidence/family-b-resumption-protocol-v1.json',None,self.budget,running_start=FixedClock.now(timezone.utc).isoformat(),prior_running_seconds=0)
    def wire(self,path,body,timeout):
        request=json.loads(body);facts=json.loads(request['messages'][1]['content'].split('Records in supplied order: ',1)[1]);record=facts[0]
        content=json.dumps({'value':float(record['value']),'unit':record['unit'],'source_id':record['source_id']})
        return json.dumps({'model':study.transport.MODEL,'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':content}}], 'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}}).encode()
    def test_register_then_run_and_network_free_replay(self):
        reg=self.register();self.assertEqual(reg['max_logical_calls'],5)
        with patch.object(study.transport,'network',side_effect=self.wire) as call:result=study.run(self.root)
        self.assertEqual(call.call_count,5);self.assertTrue(result['complete']);self.assertEqual(len(list(self.budget.glob('call-*.json'))),5)
        with patch.object(study.transport,'network',side_effect=AssertionError('replay must not call')):self.assertEqual(study.verify(self.root),result)
        with self.assertRaises(FileExistsError):study.run(self.root)
    def test_timeout_only_identical_retry_claims(self):
        self.register();requests=[]
        def wire(path,body,timeout):
            requests.append(body)
            if len(requests)==1:raise TimeoutError()
            return self.wire(path,body,timeout)
        with patch.object(study.transport,'network',side_effect=wire):result=study.run(self.root)
        self.assertEqual(result['attempts'],6);self.assertEqual(result['timeouts'],1);self.assertEqual(requests[0],requests[1])
    def test_non_timeout_stops_without_retry(self):
        self.register()
        with patch.object(study.transport,'network',side_effect=RuntimeError('broken')) as call:result=study.run(self.root)
        self.assertEqual(call.call_count,1);self.assertFalse(result['complete']);self.assertEqual(result['verdict'],'incomplete_infrastructure')
    def test_source_change_rejects_before_inference(self):
        self.register()
        with patch.object(study,'pins',return_value={}),patch.object(study.transport,'network',side_effect=AssertionError('no inference')):
            with self.assertRaises(ValueError):study.run(self.root)
    def test_tampered_aggregate_rejected(self):
        self.register()
        with patch.object(study.transport,'network',side_effect=self.wire):study.run(self.root)
        path=self.root/'aggregate.json';value=json.loads(path.read_text());value['attempts']=0;path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):study.verify(self.root)
    def test_random_abstention_is_valid_control(self):
        task=study.bank.item(bytes(32),'dev','supported-measurement',0);p=study.control_prepared(study.prepare(task,'random'),'random')
        result=study.score('ABSTAIN',task,p);self.assertTrue(result['format_valid']);self.assertTrue(result['false_abstention'])
    def test_domain_violation_does_not_repair_output(self):
        task=study.bank.item(bytes(32),'dev','supported-measurement',0);p=study.prepare(task,'adapted_v1');source=p['records'][0]['source_id']
        result=study.score(json.dumps({'value':999999,'unit':'mg','source_id':source}),task,p);self.assertTrue(result['domain_violation']);self.assertFalse(result['strict_correct'])

    def test_exact_development_candidate_binding(self):
        candidate=self.base/'candidate.py';candidate.write_text('# registered fixture')
        reg={'kind':'dev','candidate_module':str(candidate),'sources':{str(candidate):study.hashbytes(candidate.read_bytes())},'protocol_sha256':'protocol'}
        study.require_exact_development_candidate(reg,str(candidate),'protocol')
        other=self.base/'other.py';other.write_text('# substitute')
        with self.assertRaises(ValueError):study.require_exact_development_candidate(reg,str(other),'protocol')
        candidate.write_text('# tampered')
        with self.assertRaises(ValueError):study.require_exact_development_candidate(reg,str(candidate),'protocol')
    def test_replacement_transport_rejects_laptop_and_original_pod(self):
        with patch.object(study.transport.platform,'system',return_value='Darwin'),patch.dict(study.transport.os.environ,{'RUNPOD_POD_ID':study.transport.POD}):
            with self.assertRaises(RuntimeError):study.transport.network('/api/tags')
        with patch.object(study.transport.platform,'system',return_value='Linux'),patch.dict(study.transport.os.environ,{'RUNPOD_POD_ID':'lg0svvuenxvbno'}):
            with self.assertRaises(RuntimeError):study.transport.network('/api/tags')
        self.assertEqual(study.transport.POD,'97vr620wnmtuga')
        self.assertEqual(study.transport.original.POD,'lg0svvuenxvbno')

    def test_attended_window_caps_deadline_before_final_handoff(self):
        class AttendedClock(datetime):
            @classmethod
            def now(cls,tz=None):return datetime(2026,10,16,6,30,tzinfo=timezone.utc)
        with patch.object(study,'datetime',AttendedClock):
            study.register(self.root,'calibration',None,ROOT/'docs/galahad/evidence/family-b-attended-protocol-v3.json',None,self.budget,running_start='2026-10-16T06:30:00+00:00',prior_running_seconds=1160.783)
        reg=json.loads((self.root/'registration.json').read_text())
        self.assertEqual(reg['absolute_deadline_utc'],'2026-10-16T10:15:00+00:00')
        self.assertEqual(reg['prior_running_seconds'],1160.783)
        self.assertEqual(reg['physical_attempt_cap'],6000)
        self.assertEqual(len(list(self.budget.glob('call-*.json'))),0)

    def test_loop_wall_budgets(self):
        self.assertEqual(study.study_wall_budget('dev',None),1800)
        self.assertEqual(study.study_wall_budget('dev','candidate.py'),2400)
        self.assertEqual(study.study_wall_budget('holdout','candidate.py',{'wall_seconds':900}),1500)
        with self.assertRaises(ValueError):study.study_wall_budget('holdout','candidate.py',{'wall_seconds':2400})

    def test_new_budget_directory_rejected(self):
        reg={'budget_directory':str(self.budget.resolve()),'protocol_sha256':'protocol'}
        study.require_shared_budget(self.budget,reg,'protocol')
        with self.assertRaises(ValueError):study.require_shared_budget(self.base/'reset-counter',reg,'protocol')

if __name__=='__main__':unittest.main()
