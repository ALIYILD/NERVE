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

    def approve(self):
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


if __name__ == '__main__': unittest.main()
