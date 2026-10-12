"""Fabricated offline contract fixtures never serve as live staging receipts."""
from copy import deepcopy
from dataclasses import asdict, replace
import unittest
from nerve_awim.cue_engine import ModelProfile
from nerve_awim.cue_evaluation import (DatasetManifest, ModelParity, Observation, PairedResult,
    IndependentReceipt, evaluate_pairs, promotion_decision)
from nerve_awim.cue_release import StagingReceipt, RollbackReceipt, build_release_manifest


class CueReleaseTests(unittest.TestCase):
    def setUp(self):
        self.profile=ModelProfile('provider','model','revision','tok','tok-rev',('instruction',),'template-rev')
        model=ModelParity('provider','model','revision','tok','tok-rev','template','sampling',0,100,'context',self.profile.key)
        manifest=DatasetManifest(('d',),('s',),tuple('h%d'%i for i in range(30)))
        pairs=tuple(PairedResult(Observation(t,model,False,True,.1,10,.01,t+'b',False,'','baseline'),
            Observation(t,model,True,True,1,9,.009,t+'c',False,'a'*64,'candidate')) for t in manifest.holdout)
        self.report=evaluate_pairs('candidate',manifest,pairs,profile_key=self.profile.key,cue_digest='a'*64,task_type='handoff')
        receipt=IndependentReceipt('independent','candidate',self.report.digest,True)
        decision=promotion_decision(self.report,[receipt],generator_id='generator')
        self.candidate={'candidate':'candidate','status':'approved','task_type':'handoff', 'expires':2000,
            'profile_key':self.profile.key,'generator_id':'generator',
            'evaluation':{'report':self.report.to_dict(),'metrics':self.report.metrics,'receipt':asdict(receipt),
                          'decision':decision.to_dict()}}
        self.host={'enabled':True,'reason':'enabled','profiles':{'worker':{'configured':True,
            'profile_key':self.profile.key,'task_type':'handoff','active_candidate':'candidate'}}}
        self.stage=StagingReceipt('stage','candidate',self.report.digest,self.profile.key,True,True,True,950,False)
        self.rollback=RollbackReceipt('rollback','candidate',self.profile.key,'no-cue',True,960,False)

    def build(self,**overrides):
        kwargs=dict(profile_name='worker',profile=self.profile,host_status=self.host,
            candidate_status=self.candidate,generator_id='generator',now=1000)
        kwargs.update(overrides)
        return build_release_manifest(**kwargs)

    def test_default_staging_and_rollback_missing_with_actions(self):
        result=self.build()
        self.assertFalse(result['ready'])
        self.assertEqual(result['blockers'],['staging_missing','rollback_missing'])
        self.assertFalse(result['authorization_granted'])
        self.assertEqual(result['rollback']['target'],'no-cue')
        self.assertTrue(result['next_steps'])

    def test_complete_receipts_only_report_readiness_never_authority(self):
        result=self.build(staging=self.stage,rollback=self.rollback)
        self.assertTrue(result['ready'])
        self.assertFalse(result['authorization_granted'])
        self.assertEqual(result,self.build(staging=self.stage,rollback=self.rollback))
        self.assertNotIn('pairs',result)
        self.assertNotIn('cue',result)

    def test_dataset_cutover_blocks_legacy_readiness(self):
        candidate=dict(self.candidate,dataset={'required':True,'bound':False,'digest':None})
        result=self.build(candidate_status=candidate,staging=self.stage,rollback=self.rollback)
        self.assertFalse(result['ready'])
        self.assertEqual(result['blockers'],['dataset_binding_required'])
        self.assertEqual(result['dataset'],candidate['dataset'])
        candidate['dataset']['required']=False
        self.assertTrue(result['dataset']['required'])
        for invalid in (None, {'required':True,'bound':False,'digest':'a'*64},
                        {'required':True,'bound':True,'digest':None}):
            with self.assertRaises(ValueError):
                self.build(candidate_status=dict(self.candidate,dataset=invalid))

    def test_staging_fixtures_stale_future_and_wrong_bindings_fail(self):
        for override in ({'synthetic':True},{'worker_attested':False},{'cue_applied':False},
                         {'smoke_passed':False},{'candidate':'other'},{'report_digest':'b'*64},
                         {'observed_at':1001},{'observed_at':1}):
            stage=replace(self.stage,**override)
            now=100000 if override=={'observed_at':1} else 1000
            self.assertIn('staging_invalid',self.build(staging=stage,rollback=self.rollback,now=now)['blockers'])
        with self.assertRaises(ValueError): self.build(staging=asdict(self.stage))

    def test_rollback_must_be_live_scoped_and_distinct(self):
        for override in ({'synthetic':True},{'verified':False},{'candidate':'other'},
                         {'profile_key':'b'*64},{'evidence_id':'stage'}):
            self.assertIn('rollback_invalid',self.build(staging=self.stage,
                rollback=replace(self.rollback,**override))['blockers'])

    def test_missing_evidence_disabled_host_expired_and_unapproved(self):
        status=dict(self.candidate,evaluation=None,status='pending',expires=None)
        result=self.build(candidate_status=status,host_status=dict(self.host,enabled=False,reason='disabled'))
        for blocker in ('host_disabled','evaluation_missing','evidence_expired','candidate_not_approved'):
            self.assertIn(blocker,result['blockers'])
        self.assertIn('candidate_missing',self.build(candidate_status=None)['blockers'])

    def test_report_tampering_or_synthetic_evidence_cannot_qualify(self):
        for key in ('decision','metrics'):
            status=deepcopy(self.candidate)
            status['evaluation'][key]['forged']=True
            self.assertIn('stored_evidence_mismatch',self.build(candidate_status=status)['blockers'])
        status=deepcopy(self.candidate)
        status['evaluation']['report']['pairs'][0]['candidate']['synthetic']=True
        result=self.build(candidate_status=status)
        self.assertFalse(result['ready'])
        self.assertIn('evaluation:live_evidence_required',result['blockers'])
        with self.assertRaises(ValueError): self.build(generator_id='another')

    def test_exact_profile_and_active_pointer_required(self):
        self.assertIn('profile_mismatch',self.build(profile=replace(self.profile,revision='changed'))['blockers'])
        host=deepcopy(self.host)
        host['profiles']['worker']['active_candidate']='other'
        self.assertIn('candidate_not_active',self.build(host_status=host)['blockers'])


if __name__=='__main__':unittest.main()
