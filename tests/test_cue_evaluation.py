import json
import unittest
from dataclasses import replace
from nerve_awim.cue_evaluation import (
    DatasetManifest, ModelParity, Observation, PairedResult, EvaluationReport,
    IndependentReceipt, evaluate_pairs, promotion_decision, discover_candidates,
)


class CueEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = DatasetManifest(('d1',), ('s1',), tuple('h%d' % i for i in range(30)))
        self.model = ModelParity('provider', 'model', 'rev', 'tok', 'tok-rev', 'template',
                                 'sampling', 0, 128, 'context', 'profile')
        self.pairs = tuple(PairedResult(
            Observation(task, self.model, False, True, .5, 10, .01, task+'base', False, '', 'baseline'),
            Observation(task, self.model, True, True, .9, 10, .01, task+'cue', False, 'a'*64, 'candidate'))
            for task in self.manifest.holdout)

    def report(self, pairs=None, **kwargs):
        return evaluate_pairs('cue-v1', self.manifest, self.pairs if pairs is None else pairs,
                              cue_digest='a'*64, task_type='reasoning', **kwargs)

    def decision(self, report):
        receipt = IndependentReceipt('independent', report.candidate_id, report.digest, True)
        return promotion_decision(report, [receipt], generator_id='generator')

    def test_metrics_and_roundtrip(self):
        report = self.report()
        self.assertEqual(report.metrics['paired_accuracy_delta'], 1)
        self.assertAlmostEqual(report.metrics['candidate']['brier_score'], .01)
        loaded = EvaluationReport.from_dict(json.loads(json.dumps(report.to_dict())))
        self.assertEqual(loaded.digest, report.digest)
        self.assertTrue(self.decision(loaded).eligible)

    def test_leakage_and_incomplete_partition(self):
        with self.assertRaises(ValueError):
            DatasetManifest(('x',), ('y',), ('x',))
        with self.assertRaises(ValueError): self.report(self.pairs[:-1])
        with self.assertRaises(ValueError): self.report(self.pairs + self.pairs[:1])

    def test_parity_includes_template_tokenizer_and_sampling(self):
        for field in ('revision', 'tokenizer_revision', 'template_digest', 'sampling_digest'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                PairedResult(self.pairs[0].baseline, replace(self.pairs[0].candidate,
                    model=replace(self.model, **{field: 'different'})))
        with self.assertRaises(ValueError): self.report(profile_key='another')

    def test_missing_nonfinite_and_boolean_metrics(self):
        for field, value in [('confidence', None), ('confidence', float('nan')),
                             ('cost_usd', None), ('cost_usd', -1),
                             ('latency_ms', float('inf')), ('correct', 1),
                             ('confidence', True), ('confidence', 1.1)]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                replace(self.pairs[0].candidate, **{field: value})
        raw = self.report().to_dict()
        del raw['pairs'][0]['candidate']['cost_usd']
        with self.assertRaises(ValueError): EvaluationReport.from_dict(raw)

    def test_reused_evidence_rejected(self):
        with self.assertRaises(ValueError):
            replace(self.pairs[0], candidate=replace(self.pairs[0].candidate,
                evidence_id=self.pairs[0].baseline.evidence_id))

    def test_safety_regression_fails_closed(self):
        rows = list(self.pairs)
        rows[0] = replace(rows[0], candidate=replace(rows[0].candidate, safe=False))
        self.assertIn('safety_failure', self.decision(self.report(rows)).reasons)

    def test_receipt_missing_stale_and_self_generated(self):
        report = self.report()
        self.assertFalse(promotion_decision(report, generator_id='g').eligible)
        for evaluator, digest in [('g', report.digest), ('other', 'stale')]:
            receipt = IndependentReceipt(evaluator, report.candidate_id, digest, True)
            self.assertFalse(promotion_decision(report, [receipt], generator_id='g').eligible)
        valid = IndependentReceipt('other', report.candidate_id, report.digest, True)
        reject = replace(valid, evaluator_id='third', approved=False)
        self.assertFalse(promotion_decision(report, [valid, reject], generator_id='g').eligible)

    def test_fixture_and_unbound_report_cannot_promote(self):
        rows = [replace(p, candidate=replace(p.candidate, synthetic=True)) for p in self.pairs]
        self.assertIn('live_evidence_required', self.decision(self.report(rows)).reasons)
        report = evaluate_pairs('cue', self.manifest, self.pairs)
        self.assertFalse(self.decision(report).eligible)

    def test_small_selection_and_no_gain_cannot_promote(self):
        pair = self.pairs[0]
        selection_pair = PairedResult(replace(pair.baseline, task_id='s1'),
                                      replace(pair.candidate, task_id='s1'))
        report = evaluate_pairs('cue', self.manifest, [selection_pair], split='selection',
                                cue_digest='a'*64, task_type='reasoning')
        decision = self.decision(report)
        self.assertIn('untouched_holdout_required', decision.reasons)
        self.assertIn('insufficient_pairs', decision.reasons)
        rows = [replace(p, candidate=replace(p.candidate, correct=False)) for p in self.pairs]
        self.assertIn('accuracy_gain_required', self.decision(self.report(rows)).reasons)
        with self.assertRaises(ValueError): promotion_decision(self.report(), min_pairs=1)

    def test_observation_cue_binding_required(self):
        for field, value in [('cue_digest', 'b'*64), ('arm', '')]:
            rows = [replace(p, candidate=replace(p.candidate, **{field:value})) for p in self.pairs]
            self.assertIn('observation_cue_binding_required', self.decision(self.report(rows)).reasons)

    def test_metric_regressions(self):
        for field, value, reason in [('latency_ms', 11, 'latency_ms_regression'),
                                    ('cost_usd', .02, 'cost_usd_regression'),
                                    ('confidence', 0, 'brier_score_regression')]:
            rows = [replace(p, candidate=replace(p.candidate, **{field: value})) for p in self.pairs]
            self.assertIn(reason, self.decision(self.report(rows)).reasons)

    def test_discovery_uses_existing_hermes_only_and_hides_holdout(self):
        calls = []
        def execute(role, payload, **kwargs):
            calls.append((role, payload, kwargs))
            return {'candidates': ['Check assumptions.']}
        self.assertEqual(discover_candidates(execute, self.manifest, tenant='t', agent='a'),
                         ('Check assumptions.',))
        self.assertEqual(calls[0][0], 'research')
        self.assertEqual(calls[0][1]['discovery_ids'], ['d1'])
        self.assertNotIn('holdout', calls[0][1])
        with self.assertRaises(ValueError):
            discover_candidates(lambda *a, **kw: {'candidates': ['x']*5}, self.manifest,
                                tenant='t', agent='a')


if __name__ == '__main__':
    unittest.main()
