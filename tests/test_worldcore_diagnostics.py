import json
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.memory_gateway import worldcore_diagnostics as diagnostic


class WorldCoreDiagnosticTests(unittest.TestCase):
    def test_source_contract_recognizes_structural_impossibility(self):
        contract = diagnostic._source_contract()
        self.assertEqual(contract['guaranteed_consecutive_missing_steps'], 15)
        self.assertEqual(contract['max_allowed_missing_tolerance'], 12)
        self.assertEqual(contract['absolute_min_completion'], .95)

    def test_all_cases_and_durable_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'diagnosis'
            # The diagnostic must never invoke the plant evaluator/holdout.
            with patch('nerve_awim.autoresearch_v04.episode', side_effect=AssertionError('plant called')):
                report = diagnostic.run_diagnostic(root)
            self.assertEqual(report['mechanism_cases'], 33)
            self.assertEqual(report['measured_miss_calls'], 231)
            self.assertEqual(report['measured_choose_calls'], 231)
            self.assertEqual(report['simulation_episodes'], 0)
            self.assertEqual(report['holdout_calls'], 0)
            self.assertFalse(report['policy_promoted'])
            self.assertFalse(report['model_weights_trained'])
            self.assertEqual(report['structural_inference']['maximum_completion'], .6)
            self.assertFalse(report['structural_inference']['absolute_completion_gate_satisfiable'])
            self.assertFalse(report['structural_inference']['absolute_abort_gate_satisfiable'])
            self.assertEqual(report['recommendation'], 'stop_unmodified_parameter_search')
            with patch.object(diagnostic, '_case', side_effect=AssertionError('must not replay')):
                self.assertTrue(diagnostic.validate_receipt(root, report))
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                state, persisted = db.execute('SELECT status, report FROM diagnostic').fetchone()
                rows = db.execute('SELECT ordinal, max_missing, risk_aversion, status, evidence FROM cases ORDER BY ordinal').fetchall()
            self.assertEqual(state, 'complete')
            self.assertEqual(json.loads(persisted), json.loads((root / 'report.json').read_text()))
            self.assertEqual([row[0] for row in rows], list(range(1, 34)))
            self.assertEqual([(row[1], row[2]) for row in rows],
                             [(limit, risk) for limit in diagnostic.LIMITS for risk in diagnostic.RISKS])
            for ordinal, limit, risk, state, evidence in rows:
                self.assertEqual(state, 'complete')
                self.assertEqual(json.loads(evidence), report['cases'][ordinal - 1])
                self.assertEqual(json.loads(evidence)['first_sensor_unavailable_count'], limit)
                self.assertEqual(json.loads(evidence)['plant_actions'], 0)
            with self.assertRaises(FileExistsError):
                diagnostic.run_diagnostic(root)

    def test_strict_registered_case_schema(self):
        for missing, risk in ((True, .25), (2, True), (2.0, .25), (1, .25),
                              (13, .25), (2, float('nan')), (2, .5)):
            with self.subTest(missing=missing, risk=risk), self.assertRaises(ValueError):
                diagnostic._case(missing, risk)

    def test_claim_precedes_execution_and_failure_consumes_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'diagnosis'
            original = diagnostic._case

            def observed(limit, risk):
                with sqlite3.connect(root / 'ledger.sqlite') as db:
                    last = db.execute('SELECT max_missing, risk_aversion, status FROM cases ORDER BY ordinal DESC LIMIT 1').fetchone()
                self.assertEqual(last, (limit, risk, 'claimed'))
                if risk == .25:
                    raise RuntimeError('private data must not be recorded')
                return original(limit, risk)

            with patch.object(diagnostic, '_case', side_effect=observed), self.assertRaises(RuntimeError):
                diagnostic.run_diagnostic(root)
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                self.assertEqual(db.execute('SELECT status FROM diagnostic').fetchone()[0], 'failed')
                self.assertEqual(db.execute('SELECT status FROM cases ORDER BY ordinal').fetchall(),
                                 [('complete',), ('failed',)])
            self.assertNotIn('private data', (root / 'error.json').read_text())
            with self.assertRaises(FileExistsError):
                diagnostic.run_diagnostic(root)

    def test_source_drift_stops_before_case(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'diagnosis'
            with patch.object(diagnostic, '_hashes', side_effect=[{'source': 'a'}, {'source': 'b'}]), self.assertRaisesRegex(RuntimeError, 'source_drift'):
                diagnostic.run_diagnostic(root)
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM cases').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT status FROM diagnostic').fetchone()[0], 'failed')

    def test_source_drift_after_case_retains_failed_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'diagnosis'
            with patch.object(diagnostic, '_hashes', side_effect=[{'source': 'a'}] * 3 + [{'source': 'b'}]), self.assertRaisesRegex(RuntimeError, 'source_drift'):
                diagnostic.run_diagnostic(root)
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                self.assertEqual(db.execute('SELECT status FROM cases').fetchall(), [('failed',)])

    def test_unknown_evaluator_or_gate_contract_fails_closed(self):
        original = Path.read_text
        changes = (
            ('autoresearch_v04.py', '35<=t<50', '35<=t<49'),
            ('autoresearch_v04.py', 't+2,t', 't+3,t'),
            ('autoresearch_v04.py', '2<=self.max_missing<=12', '2<=self.max_missing<=16'),
            ('autoresearch_v04.py', 'STEPS=80', 'STEPS=81'),
            ('autoresearch_v05.py', 'MIN_COMPLETION=0.95', 'MIN_COMPLETION=0.5'),
            ('worldcore_v20.py', 'self.last_packet_age>=self.max_missing', 'self.last_packet_age>self.max_missing'),
        )
        for name, before, after in changes:
            def changed(path, *args, **kwargs):
                text = original(path, *args, **kwargs)
                return text.replace(before, after) if path.name == name else text
            with self.subTest(change=after), patch.object(Path, 'read_text', changed), self.assertRaises(RuntimeError):
                diagnostic._source_contract()

    def test_unexpected_controller_failure_cannot_be_success(self):
        with patch.object(diagnostic.WorldCoreV2, 'choose', side_effect=RuntimeError('no feasible action')):
            with self.assertRaisesRegex(RuntimeError, 'unexpected_guard_failure'):
                diagnostic._case(2, .25)
        with patch.object(diagnostic.WorldCoreV2, 'choose', return_value=0):
            with self.assertRaisesRegex(RuntimeError, 'sensor_guard_did_not_stop'):
                diagnostic._case(2, .25)

    def test_existing_symlink_root_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'target').mkdir()
            (root / 'link').symlink_to(root / 'target', target_is_directory=True)
            with self.assertRaises(FileExistsError):
                diagnostic.run_diagnostic(root / 'link')
            self.assertEqual(list((root / 'target').iterdir()), [])

    def test_receipt_rejects_consistently_tampered_counts_and_conclusions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'diagnosis'
            report = diagnostic.run_diagnostic(root)
            changes = [('measured_choose_calls', 230), ('policy_promoted', True),
                       ('mechanism_cases', True), ('holdout_calls', 1),
                       ('recommendation', 'deploy')]
            for key, value in changes:
                broken = deepcopy(report)
                broken[key] = value
                (root / 'report.json').write_text(diagnostic._json(broken))
                with sqlite3.connect(root / 'ledger.sqlite') as db:
                    db.execute('UPDATE diagnostic SET report=?', (diagnostic._json(broken),))
                with self.subTest(field=key), self.assertRaises(ValueError):
                    diagnostic.validate_receipt(root, broken)
            broken = deepcopy(report)
            broken['structural_inference']['maximum_completion'] = 1.0
            (root / 'report.json').write_text(diagnostic._json(broken))
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                db.execute('UPDATE diagnostic SET report=?', (diagnostic._json(broken),))
            with self.assertRaises(ValueError):
                diagnostic.validate_receipt(root, broken)

    def test_receipt_rejects_missing_or_incomplete_case(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'diagnosis'
            report = diagnostic.run_diagnostic(root)
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                db.execute("UPDATE cases SET status='claimed' WHERE ordinal=1")
            with self.assertRaises(ValueError):
                diagnostic.validate_receipt(root, report)
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                db.execute('DELETE FROM cases WHERE ordinal=1')
            with self.assertRaises(ValueError):
                diagnostic.validate_receipt(root, report)

    def test_receipt_rejects_consistent_false_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'diagnosis'
            report = diagnostic.run_diagnostic(root)
            report['cases'][0]['first_sensor_unavailable_count'] = 1
            (root / 'report.json').write_text(diagnostic._json(report))
            with sqlite3.connect(root / 'ledger.sqlite') as db:
                db.execute('UPDATE diagnostic SET report=?', (diagnostic._json(report),))
                db.execute('UPDATE cases SET evidence=? WHERE ordinal=1', (diagnostic._json(report['cases'][0]),))
            with self.assertRaises(ValueError):
                diagnostic.validate_receipt(root, report)


if __name__ == '__main__':
    unittest.main()
