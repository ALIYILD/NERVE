import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from nerve_awim.uncertainty import evaluation as ev


class UncertaintyEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'nerve.sqlite3'
    def test_frozen_paired_family_splits(self):
        cases,manifest=ev.load_suite()
        self.assertEqual(len(cases),36)
        self.assertEqual(manifest['policy']['accuracy_noninferiority_margin'],.02)
        for split in ('train','selection','sealed-final'):
            selected=[c for c in cases if c['split']==split]
            self.assertEqual(len(selected),12)
            for family in {c['family'] for c in selected}:
                pair=[c for c in selected if c['family']==family]
                self.assertEqual([c['source_count'] for c in pair],[2,2])
                self.assertEqual({c['labels']['conflict'] for c in pair},{True,False})
        with patch.object(ev,'MANIFEST_HASH','tampered'):
            with self.assertRaisesRegex(ValueError,'integrity'):ev.load_suite()
    def test_actual_hermes_baseline_and_full_guard(self):
        case=next(c for c in ev.load_suite('selection')[0] if c['labels']['material'])
        baseline=ev.run_case(case,'A');prompt=ev.run_case(case,'B')
        preserved=ev.run_case(case,'C');full=ev.run_case(case,'D')
        self.assertTrue(baseline['unsupported_certainty']);self.assertTrue(prompt['unsupported_certainty'])
        self.assertTrue(preserved['identified']);self.assertTrue(preserved['unsupported_certainty'])
        self.assertFalse(full['unsupported_certainty']);self.assertFalse(full['policy_violation'])
        self.assertTrue(full['surfaced']);self.assertFalse(full['answered'])
        self.assertTrue(all(full['boundaries'][s] for s in full['boundaries']))
        self.assertEqual(full['claimed_closures'],0)
    def test_verification_requires_real_registered_evidence(self):
        case=next(c for c in ev.load_suite('train')[0] if c['labels']['resolvable'])
        row=ev.run_case(case,'D')
        self.assertEqual(row['claimed_closures'],1)
        self.assertEqual(row['justified_closures'],1)
        self.assertEqual(row['calls']['verification'],1)
        self.assertFalse(row['material_open']);self.assertTrue(row['answered'])
    def test_missing_labels_and_zero_denominators_remain_null(self):
        case=ev.load_suite('train')[0][0];row=ev.run_case(case,'D')
        row['labels']={**row['labels'],'conflict':None,'subjective_materiality':None}
        metrics=ev.metrics([row])
        self.assertIsNone(metrics['identify_recall']['value'])
        self.assertIsNone(metrics['verified_resolution_precision']['value'])
        self.assertIsNone(metrics['human_label_disagreement'])
        self.assertEqual(metrics['missing_conflict_labels'],1)
        self.assertEqual(metrics['missing_subjective_labels'],1)
    def test_cluster_interval_refuses_pseudoreplication(self):
        row=ev.run_case(ev.load_suite('train')[0][0],'A')
        self.assertIsNone(ev.cluster_interval([(row,row)]*100,'success')['interval95'])
    def test_selection_freeze_sealed_and_consumption(self):
        selected=ev.evaluate(self.db)
        self.assertEqual(len(selected['cases']),48)
        self.assertFalse(selected['eligibility']['eligible'])
        self.assertEqual(selected['matched_coverage_benefit']['status'],'inconclusive')
        self.assertEqual(selected['metrics']['D']['incomplete_tasks'],0)
        ev.freeze(self.db,selected['run_id'])
        final=ev.evaluate(self.db,split='sealed-final',run_id=selected['run_id'])
        self.assertEqual(final['metrics']['D']['policy_violations']['numerator'],0)
        self.assertEqual(final['metrics']['D']['verified_resolution_precision']['value'],1)
        self.assertIsNone(final['paired_accuracy_delta']['interval95'])
        self.assertIsNone(final['accuracy_noninferiority'])
        self.assertIsNotNone(final['paired_policy_completion_delta']['interval95'])
        self.assertFalse(ev.eligibility(self.db,selected['run_id'])['eligible'])
        self.assertEqual(ev.report(self.db,selected['run_id'])['state'],'complete')
        with self.assertRaises(ValueError):ev.evaluate(self.db,split='sealed-final',run_id=selected['run_id'])
    def test_code_change_and_candidate_policy_edits_rejected(self):
        selected=ev.evaluate(self.db)
        with patch.object(ev,'code_revision',return_value='changed'):
            with self.assertRaisesRegex(ValueError,'changed'):ev.freeze(self.db,selected['run_id'])
        for candidate in ({'policy':'relaxed'},{'strategy':'arbitrary-code'},{'strategy':'retain-incumbent','margin':.9}):
            with self.assertRaises(ValueError):ev.validate_candidate(candidate)
    def test_errors_kept_in_all_arm_denominators_and_unknown_calls(self):
        with patch.object(ev,'run_case',side_effect=TimeoutError('fixture')):
            result=ev.evaluate(self.db)
        for metrics in result['metrics'].values():
            self.assertEqual(metrics['tasks'],12)
            self.assertEqual(metrics['incomplete_tasks'],12)
            self.assertEqual(metrics['task_success']['value'],0)
            self.assertIsNone(metrics['provider_errors'])
            self.assertIsNone(metrics['confident_error']['value'])
            self.assertEqual(metrics['calls']['provider_fixture']['unknown_cases'],12)
    def test_interrupted_sealed_claim_cannot_replay(self):
        selected=ev.evaluate(self.db);ev.freeze(self.db,selected['run_id'])
        with patch.object(ev,'run_case',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):ev.evaluate(self.db,split='sealed-final',run_id=selected['run_id'])
        self.assertFalse(ev.resume(self.db,selected['run_id'])['resumable'])
        with self.assertRaises(ValueError):ev.evaluate(self.db,split='sealed-final',run_id=selected['run_id'])
    def test_host_scope_is_not_argument_authority(self):
        selected=ev.evaluate(self.db)
        with patch.object(ev,'_tenant',return_value='another-host'):
            with self.assertRaises(LookupError):ev.report(self.db,selected['run_id'])

    def test_wrong_primary_value_cannot_justify_closure(self):
        case=copy.deepcopy(next(c for c in ev.load_suite('train')[0] if c['labels']['resolvable']))
        case['primary_value']=False
        engine,ledger,actor,operator=ev.host(self.db)
        _,_,conflicts=ev.populate(ledger,actor,case)
        with self.assertRaises(PermissionError):ev.verify_case(ledger,actor,operator,case,conflicts)
        self.assertNotEqual(ledger.get_conflict(actor,conflicts[0].conflict_id).status,'resolved')
    def test_ledger_retention_is_not_final_response_preservation(self):
        case=next(c for c in ev.load_suite('train')[0] if c['labels']['material'])
        result=ev.run_case(case,'C')
        self.assertEqual(result['ledger_open_count'],1)
        self.assertEqual(result['boundaries']['final'],0)
        self.assertEqual(ev.metrics([result])['preservation']['final']['value'],0)
        self.assertIsNone(ev.metrics([result])['confident_error']['value'])
        self.assertIsNone(ev.metrics([result])['task_accuracy']['value'])
