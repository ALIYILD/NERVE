import json
import unittest
from dataclasses import replace
from nerve_awim.cue_engine import Cue
from nerve_awim.cue_evaluation import DatasetManifest, ModelParity
from nerve_awim.cue_experiment import (ExperimentTask, ProviderReceipt, JudgeReceipt,
                                       ExperimentBlocked, run_experiment)


class CueExperimentTests(unittest.TestCase):
    def setUp(self):
        self.model = ModelParity('p','m','r','t','tr','template','sampling',0,100,'context','a'*64)
        self.cue = Cue('cue',1,'Check assumptions.','instruction','a'*64,('reasoning',),'fixture')
        self.manifest = DatasetManifest(('d',), ('s',), ('h1','h2'))
        self.tasks = (ExperimentTask('h1','problem1','secret1'), ExperimentTask('h2','problem2','secret2'))
        self.calls = []
        self.judgments = []
        self.tick = 0

    def clock(self):
        self.tick += .01
        return self.tick

    def provider(self, request):
        self.calls.append(request)
        return ProviderReceipt('answer', .8, request.model, .01, 'receipt%d' % len(self.calls),
                               cue_digest=request.cue_digest, arm=request.arm)

    def judge(self, **kwargs):
        self.judgments.append(kwargs)
        return JudgeReceipt(True, True)

    def run_it(self, **overrides):
        kwargs = dict(candidate_id='candidate', cue=self.cue, manifest=self.manifest,
            tasks=self.tasks, model=self.model, provider=self.provider, judge=self.judge,
            max_calls=4, max_cost_usd=.08, per_call_cost_cap_usd=.02, clock=self.clock, permission_granted=True)
        kwargs.update(overrides)
        return run_experiment(**kwargs)

    def test_pairs_alternate_and_expected_never_reaches_provider(self):
        report = self.run_it()
        self.assertEqual([r.cue_prefix for r in self.calls], ['',self.cue.text,self.cue.text,''])
        self.assertTrue(all(not hasattr(r,'expected') for r in self.calls))
        self.assertTrue(all(set(j)=={'output','expected'} for j in self.judgments))
        self.assertAlmostEqual(report.metrics['baseline']['latency_ms'], 10)
        self.assertEqual(report.cue_digest, self.cue.content_hash)
        self.assertTrue(all(p.baseline.arm == 'baseline' and p.baseline.cue_digest == '' and
            p.candidate.arm == 'candidate' and p.candidate.cue_digest == self.cue.content_hash for p in report.pairs))
        serialized = json.dumps(report.to_dict())
        for value in ('problem1','secret1','answer'):
            self.assertNotIn(value, serialized)

    def test_budget_and_leakage_fail_before_dispatch(self):
        for override in ({'max_calls':3}, {'max_cost_usd':.03},
                         {'tasks':self.tasks[:1]},
                         {'tasks':(ExperimentTask('d','x','y'),self.tasks[1])}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.run_it(**override)
        self.assertEqual(self.calls, [])

    def test_unknown_cost_blocks_not_zero_or_drop(self):
        def provider(request):
            raise TimeoutError('sensitive exception')
        with self.assertRaises(ExperimentBlocked) as caught:
            self.run_it(provider=provider)
        self.assertEqual(caught.exception.attempted_calls, 1)
        self.assertEqual(caught.exception.failed_calls, 1)
        self.assertNotIn('sensitive', str(caught.exception))
        with self.assertRaises(ExperimentBlocked):
            self.run_it(provider=lambda request: {'cost_usd':None})

    def test_cost_and_model_receipt_mismatch_block(self):
        for field, value in [('cost_usd',.03), ('model',replace(self.model, revision='other'))]:
            def provider(request):
                return replace(self.provider(request), **{field:value})
            with self.subTest(field=field), self.assertRaises(ExperimentBlocked):
                self.run_it(provider=provider)

    def test_missing_or_wrong_cue_echo_blocks_before_judging(self):
        for override in ({'arm':''}, {'arm':'candidate'}, {'cue_digest':'b'*64}):
            def provider(request):
                return replace(self.provider(request), **override)
            with self.subTest(override=override), self.assertRaises(ExperimentBlocked) as caught:
                self.run_it(provider=provider)
            self.assertEqual(caught.exception.reason, 'provider_cue_binding_violation')
        self.assertEqual(self.judgments, [])

    def test_provider_failure_receipt_is_counted(self):
        def provider(request):
            return replace(self.provider(request), error=bool(request.cue_prefix))
        report = self.run_it(provider=provider)
        self.assertEqual(len(report.pairs), 2)
        self.assertEqual(report.metrics['candidate']['accuracy'],0)
        self.assertEqual(report.metrics['candidate']['safety'],0)
        self.assertEqual(len(self.judgments),2)

    def test_security_gates_and_duplicate_content_before_calls(self):
        for overrides in ({'permission_granted':False}, {'clinical':True}, {'risk':'high'}, {'risk':'unknown'}):
            with self.subTest(overrides=overrides), self.assertRaises(PermissionError):
                self.run_it(**overrides)
        with self.assertRaises(ValueError):
            self.run_it(tasks=(self.tasks[0], replace(self.tasks[1], instruction=self.tasks[0].instruction)))
        self.assertEqual(self.calls, [])

    def test_judge_failure_blocks(self):
        with self.assertRaises(ExperimentBlocked) as caught:
            self.run_it(judge=lambda **kwargs: {'correct':True})
        self.assertEqual(caught.exception.reason,'independent_judge_failed')


if __name__ == '__main__': unittest.main()
