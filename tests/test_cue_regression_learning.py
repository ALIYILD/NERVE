"""Persisted regression guardrails and irreversible scoped cutover, offline only."""
from dataclasses import asdict, replace
import json
import unittest

import test_cue_learning as fixtures
from nerve_awim.cue_dataset import parse_dataset_json
from nerve_awim.cue_evaluation import DatasetManifest, Observation, PairedResult
from nerve_awim.cue_learning import GovernedCueCoordinator


class CueRegressionLearningTests(unittest.TestCase):
    setUp = fixtures.CueLearningTests.setUp
    propose = fixtures.CueLearningTests.propose
    pairs = fixtures.CueLearningTests.pairs
    passed = fixtures.CueLearningTests.passed
    activate = fixtures.CueLearningTests.activate
    select = fixtures.CueLearningTests.select

    def regression_candidate(self):
        self.manifest = replace(self.manifest, regression=('regression-0', 'regression-1'))
        return self.propose()

    def regression_pairs(self, *, loss=False, synthetic=False):
        return tuple(PairedResult(
            Observation(task, self.model, True, True, 1., 10, .01, task+'b', synthetic, '', 'baseline'),
            Observation(task, self.model, not loss, True, 1., 9, .009, task+'c', synthetic,
                        self.cue.content_hash, 'candidate')) for task in self.manifest.regression)

    def regression(self, candidate, **changes):
        return self.cce.evaluate_regression(self.actors['evaluator'], candidate,
                                           self.regression_pairs(**changes), evaluator_id='independent')

    def cutover(self):
        return self.cce.reserve_study(self.actors['trainer'],
            DatasetManifest(('new-discovery',), ('new-selection',), ('new-holdout',), ('regression-cutover',)))

    def test_gate_required_before_holdout_and_persists_across_restart_activation(self):
        candidate = self.regression_candidate()
        with self.assertRaises(PermissionError):
            self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='independent')
        stored = self.regression(candidate)
        self.assertTrue(stored['decision']['eligible'])
        status = self.cce.status(self.actors['auditor'], candidate)
        self.assertEqual(status['status'], 'pending')
        self.assertTrue(status['regression']['required'])
        self.assertEqual(status['regression']['evaluation']['report']['split'], 'regression')
        self.cce = GovernedCueCoordinator(self.engine, enabled=True, clock=lambda: self.now)
        self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='independent')
        self.activate(candidate)
        self.assertEqual(self.select().cue.cue_id, self.cue.cue_id)
        with self.assertRaises(ValueError):
            self.regression(candidate)

    def test_retained_capability_loss_is_durable_rejection_without_holdout(self):
        candidate = self.regression_candidate()
        result = self.regression(candidate, loss=True)
        self.assertIn('retained_capability_loss', result['decision']['reasons'])
        self.assertEqual(self.cce.status(self.actors['auditor'], candidate)['status'], 'rejected')
        with self.assertRaises(ValueError):
            self.regression(candidate)
        with self.assertRaises(ValueError):
            self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='independent')
        with self.assertRaises(PermissionError):
            self.activate(candidate)

    def test_self_review_cannot_persist_a_passing_gate(self):
        candidate = self.regression_candidate()
        result = self.cce.evaluate_regression(self.actors['evaluator'], candidate,
            self.regression_pairs(), evaluator_id='generator')
        self.assertFalse(result['decision']['eligible'])
        self.assertEqual(self.cce.status(self.actors['auditor'], candidate)['status'], 'rejected')

    def test_preregistered_inference_configuration_and_scope_are_enforced(self):
        candidate = self.regression_candidate()
        changed = tuple(PairedResult(replace(pair.baseline, model=replace(self.model, temperature=.9)),
                                   replace(pair.candidate, model=replace(self.model, temperature=.9)))
                        for pair in self.regression_pairs())
        with self.assertRaises(ValueError):
            self.cce.evaluate_regression(self.actors['evaluator'], candidate, changed, evaluator_id='independent')
        self.assertIsNone(self.cce.status(self.actors['auditor'], candidate)['regression']['evaluation'])
        with self.assertRaises(PermissionError):
            self.cce.evaluate_regression(self.actors['trainer'], candidate, self.regression_pairs(), evaluator_id='independent')
        foreign = self.authority.issue('other', 'agent', 'evaluator')
        with self.assertRaises(LookupError):
            self.cce.evaluate_regression(foreign, candidate, self.regression_pairs(), evaluator_id='independent')

    def test_cutover_blocks_old_pending_candidate_and_unconsumed_reservation(self):
        candidate = self.propose()
        old_manifest = DatasetManifest(('oldd',), ('olds',), ('oldh',))
        old_reservation = self.cce.reserve_study(self.actors['trainer'], old_manifest)
        self.cutover()
        with self.assertRaises(PermissionError):
            self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='independent')
        with self.assertRaises(ValueError):
            self.cce.propose(self.actors['trainer'], replace(self.cue, version=2), self.profile, 'research',
                old_manifest, generator_id='generator', model_config=self.model, reservation=old_reservation)
        with self.assertRaises(ValueError):
            self.cce.reserve_study(self.actors['trainer'], DatasetManifest(('freshd',), ('freshs',), ('freshh',)))
        self.assertTrue(self.cce.status(self.actors['auditor'], candidate)['regression']['required'])

    def test_cutover_blocks_old_passed_activation(self):
        candidate = self.passed()
        self.cutover()
        with self.assertRaises(PermissionError):
            self.activate(candidate)

    def test_cutover_filters_old_active_route_without_destroying_audit(self):
        candidate = self.passed()
        self.activate(candidate)
        self.assertIsNotNone(self.select().cue)
        self.cutover()
        self.assertIsNone(self.select().cue)
        self.assertEqual(self.cce.route_status(self.actors['runtime'], self.profile, 'research')['active'], candidate)
        self.assertEqual(self.cce.status(self.actors['auditor'], candidate)['status'], 'approved')

    def test_scope_cutover_survives_restart_and_earlier_contract_rows(self):
        self.cutover()
        with self.engine._db() as con:
            con.execute("UPDATE cce_regression_studies SET contract='earlier-contract'")
        self.cce = GovernedCueCoordinator(self.engine, enabled=True, clock=lambda: self.now)
        with self.assertRaisesRegex(ValueError, 'regression'):
            self.cce.reserve_study(self.actors['trainer'], self.manifest)

    def test_malformed_persisted_gate_prevents_active_selection(self):
        candidate = self.regression_candidate()
        self.regression(candidate)
        self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='independent')
        self.activate(candidate)
        with self.engine._db() as con:
            con.execute('UPDATE cce_regression_reports SET evidence=? WHERE candidate=?', ('{', candidate))
        self.assertIsNone(self.select().cue)

    def test_tampered_metrics_or_report_binding_prevents_activation(self):
        candidate = self.regression_candidate()
        self.regression(candidate)
        self.cce.evaluate(self.actors['evaluator'], candidate, self.pairs(), evaluator_id='independent')
        with self.engine._db() as con:
            raw = json.loads(con.execute('SELECT evidence FROM cce_regression_reports WHERE candidate=?', (candidate,)).fetchone()[0])
            raw['metrics']['candidate']['accuracy'] = .5
            con.execute('UPDATE cce_regression_reports SET evidence=? WHERE candidate=?', (json.dumps(raw), candidate))
        with self.assertRaises(PermissionError):
            self.activate(candidate)

    def test_same_regression_suite_reusable_with_fresh_holdout_but_cannot_move_splits(self):
        first = DatasetManifest(('d1',), ('s1',), ('h1',), ('r1',))
        second = DatasetManifest(('d2',), ('s2',), ('h2',), ('r1',))
        self.cce.reserve_study(self.actors['trainer'], first)
        self.cce.reserve_study(self.actors['trainer'], second)
        with self.assertRaises(ValueError):
            self.cce.reserve_study(self.actors['trainer'], DatasetManifest(('r1',), ('s3',), ('h3',), ('r2',)))

    def test_legacy_empty_regression_serialization_matches_semantically(self):
        reservation = self.cce.reserve_study(self.actors['trainer'], self.manifest)
        with self.engine._db() as con:
            # Simulate a briefly stored explicit empty trailing regression field.
            con.execute('UPDATE cce_studies SET manifest=? WHERE id=?', (json.dumps(asdict(self.manifest)), reservation))
        candidate = self.cce.propose(self.actors['trainer'], self.cue, self.profile, 'research', self.manifest,
            generator_id='generator', model_config=self.model, reservation=reservation)
        self.assertFalse(self.cce.status(self.actors['auditor'], candidate)['regression']['required'])

    def test_dataset_regression_content_is_reserved_and_reusable_only_in_same_split(self):
        def record(suffix):
            return {'schema_version': 2, 'dataset_id': 'data'+suffix,
                'source': {'uri': 'fixture:local', 'revision': 'v1'},
                'splits': {split: [{'task_id': split + (suffix if split == 'holdout' else ''),
                    'family_id': split + '-family' + (suffix if split == 'holdout' else ''),
                    'instruction': split + '-text' + (suffix if split == 'holdout' else ''), 'expected': 'x'}]
                    for split in ('discovery', 'selection', 'holdout', 'regression')}}
        first = parse_dataset_json(json.dumps(record('1')))
        self.cce.reserve_dataset(self.actors['trainer'], first)
        self.cce.reserve_dataset(self.actors['trainer'], parse_dataset_json(json.dumps(record('2'))))
        with self.engine._db() as con:
            count = con.execute("SELECT COUNT(*) FROM cce_dataset_fingerprints WHERE split='regression'").fetchone()[0]
            self.assertEqual(count, 2)
        moved = record('3')
        moved['splits']['discovery'][0]['instruction'] = 'regression-text'
        moved['splits']['regression'][0]['instruction'] = 'fresh-regression'
        with self.assertRaises(ValueError):
            self.cce.reserve_dataset(self.actors['trainer'], parse_dataset_json(json.dumps(moved)))


if __name__ == '__main__':
    unittest.main()
