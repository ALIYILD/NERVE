"""Offline fabricated snapshots exercise release regression gates only."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import unittest

import test_cue_release
from nerve_awim.cue_evaluation import (DatasetManifest, IndependentReceipt, evaluate_pairs,
    promotion_decision, regression_decision)


class CueReleaseRegressionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_cue_release.CueReleaseTests()
        self.fixture.setUp()
        old = self.fixture.report
        self.manifest = replace(old.manifest, regression=('regression-task',))
        self.holdout = replace(old, manifest=self.manifest)
        self.regression = evaluate_pairs('candidate', self.manifest,
            (replace(old.pairs[0], baseline=replace(old.pairs[0].baseline,
                task_id='regression-task', correct=True, confidence=1),
                candidate=replace(old.pairs[0].candidate, task_id='regression-task')),),
            split='regression', profile_key=old.profile_key, cue_digest=old.cue_digest, task_type='handoff')
        self.status = deepcopy(self.fixture.candidate)
        self.status['evaluation'] = self.evidence(self.holdout, promotion_decision)
        self.status['regression'] = {'required':True, 'evaluation':self.evidence(self.regression)}
        self.stage = replace(self.fixture.stage, report_digest=self.holdout.digest)

    def evidence(self, report, decide=regression_decision, evaluator='independent'):
        receipt = IndependentReceipt(evaluator, report.candidate_id, report.digest, True)
        return {'report':report.to_dict(), 'metrics':report.metrics, 'receipt':asdict(receipt),
                'decision':decide(report, (receipt,), generator_id='generator').to_dict()}

    def build(self):
        return self.fixture.build(candidate_status=self.status, staging=self.stage,
                                  rollback=self.fixture.rollback)

    def test_required_independent_gate_is_redacted(self):
        value = self.build()
        self.assertTrue(value['ready'], value['blockers'])
        self.assertEqual(value['regression']['report_digest'], self.regression.digest)
        encoded = json.dumps(value)
        self.assertNotIn('regression-task', encoded)
        self.assertNotIn('observations', encoded)
        self.assertNotIn('pairs', value['regression'])

    def test_manifest_requires_gate_even_without_metadata_or_false_flag(self):
        for metadata in (None, {'required':False, 'evaluation':None}, {'required':True, 'evaluation':None}):
            self.status.pop('regression', None)
            if metadata is not None:
                self.status['regression'] = metadata
            result = self.build()
            self.assertIn('regression_missing', result['blockers'])
            self.assertTrue(result['regression']['required'])

    def test_metadata_requires_gate_for_historical_three_split_report(self):
        self.status = deepcopy(self.fixture.candidate)
        self.stage = self.fixture.stage
        self.status['regression'] = {'required':True, 'evaluation':None}
        self.assertIn('regression_missing', self.build()['blockers'])
        self.status['regression']['required'] = False
        self.assertTrue(self.build()['ready'])

    def test_optional_dataset_and_regression_status_compose(self):
        self.status['dataset'] = {'required':True, 'bound':True, 'digest':'f'*64}
        self.assertTrue(self.build()['ready'])
        self.status['unexpected'] = True
        with self.assertRaises(ValueError): self.build()

    def test_metrics_and_decision_are_recomputed(self):
        for field in ('metrics', 'decision'):
            original = deepcopy(self.status)
            self.status['regression']['evaluation'][field]['forged'] = True
            self.assertIn('regression_evidence_mismatch', self.build()['blockers'])
            self.status = original
        self.status['regression']['evaluation'] = self.evidence(self.regression, evaluator='generator')
        self.assertIn('regression:independent_receipt_required', self.build()['blockers'])

    def test_independently_valid_reports_must_match_all_holdout_bindings(self):
        for field, value in (('candidate_id','other'), ('task_type','reasoning'),
                             ('manifest', replace(self.manifest, discovery=('other-discovery',)))):
            self.status['regression']['evaluation'] = self.evidence(replace(self.regression, **{field:value}))
            self.assertIn('regression_invalid', self.build()['blockers'], field)
        for field, value in (('sampling_digest','changed'), ('max_tokens',101)):
            model = replace(self.regression.pairs[0].baseline.model, **{field:value})
            pair = self.regression.pairs[0]
            changed = replace(self.regression, pairs=(replace(pair,
                baseline=replace(pair.baseline, model=model), candidate=replace(pair.candidate, model=model)),))
            self.status['regression']['evaluation'] = self.evidence(changed)
            self.assertIn('regression_invalid', self.build()['blockers'], field)

    def test_cue_and_profile_are_bound_even_for_valid_independent_verdict(self):
        pair = self.regression.pairs[0]
        changed = replace(self.regression, cue_digest='b'*64, pairs=(replace(pair,
            candidate=replace(pair.candidate, cue_digest='b'*64)),))
        self.status['regression']['evaluation'] = self.evidence(changed)
        self.assertIn('regression_invalid', self.build()['blockers'])
        model = replace(pair.baseline.model, profile_key='c'*64)
        changed = replace(self.regression, profile_key='c'*64, pairs=(replace(pair,
            baseline=replace(pair.baseline, model=model), candidate=replace(pair.candidate, model=model)),))
        self.status['regression']['evaluation'] = self.evidence(changed)
        self.assertIn('regression_invalid', self.build()['blockers'])

    def test_failed_retained_capability_and_malformed_report_fail_closed(self):
        pair = self.regression.pairs[0]
        changed = replace(self.regression, pairs=(replace(pair, candidate=replace(pair.candidate, correct=False)),))
        self.status['regression']['evaluation'] = self.evidence(changed)
        self.assertIn('regression:retained_capability_loss', self.build()['blockers'])
        self.status['regression']['evaluation'] = {}
        self.assertIn('regression_invalid', self.build()['blockers'])
        self.status['regression'] = {'required':1, 'evaluation':None}
        with self.assertRaises(ValueError): self.build()


if __name__ == '__main__':
    unittest.main()
