"""Retained-capability screening cannot substitute for untouched holdout evidence."""
from dataclasses import asdict, replace
from hashlib import sha256
import json
import unittest

from nerve_awim.cue_engine import Cue
from nerve_awim.cue_evaluation import (DatasetManifest, ModelParity, Observation, PairedResult,
    EvaluationReport, IndependentReceipt, evaluate_pairs, regression_decision, promotion_decision)
from nerve_awim.cue_experiment import ExperimentTask, ProviderReceipt, JudgeReceipt, run_experiment


class CueRegressionEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.model=ModelParity('p','m','r','t','tr','template','sampling',0,128,'context','a'*64)
        self.manifest=DatasetManifest(('d',),('s',),('h',),('r1','r2'))
        self.pairs=tuple(PairedResult(
            Observation(t,self.model,True,True,1.,10,.01,t+'b',False,'','baseline'),
            Observation(t,self.model,True,True,1.,10,.01,t+'c',False,'b'*64,'candidate'))
            for t in self.manifest.regression)

    def report(self,pairs=None):
        return evaluate_pairs('candidate',self.manifest,self.pairs if pairs is None else pairs,
            split='regression',profile_key=self.model.profile_key,cue_digest='b'*64,task_type='handoff')

    def decision(self,report):
        receipt=IndependentReceipt('independent','candidate',report.digest,True)
        return regression_decision(report,[receipt],generator_id='generator')

    def test_no_gain_small_complete_partition_passes_only_regression_gate(self):
        report=self.report()
        self.assertTrue(self.decision(report).eligible)
        self.assertEqual(report.metrics['paired_accuracy_delta'],0)
        self.assertFalse(promotion_decision(report,generator_id='generator').eligible)
        self.assertEqual(EvaluationReport.from_dict(report.to_dict()).digest,report.digest)

    def test_losses_cannot_be_cancelled_by_other_gains(self):
        rows=[replace(self.pairs[0],candidate=replace(self.pairs[0].candidate,correct=False,confidence=0.)),
              replace(self.pairs[1],baseline=replace(self.pairs[1].baseline,correct=False,confidence=0.))]
        report=self.report(rows)
        self.assertEqual(report.metrics['paired_accuracy_delta'],0)
        self.assertIn('retained_capability_loss',self.decision(report).reasons)

    def test_safety_calibration_latency_cost_and_synthetic_gates(self):
        for override,reason in [({'safe':False},'safety_failure'),
                ({'confidence':None},'missing_calibration'),({'confidence':.5},'brier_score_regression'),
                ({'latency_ms':11},'latency_ms_regression'),({'cost_usd':.02},'cost_usd_regression'),
                ({'synthetic':True},'live_evidence_required'),({'arm':''},'observation_cue_binding_required'),
                ({'cue_digest':'c'*64},'observation_cue_binding_required')]:
            rows=[replace(p,candidate=replace(p.candidate,**override)) for p in self.pairs]
            with self.subTest(reason=reason):
                self.assertIn(reason,self.decision(self.report(rows)).reasons)

    def test_incomplete_leaking_or_wrong_partition_rejected(self):
        with self.assertRaises(ValueError): self.report(self.pairs[:1])
        with self.assertRaises(ValueError): DatasetManifest(('d',),('s',),('h',),('h',))
        with self.assertRaises(ValueError): DatasetManifest(('d',),('s',),('h',),('r','r'))
        pair=PairedResult(replace(self.pairs[0].baseline,task_id='h'),replace(self.pairs[0].candidate,task_id='h'))
        holdout=evaluate_pairs('candidate',self.manifest,[pair],cue_digest='b'*64,task_type='handoff')
        self.assertIn('regression_partition_required',self.decision(holdout).reasons)

    def test_receipts_cannot_be_missing_stale_or_self_judged(self):
        report=self.report()
        for receipts in ([],[IndependentReceipt('generator','candidate',report.digest,True)],
                         [IndependentReceipt('independent','candidate','stale',True)]):
            self.assertFalse(regression_decision(report,receipts,generator_id='generator').eligible)
        receipt=IndependentReceipt('independent','candidate',report.digest,True)
        self.assertFalse(regression_decision(report,[receipt,replace(receipt,approved=False)],generator_id='generator').eligible)

    def test_empty_regression_preserves_historical_report_digest(self):
        manifest=DatasetManifest(('d',),('s',),('h',))
        self.assertNotIn('regression',manifest.to_dict())
        pair=PairedResult(replace(self.pairs[0].baseline,task_id='h'),replace(self.pairs[0].candidate,task_id='h'))
        report=evaluate_pairs('candidate',manifest,[pair],cue_digest='b'*64,task_type='handoff')
        historical=asdict(report)
        del historical['manifest']['regression']
        for arm in ('baseline','candidate'):
            del historical['pairs'][0][arm]['input_tokens']; del historical['pairs'][0][arm]['output_tokens']
        digest=sha256(json.dumps(historical,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.assertEqual(report.digest,digest)
        self.assertEqual(EvaluationReport.from_dict(historical).digest,digest)
        with self.assertRaises(ValueError):evaluate_pairs('candidate',manifest,[],split='regression')

    def test_runner_executes_exact_regression_partition(self):
        cue=Cue('cue',1,'Check the answer.','instruction',self.model.profile_key,('handoff',),'fixture')
        calls=[]
        def provider(request):
            calls.append(request)
            return ProviderReceipt('answer',1.,request.model,.01,request.task_id+request.arm,False,
                cue_digest=request.cue_digest,arm=request.arm)
        report=run_experiment('candidate',cue,self.manifest,
            [ExperimentTask(t,'question '+t,'answer') for t in self.manifest.regression],
            self.model,provider,lambda **kw:JudgeReceipt(True,True),max_calls=4,max_cost_usd=.04,
            per_call_cost_cap_usd=.01,permission_granted=True,split='regression')
        self.assertEqual(report.split,'regression')
        self.assertEqual({r.task_id for r in calls},{'r1','r2'})
        self.assertEqual(len(calls),4)


if __name__=='__main__':unittest.main()
