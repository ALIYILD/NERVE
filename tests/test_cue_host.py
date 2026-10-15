import json
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from nerve_awim.agentos_learning import AgentOSLearning
from nerve_awim.cue_host import CueHost
from nerve_awim.cue_engine import Cue, ModelProfile
from nerve_awim.cue_evaluation import DatasetManifest, ModelParity, Observation, PairedResult


class CueHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.host = AgentOSLearning(self.temp.name)
        self.adapter = CueHost(self.host)
        self.profile = ModelProfile('fixture', 'model', 'revision-1', 'tokenizer', 'tokens-1',
                                    ('instruction',), 'template-1')
        self.config = {'enabled': True, 'profiles': {'worker':
            {'model_profile': asdict(self.profile), 'task_type': 'handoff'}}}

    def configure(self, config=None):
        (Path(self.temp.name)/'cce-config.json').write_text(json.dumps(self.config if config is None else config))

    def approve(self, activate=True):
        self.configure()
        coordinator = self.adapter._coordinator('worker')
        cue = Cue('verify', 1, 'Check the evidence.', 'instruction', self.profile.key,
                  ('handoff',), 'test fixture')
        manifest = DatasetManifest(('d',), ('s',), tuple('h%d'%i for i in range(30)))
        model = ModelParity('fixture','model','revision-1','tokenizer','tokens-1',
                            'template-hash','sampling-hash',0,100,'context-hash',self.profile.key)
        candidate = coordinator.propose(self.adapter._actor('worker','trainer'), cue, self.profile,
            'handoff', manifest, generator_id='generator', model_config=model)
        pairs = tuple(PairedResult(
            Observation(t,model,False,True,.1,10,.01,t+'b',False,'','baseline'),
            Observation(t,model,True,True,1,9,.009,t+'c',False,cue.content_hash,'candidate')) for t in manifest.holdout)
        coordinator.evaluate(self.adapter._actor('worker','evaluator'),candidate,pairs,evaluator_id='independent')
        if activate:
            coordinator.activate(self.adapter._actor('worker','operator'),candidate,expected_generation=0,reason='test')
        return candidate

    def test_missing_disabled_invalid_config_stays_off(self):
        self.assertEqual(self.adapter.status()['reason'],'not_configured')
        self.assertIsNone(self.adapter.prepare('worker','handoff',permission_granted=True)['envelope'])
        self.assertIsNone(self.adapter._engine)
        self.configure(dict(self.config, enabled=False))
        self.assertEqual(self.adapter.status()['reason'],'disabled')
        self.configure(dict(self.config, extra=True))
        self.assertEqual(self.adapter.status()['reason'],'invalid_config')

    def test_profile_must_be_pinned_and_schema_complete(self):
        for field in ('revision','tokenizer_revision','template_revision'):
            raw=asdict(self.profile); raw[field]='unknown'
            self.configure({'enabled':True,'profiles':{'worker':{'model_profile':raw,'task_type':'handoff'}}})
            self.assertEqual(self.adapter.status()['reason'],'invalid_config')
        (Path(self.temp.name)/'cce-config.json').write_text('{"enabled":true,"enabled":false,"profiles":{}}')
        self.assertEqual(self.adapter.status()['reason'],'invalid_config')

    def test_context_permission_and_unknown_profiles_no_bootstrap(self):
        self.configure()
        for kwargs in ({}, {'permission_granted':True,'clinical':True},
                       {'permission_granted':True,'risk':'high'}):
            self.assertIsNone(self.adapter.prepare('worker','handoff',**kwargs)['envelope'])
        self.assertIsNone(self.adapter.prepare('worker','research',permission_granted=True)['envelope'])
        self.assertIsNone(self.adapter.prepare('unknown','handoff',permission_granted=True)['envelope'])
        self.assertIsNone(self.adapter._engine)

    def test_approved_envelope_sanitized_receipt_and_same_database(self):
        candidate=self.approve()
        result=self.adapter.prepare('worker','handoff',permission_granted=True)
        self.assertEqual(result['envelope']['cue']['approval_id'],candidate)
        self.assertTrue(result['receipt']['worker_attestation_required'])
        self.assertEqual(self.adapter._engine.path,str(self.host.path))
        receipt=(Path(self.temp.name)/'cce-last-receipt.json').read_text()
        self.assertNotIn('Check the evidence.',receipt)
        self.assertEqual(self.adapter.status('worker')['profiles']['worker']['active_candidate'],candidate)
        reloaded=CueHost(AgentOSLearning(self.temp.name))
        self.assertIsNotNone(reloaded.prepare('worker','handoff',permission_granted=True)['envelope'])

    def test_changed_model_and_expired_approval_never_prepare(self):
        candidate = self.approve()
        raw = asdict(self.profile); raw['revision'] = 'revision-2'
        self.configure({'enabled':True,'profiles':{'worker':{'model_profile':raw,'task_type':'handoff'}}})
        self.assertIsNone(self.adapter.prepare('worker','handoff',permission_granted=True)['envelope'])
        self.configure()
        with self.adapter._engine._db() as con:
            con.execute('UPDATE cce_candidates SET expires=1 WHERE id=?', (candidate,))
        self.assertIsNone(self.adapter.prepare('worker','handoff',permission_granted=True)['envelope'])

    def test_inspect_revoke_and_feedback_use_scoped_existing_governance(self):
        candidate=self.approve()
        self.assertEqual(self.adapter.inspect('worker',candidate)['status'],'approved')
        with self.assertRaises(LookupError): self.adapter.inspect('other',candidate)
        memory=self.adapter.export_memory('worker',candidate)
        self.assertEqual(self.host.ledger.status(self.host.actor('worker'),memory).status,'pending')
        self.adapter.feedback('worker',candidate,episode_id='outcome',safe=False,correct=True)
        self.assertIsNone(self.adapter.prepare('worker','handoff',permission_granted=True)['envelope'])
        self.assertEqual(self.adapter.revoke('worker',candidate,reason='review')['status'],'revoked')

    def test_operator_approval_checks_current_profile_and_generation(self):
        candidate = self.approve(activate=False)
        self.assertEqual(self.adapter.route_status('worker'), {'active': None, 'generation': 0})
        with self.assertRaises(ValueError):
            self.adapter.approve('worker', candidate, expected_generation=1, reason='stale-review')
        raw = asdict(self.profile); raw['revision'] = 'revision-2'
        self.configure({'enabled':True,'profiles':{'worker':{'model_profile':raw,'task_type':'handoff'}}})
        with self.assertRaises(PermissionError):
            self.adapter.approve('worker', candidate, expected_generation=0, reason='wrong-model')
        self.configure()
        result = self.adapter.approve('worker', candidate, expected_generation=0, reason='independent-review')
        self.assertEqual(result['generation'], 1)
        self.assertEqual(self.adapter.route_status('worker')['active'], candidate)
        with self.assertRaises(PermissionError):
            self.adapter.approve('worker', candidate, expected_generation=1, reason='repeat')

    def test_disabled_host_cannot_dispatch_or_approve(self):
        from unittest.mock import Mock
        dispatch = Mock()
        with self.assertRaises(PermissionError):
            self.adapter.run_cycle('worker', discovery_execute=dispatch, permission_granted=True)
        with self.assertRaises(PermissionError):
            self.adapter.approve('worker', 'candidate', expected_generation=0, reason='review')
        self.configure()
        with self.assertRaises(PermissionError):
            self.adapter.run_cycle('worker', discovery_execute=dispatch)
        with self.assertRaises(ValueError):
            self.adapter.run_cycle('worker', permission_granted=True, task_type='clinical')
        dispatch.assert_not_called()
        self.assertIsNone(self.adapter._engine)

    def test_host_cycle_persists_evidence_and_pending_memory_without_activation(self):
        import itertools
        from nerve_awim.cue_cycle import DiscoveryReceipt
        from nerve_awim.cue_experiment import ExperimentTask, ProviderReceipt, JudgeReceipt
        self.configure()
        manifest = DatasetManifest(('d',), ('s',), tuple('h%d'%i for i in range(30)))
        model = ModelParity('fixture','model','revision-1','tokenizer','tokens-1',
                            'template-hash','sampling-hash',0,100,'context-hash',self.profile.key)
        def provider(request):
            candidate = request.arm == 'candidate'
            return ProviderReceipt('right' if candidate else 'wrong', float(candidate), request.model,
                .009 if candidate else .01, request.task_id+request.arm, False, False,
                request.cue_digest, request.arm)
        ticks = itertools.count()
        result = self.adapter.run_cycle('worker', model=model, manifest=manifest,
            selection_tasks=[ExperimentTask(t,'instruction:'+t,'right') for t in manifest.selection],
            holdout_tasks=[ExperimentTask(t,'instruction:'+t,'right') for t in manifest.holdout],
            discovery_execute=lambda *a, **k: DiscoveryReceipt({'candidates':['Check the evidence.']},.01,False),
            provider=provider, judge=lambda output,expected: JudgeReceipt(output==expected,True),
            generator_id='generator', evaluator_id='independent', max_calls=63, max_cost_usd=1,
            discovery_cost_cap_usd=.1,per_call_cost_cap_usd=.01,permission_granted=True,
            experiment_clock=lambda:next(ticks))
        self.assertEqual(result['state'],'awaiting_approval')
        self.assertFalse(result['activated'])
        self.assertEqual(self.host.ledger.status(self.host.actor('worker'),result['memory_id']).status,'pending')
        self.assertIsNone(self.adapter.route_status('worker')['active'])
        persisted=json.loads((Path(self.temp.name)/'cce-last-cycle.json').read_text())
        self.assertEqual(persisted,result)
        self.assertNotIn('instruction:',json.dumps(result))

    def test_operator_cli_and_readiness_use_persisted_evidence(self):
        import subprocess
        import sys
        candidate = self.approve(activate=False)
        script = Path(__file__).resolve().parents[1]/'scripts/agentos_bridge.py'
        def cli(command, *arguments):
            process = subprocess.run([sys.executable,str(script),command,'--state',self.temp.name,
                '--profile','worker',*arguments],capture_output=True,text=True,timeout=20)
            self.assertEqual(process.returncode,0,process.stderr)
            return json.loads(process.stdout)
        self.assertEqual(cli('cce-route')['generation'],0)
        ready = cli('cce-readiness','--cue-candidate',candidate)
        self.assertIn('candidate_not_approved',ready['blockers'])
        self.assertIn('staging_missing',ready['blockers'])
        self.assertFalse(ready['authorization_granted'])
        cli('cce-approve','--cue-candidate',candidate,'--cue-generation','0','--cue-review','test-review')
        self.assertEqual(cli('cce-route')['active'],candidate)
        ready=cli('cce-readiness','--cue-candidate',candidate)
        self.assertEqual(set(ready['blockers']),{'staging_missing','rollback_missing'})
        self.assertFalse(ready['ready'])

    def test_discovery_host_wiring_keeps_proposals_unapproved_and_audit_redacted(self):
        self.configure()
        calls=[]
        def execute(role,payload,**scope):
            calls.append((role,payload,scope))
            return {'candidates':['Check the evidence.']}
        batch=self.adapter.discover('worker',execute,DatasetManifest(('d',),('s',),('h',)),
            generator_id='generator',max_calls=1,max_candidates=1,permission_granted=True)
        self.assertEqual(len(batch.candidates),1)
        self.assertEqual(calls[0][2],{'tenant':'agentos-local','agent':'worker'})
        audit=(Path(self.temp.name)/'cce-last-discovery.json').read_text()
        self.assertNotIn('Check the evidence.',audit)
        self.assertFalse(json.loads(audit)['approved'])
        self.assertIsNone(self.adapter._engine)


if __name__ == '__main__': unittest.main()
