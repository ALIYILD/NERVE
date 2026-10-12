"""Unknown confidence remains measured-but-ineligible throughout governance."""
import unittest

import test_cue_cycle as fixtures
from nerve_awim.cue_experiment import ProviderReceipt
from nerve_awim.cue_release import build_release_manifest


class CueCycleCalibrationTests(unittest.TestCase):
    setUp = fixtures.CueCycleTests.setUp
    run_cycle = fixtures.CueCycleTests.run_cycle

    def provider(self, request, *, missing_selection):
        missing = missing_selection or request.task_id in self.manifest.holdout
        return ProviderReceipt('right' if request.arm == 'candidate' else 'wrong',
            None if missing else (1. if request.arm == 'candidate' else 0.),
            request.model, .009 if request.arm == 'candidate' else .01,
            request.task_id+request.arm, False, False, request.cue_digest,request.arm,
            input_tokens=10,output_tokens=1)

    def assert_cannot_activate(self, candidate):
        with self.assertRaises(PermissionError):
            self.cce.activate(self.actors['operator'],candidate,expected_generation=0,reason='review')
        self.assertIsNone(self.cce.select(self.actors['runtime'],self.profile,'research',permission_granted=True).cue)

    def test_missing_selection_calibration_stops_before_holdout_without_crash(self):
        seen=[]
        def provider(request):
            seen.append(request.task_id)
            return self.provider(request,missing_selection=True)
        result=self.run_cycle(provider=provider)
        self.assertEqual(result['state'],'rejected')
        self.assertEqual(result['reason'],'missing_calibration')
        self.assertEqual(result['attempted_calls'],3)
        self.assertEqual(set(seen),set(self.manifest.selection))
        self.assertIsNone(result['holdout_digest'])
        self.assert_cannot_activate(result['candidate'])

    def test_missing_holdout_calibration_persists_honestly_and_readiness_blocks(self):
        result=self.run_cycle(provider=lambda request:self.provider(request,missing_selection=False))
        self.assertEqual(result['state'],'rejected')
        self.assertEqual(result['reason'],'holdout_gate_failed')
        self.assertEqual(result['attempted_calls'],63)
        self.assert_cannot_activate(result['candidate'])
        status=self.cce.status(self.actors['auditor'],result['candidate'])
        self.assertIn('missing_calibration',status['evaluation']['decision']['reasons'])
        self.assertIsNone(status['evaluation']['metrics']['candidate']['brier_score'])
        readiness=build_release_manifest(profile_name='agent',profile=self.profile,
            host_status={'enabled':True,'reason':'enabled','profiles':{'agent':{'configured':True,
                'profile_key':self.profile.key,'task_type':'research','active_candidate':None}}},
            candidate_status=status,generator_id='generator',now=self.now)
        self.assertFalse(readiness['ready'])
        self.assertFalse(readiness['authorization_granted'])
        self.assertIn('evaluation:missing_calibration',readiness['blockers'])


if __name__=='__main__':unittest.main()
