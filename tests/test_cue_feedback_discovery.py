"""Only bounded scoped evaluator observations can influence fresh discovery."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
import unittest

import test_cue_cycle as cycle_fixtures
import test_cue_host as host_fixtures
import test_cue_learning as learning_fixtures
from nerve_awim.cue_discovery import discover_cue_pool
from nerve_awim.cue_evaluation import DatasetManifest, discover_candidates
from nerve_awim.cue_feedback import learning_context_digest


def context(profile_key,task_type='research',candidates=True):
    text='Check previously missed assumptions.'
    return {'schema_version':1,'profile_key':profile_key,'task_type':task_type,
        'source':'trusted_evaluator_feedback','causal_evidence':False,'authorization_granted':False,
        'candidates':[{'cue_text':text,'cue_digest':sha256(text.encode()).hexdigest(),
            'status':'revoked','observations':2,'correct':1,'safe':2}] if candidates else []}


class FeedbackDiscoveryTests(unittest.TestCase):
    setUp=cycle_fixtures.CueCycleTests.setUp
    run_cycle=cycle_fixtures.CueCycleTests.run_cycle

    def test_no_history_preserves_original_payload_exactly(self):
        calls=[]
        def execute(role,payload,**scope):
            calls.append(deepcopy(payload));return {'candidates':['Check assumptions.']}
        for value in (None,context(self.profile.key,candidates=False)):
            discover_candidates(execute,self.manifest,tenant='tenant',agent='agent',learning_context=value)
        self.assertEqual(calls,[{'operation':'propose_cognitive_cues','discovery_ids':['d'],'max_candidates':4}]*2)

    def test_history_is_bounded_untrusted_data_and_callback_cannot_mutate_snapshot(self):
        history=context(self.profile.key)
        original=deepcopy(history)
        calls=[]
        def execute(role,payload,**scope):
            calls.append(deepcopy(payload))
            payload['history']['candidates'][0]['cue_text']='mutation'
            return {'candidates':['Verify each assumption.']}
        discover_candidates(execute,self.manifest,tenant='tenant',agent='agent',learning_context=history)
        self.assertEqual(history,original)
        self.assertEqual(calls[0]['history'],history)
        self.assertIn('untrusted observations',calls[0]['history_instruction'])
        self.assertIn('do not prove',calls[0]['history_instruction'])
        self.assertNotIn('holdout',calls[0]);self.assertNotIn('selection',calls[0])

    def test_pool_rejects_foreign_or_extra_context_before_dispatch(self):
        calls=[]
        def execute(*args,**kwargs):calls.append(args);return {'candidates':[]}
        for history in (context('a'*64),context(self.profile.key,'other'),
                        dict(context(self.profile.key),raw_memory='arbitrary memory')):
            with self.assertRaises(ValueError):
                discover_cue_pool(execute,self.manifest,self.profile,'research',tenant='tenant',agent='agent',
                    generator_id='generator',permission_granted=True,learning_context=history)
        self.assertEqual(calls,[])

    def test_cycle_derives_scoped_feedback_and_records_only_digest_and_count(self):
        previous=self.cce.propose(self.actors['trainer'],self.cue,self.profile,'research',self.manifest,
            generator_id='generator',model_config=self.model)
        self.cce.evaluate(self.actors['evaluator'],previous,learning_fixtures.CueLearningTests.pairs(self),
                          evaluator_id='independent')
        self.cce.activate(self.actors['operator'],previous,expected_generation=0,reason='review')
        self.cce.feedback(self.actors['evaluator'],previous,episode_id='PRIVATE_EPISODE_ID',safe=True,correct=False)
        frozen=self.cce.learning_context(self.actors['trainer'],self.profile,'research')
        self.manifest=replace(self.manifest,holdout=tuple('fresh-'+t for t in self.manifest.holdout))
        result=self.run_cycle()
        payload=self.discovery_payloads[0][1]
        self.assertEqual(payload['history'],frozen)
        self.assertEqual(result['learning_context_digest'],learning_context_digest(frozen))
        self.assertEqual(result['learning_context_candidates'],1)
        self.assertEqual(result['state'],'awaiting_approval')
        self.assertFalse(result['activated'])
        self.assertNotIn(self.cue.text,json.dumps(result))
        self.assertNotIn('PRIVATE_EPISODE_ID',json.dumps(payload))
        self.assertEqual(payload['discovery_ids'],['d'])
        with self.assertRaises(TypeError):self.run_cycle(learning_context=frozen)


class FeedbackDiscoveryHostTests(unittest.TestCase):
    setUp=host_fixtures.CueHostTests.setUp
    configure=host_fixtures.CueHostTests.configure
    approve=host_fixtures.CueHostTests.approve

    def test_host_discovery_owns_context_and_rejects_caller_overrides(self):
        previous=self.approve()
        self.adapter.feedback('worker',previous,episode_id='PRIVATE_EPISODE_ID',safe=False,correct=True)
        calls=[]
        def execute(role,payload,**scope):
            calls.append(deepcopy(payload));return {'candidates':['Verify evidence references.']}
        manifest=DatasetManifest(('new-d',),('new-s',),('new-h',))
        batch=self.adapter.discover('worker',execute,manifest,generator_id='generator',
                                   permission_granted=True,max_calls=1)
        self.assertEqual(batch.attempted_calls,1)
        self.assertEqual(calls[0]['history']['task_type'],'handoff')
        self.assertEqual(calls[0]['history']['profile_key'],self.profile.key)
        self.assertEqual(calls[0]['history']['candidates'][0]['status'],'revoked')
        self.assertNotIn('PRIVATE_EPISODE_ID',json.dumps(calls))
        public=(self.host.directory/'cce-last-discovery.json').read_text()
        self.assertNotIn('Check the evidence.',public)
        with self.assertRaises(ValueError):
            self.adapter.discover('worker',execute,manifest,generator_id='generator',
                permission_granted=True,learning_context=context(self.profile.key,'handoff'))
        self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
