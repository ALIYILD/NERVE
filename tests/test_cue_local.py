import unittest
from unittest.mock import Mock

from nerve_awim.cue_engine import ModelProfile
from nerve_awim.cue_evaluation import ModelParity
from nerve_awim.cue_experiment import ProviderReceipt
from nerve_awim.cue_local import run_local_smoke


class LocalSmokeTests(unittest.TestCase):
    def test_incomplete_run_retains_sanitized_failure_evidence(self):
        profile=ModelProfile('fixture','local','v1','embedded-artifact','hash',('instruction',),'template')
        model=ModelParity('fixture','local','v1','embedded-artifact','hash',
            'template','sampling',0.,96,'context',profile.key)
        adapter=Mock(side_effect=RuntimeError('PRIVATE_OUTPUT'))
        adapter.profile=profile; adapter.model_config=model
        adapter.inspect.return_value={}; adapter.summary.return_value={'attempted_calls':1}
        result=run_local_smoke(adapter)
        self.assertEqual(result['state'],'blocked')
        self.assertEqual(result['attempted_calls'],1)
        self.assertIsNone(result['report'])
        self.assertNotIn('PRIVATE_OUTPUT',str(result))
        self.assertFalse(result['activation_authorized'])

    def test_real_shaped_missing_confidence_never_promotes_and_retains_tokens(self):
        profile=ModelProfile('fixture','local','v1','embedded-artifact','hash',('instruction',),'template')
        model=ModelParity('fixture','local','v1','embedded-artifact','hash',
            'template','sampling',0.,96,'context',profile.key)
        requests=[]
        def generate(request):
            requests.append(request)
            return ProviderReceipt('43' if request.task_id=='local-addition' else '42',None,
                model,0.,request.task_id+request.arm,False,False,request.cue_digest,request.arm,
                input_tokens=20,output_tokens=2)
        adapter=Mock(side_effect=generate)
        adapter.profile=profile; adapter.model_config=model
        adapter.inspect.return_value={'scope':'fixture only'}
        adapter.summary.return_value={'scope':'fixture only'}
        result=run_local_smoke(adapter)
        self.assertEqual(len(requests),4)
        self.assertFalse(result['activation_authorized'])
        self.assertFalse(result['paper_reproduced'])
        self.assertFalse(result['decision']['eligible'])
        self.assertIn('missing_calibration',result['decision']['reasons'])
        self.assertIsNone(result['metrics']['candidate']['brier_score'])
        self.assertEqual(result['metrics']['candidate']['accuracy'],1.)
        for request in requests:
            self.assertFalse(hasattr(request,'expected'))
        for pair in result['report']['pairs']:
            self.assertNotIn('output',pair['candidate'])
            self.assertEqual(pair['candidate']['output_tokens'],2)

    def test_invalid_integer_is_not_a_safe_success(self):
        profile=ModelProfile('fixture','local','v1','embedded-artifact','hash',('instruction',),'template')
        model=ModelParity('fixture','local','v1','embedded-artifact','hash',
            'template','sampling',0.,96,'context',profile.key)
        adapter=Mock(side_effect=lambda r:ProviderReceipt('Here is unrelated text',None,model,0.,
            r.task_id+r.arm,False,False,r.cue_digest,r.arm))
        adapter.profile=profile; adapter.model_config=model
        adapter.inspect.return_value={}; adapter.summary.return_value={}
        result=run_local_smoke(adapter)
        self.assertEqual(result['metrics']['baseline']['safety'],0.)
        self.assertEqual(result['metrics']['candidate']['accuracy'],0.)
