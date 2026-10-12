"""Missing measurement coverage stays explicit and cannot authorize promotion."""
from dataclasses import asdict, replace
from hashlib import sha256
import json
import unittest

from nerve_awim.cue_engine import Cue
from nerve_awim.cue_evaluation import (DatasetManifest, ModelParity, Observation, PairedResult,
    EvaluationReport, IndependentReceipt, evaluate_pairs, promotion_decision)
from nerve_awim.cue_experiment import ExperimentTask, ProviderReceipt, JudgeReceipt, run_experiment


class MissingConfidenceTests(unittest.TestCase):
    def setUp(self):
        self.model=ModelParity('p','m','r','t','tr','template','sampling',0,128,'context','a'*64)
        self.manifest=DatasetManifest(('d',),('s',),tuple('h%d'%i for i in range(30)))
        self.pairs=tuple(PairedResult(
            Observation(t,self.model,False,True,.1,10,.01,t+'b',False,'','baseline'),
            Observation(t,self.model,True,True,1.,9,.009,t+'c',False,'b'*64,'candidate')) for t in self.manifest.holdout)

    def report(self,pairs=None):
        return evaluate_pairs('candidate',self.manifest,self.pairs if pairs is None else pairs,
                              cue_digest='b'*64,task_type='handoff')

    def test_one_missing_confidence_blocks_brier_and_promotion(self):
        rows=list(self.pairs)
        rows[0]=replace(rows[0],candidate=replace(rows[0].candidate,confidence=None))
        report=self.report(rows)
        self.assertIsNone(report.metrics['candidate']['brier_score'])
        self.assertEqual(report.metrics['candidate']['calibration_coverage'],
                         {'measured_observations':29,'observations':30})
        receipt=IndependentReceipt('judge','candidate',report.digest,True)
        decision=promotion_decision(report,[receipt],generator_id='generator')
        self.assertIn('missing_calibration',decision.reasons)
        self.assertFalse(decision.eligible)
        self.assertIsNone(EvaluationReport.from_dict(report.to_dict()).pairs[0].candidate.confidence)

    def test_historical_digest_preserved_when_optional_usage_unknown(self):
        report=self.report()
        old_schema=asdict(report)
        old_schema['manifest'].pop('regression',None)
        for pair in old_schema['pairs']:
            for arm in ('baseline','candidate'):
                del pair[arm]['input_tokens']; del pair[arm]['output_tokens']
        old_digest=sha256(json.dumps(old_schema,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.assertEqual(report.digest,old_digest)
        self.assertEqual(EvaluationReport.from_dict(old_schema).digest,old_digest)
        self.assertNotIn('token_usage',report.metrics['candidate'])
        self.assertNotIn('calibration_coverage',report.metrics['candidate'])

    def test_token_coverage_never_treats_missing_as_zero(self):
        rows=list(self.pairs)
        rows[0]=replace(rows[0],candidate=replace(rows[0].candidate,input_tokens=0,output_tokens=5))
        rows[1]=replace(rows[1],candidate=replace(rows[1].candidate,input_tokens=10))
        report=self.report(rows)
        usage=report.metrics['candidate']['token_usage']
        self.assertEqual(usage['input_tokens'],{'measured_observations':2,'total':10})
        self.assertEqual(usage['output_tokens'],{'measured_observations':1,'total':5})
        self.assertEqual(usage['observations'],30)
        self.assertEqual(EvaluationReport.from_dict(report.to_dict()).digest,report.digest)
        self.assertNotEqual(report.digest,self.report().digest)

    def test_invalid_tokens_and_confidence_still_rejected(self):
        receipt=ProviderReceipt('answer',None,self.model,.01,'evidence')
        for field,value in [('input_tokens',-1),('output_tokens',True),('input_tokens',1.5),
                            ('confidence',float('nan')),('confidence',True)]:
            with self.subTest(field=field,value=value):
                with self.assertRaises(ValueError): replace(receipt,**{field:value})
                with self.assertRaises(ValueError): replace(self.pairs[0].candidate,**{field:value})

    def test_runner_preserves_absent_probability_and_actual_usage(self):
        manifest=DatasetManifest(('d',),('s',),('h',))
        cue=Cue('cue',1,'Check the answer.','instruction','a'*64,('handoff',),'test')
        def provider(request):
            return ProviderReceipt('answer',None,request.model,0.,request.arm,False,
                cue_digest=request.cue_digest,arm=request.arm,input_tokens=17,output_tokens=3)
        report=run_experiment('candidate',cue,manifest,[ExperimentTask('h','question','answer')],
            self.model,provider,lambda **kw:JudgeReceipt(True,True),max_calls=2,max_cost_usd=.02,
            per_call_cost_cap_usd=.01,permission_granted=True)
        self.assertIsNone(report.pairs[0].candidate.confidence)
        self.assertEqual(report.pairs[0].candidate.input_tokens,17)
        self.assertEqual(report.pairs[0].candidate.output_tokens,3)
        self.assertIsNone(report.metrics['baseline']['brier_score'])


if __name__=='__main__':unittest.main()
