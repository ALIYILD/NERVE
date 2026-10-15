import copy
import gzip
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from historical_evidence_runtime import archived_receipt
from unittest.mock import patch
from nerve_awim.memory_gateway import recovery_gain_diagnostic as diagnostic

ROOT = Path(__file__).resolve().parents[1]


@archived_receipt
class RecoveryGainDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = gzip.decompress((ROOT/'docs/galahad/evidence/evidence-gated-study-v1.json.gz').read_bytes())
        cls.report = json.loads(cls.raw)
        cls.result = diagnostic.analyze(cls.report)

    def test_actual_training_roster_and_fixed_intervals(self):
        self.assertEqual(self.result['training_episodes'],128)
        self.assertEqual(len(self.result['intervals']),16)
        self.assertEqual(len(self.result['recoveries']),64)
        self.assertEqual(len(self.result['groups']),16)
        self.assertEqual(self.result['new_episodes'],0)
        self.assertFalse(self.result['heldout_outcomes_analyzed'])
        self.assertFalse(self.result['candidate_improvement_claimed'])
        for interval in self.result['intervals']:
            self.assertEqual(interval['steps'],8*(interval['end_step_exclusive']-interval['start_step']))
            self.assertAlmostEqual(interval['paired_goal_delta'],interval['mean_goal_error']-interval['control_mean_goal_error'])

    def test_global_recovery_age_not_renumbered_window_age(self):
        row = next(r for r in self.result['recoveries'] if r['seed']==41006 and r['scenario']=='drift' and r['arm']=='gated_retain_h1')
        self.assertEqual(row['recovery_step'],53)
        self.assertEqual(row['last_gain_change_age'],18)
        self.assertEqual(row['last_informative_update_age'],18)
        self.assertEqual([timestamp for timestamp,value in row['recorded_recovery_window']],[-4,-3,-2,-1])
        self.assertAlmostEqual(row['gain_at_recovery'],.4902090050909597)

    def test_groups_reconcile_weighted_episode_deltas(self):
        for group in self.result['groups']:
            records = [r for r in self.result['recoveries'] if all(r[k]==group[k] for k in ('scenario','arm','elevated_gain'))]
            count = sum(r['post_recovery_controller_steps'] for r in records)
            self.assertEqual(group['episodes'],len(records)); self.assertEqual(group['controller_steps'],count)
            if count:
                expected = sum(r['paired_goal_delta']*r['post_recovery_controller_steps'] for r in records)/count
                self.assertAlmostEqual(group['paired_goal_delta'],expected)
            else: self.assertIsNone(group['paired_goal_delta'])
        group = next(g for g in self.result['groups'] if g['scenario']=='drift' and g['arm']=='gated_retain_h1' and g['elevated_gain'])
        self.assertEqual(group['episodes'],3); self.assertEqual(group['controller_steps'],80)
        self.assertAlmostEqual(group['paired_goal_delta'],.028731,places=6)

    def test_missing_duplicate_changed_identity_rejected(self):
        for mutation in ('missing','duplicate','seed'):
            report = copy.deepcopy(self.report)
            if mutation=='missing': report['rows'].pop()
            elif mutation=='duplicate': report['rows'][-1]=copy.deepcopy(report['rows'][0])
            else: report['rows'][0]['episode']['seed']=46001
            with self.assertRaises(ValueError): diagnostic.analyze(report)

    def test_tampered_trace_and_learning_evidence_rejected(self):
        for mutation in ('goal','samples','recovery'):
            report = copy.deepcopy(self.report)
            row = next(r for r in report['rows'] if r['arm']=='gated_retain_h1')
            if mutation=='goal': row['episode']['trace'][60]['goal_error']=99.
            elif mutation=='samples': row['learning_evidence'][53]['samples']=[[999,999.]]
            else: row['episode']['recovery_events'][0]['step']=60
            with self.assertRaises(ValueError): diagnostic.analyze(report)

    def test_heldout_payload_is_never_analyzed(self):
        report = copy.deepcopy(self.report)
        report['rows'].append({'split':'holdout','never_access':'private withheld data'})
        self.assertEqual(diagnostic.analyze(report),self.result)

    def test_receipt_validation_and_snapshot_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'report.json'; path.write_bytes(self.raw)
            with patch.object(diagnostic.study,'validate_receipt') as validate:
                result = diagnostic.run(temp,'claims','coordinator','journal')
                validate.assert_called_once_with(temp,'claims','coordinator','journal')
                self.assertEqual(result['source_receipt_sha256'],sha256(self.raw).hexdigest())
                self.assertEqual({k:v for k,v in result.items() if k not in ('source_receipt_sha256','source_sha256')},self.result)
            with patch.object(diagnostic.study,'validate_receipt',side_effect=lambda *a:path.write_text('{}')):
                with self.assertRaisesRegex(ValueError,'study_changed'): diagnostic.run(temp,'claims','coordinator','journal')
            path.write_bytes(self.raw)
            with patch.object(diagnostic.study,'validate_receipt'), patch.object(diagnostic,'_sources',side_effect=[{'a':1},{'a':2}]):
                with self.assertRaisesRegex(ValueError,'source_changed'): diagnostic.run(temp,'claims','coordinator','journal')
