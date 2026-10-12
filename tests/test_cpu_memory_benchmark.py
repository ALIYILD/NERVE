import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('cpu_memory_study_test', Path(__file__).parents[1] / 'scripts/benchmark_cpu_memory.py')
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)
DIGEST = 'a' * 64


class CPUStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / 'claims.sqlite')
        self.calls = []

    def respond(self, adapter, gateway, reader, request):
        records = gateway.retrieve(reader, request).records
        self.assertEqual(len(records), 1)
        self.assertEqual(request.limit, 1)
        case = int(request.scope.context.split('-')[1])
        arm = request.scope.context.split('-')[2]
        target, expected, decoy, other = study.CASES[case]
        self.assertIn(target, request.query)
        for marker in (expected, other, decoy):
            self.assertNotIn(marker, request.query)
        record = records[0]
        self.assertIn(expected if arm == 'relevant' else other, record.content)
        self.assertNotIn(other if arm == 'relevant' else expected, record.content)
        self.calls.append((case, arm, len(record.content)))
        with sqlite3.connect(self.db) as db:
            report = json.loads(db.execute('SELECT report FROM cpu_memory_evidence').fetchone()[0])
        self.assertEqual(report['inference_attempts'], len(self.calls))
        self.assertEqual(report['rows'][-1]['status'], 'attempted')
        output = expected + ' ' + record.source_id if arm == 'relevant' else 'unknown'
        return {'status': 'generated_requires_review', 'output': output,
                'usage': {'prompt_tokens': 30, 'completion_tokens': 5, 'total_tokens': 35}}

    def run_study(self, responder=None, metadata=None):
        with patch.object(study, 'metadata', side_effect=metadata or [{'model': study.MODEL, 'digest': DIGEST}] * 2) as meta, \
             patch.object(study, 'preload', return_value={'wall_seconds': 0}) as preload, \
             patch.object(study.LocalInferenceAdapter, 'respond', autospec=True, side_effect=responder or self.respond) as respond:
            report = study.run(self.db, 'run', DIGEST)
        return report, meta, preload, respond

    def test_matched_eight_calls_scoped_controls_and_heuristic(self):
        report, meta, preload, respond = self.run_study()
        self.assertEqual(report['status'], 'complete')
        self.assertEqual((meta.call_count, preload.call_count, respond.call_count), (2, 1, 8))
        self.assertEqual([(c, a) for c, a, _ in self.calls],
                         [(0, 'relevant'), (0, 'control'), (1, 'control'), (1, 'relevant'),
                          (2, 'relevant'), (2, 'control'), (3, 'control'), (3, 'relevant')])
        self.assertEqual(len({n for _, _, n in self.calls}), 1)
        self.assertEqual(report['counts']['relevant_grounded_extractions'], 4)
        self.assertEqual(report['counts']['control_lexical_abstention_indicators'], 4)
        self.assertEqual(report['counts']['control_unsupported_target_codes'], 0)
        for row in report['rows']:
            if row['arm'] == 'control':
                self.assertNotIn('grounded_extraction', row)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT status FROM local_model_studies').fetchone()[0], 'complete')

    def test_failure_stops_preserves_rows_no_aggregate(self):
        def respond(*args):
            if self.calls:
                raise study.InferenceUnavailable('output_limit')
            return self.respond(*args)
        report, meta, preload, calls = self.run_study(respond)
        self.assertEqual(calls.call_count, 2)
        self.assertEqual(meta.call_count, 2)
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertNotIn('counts', report)
        self.assertEqual(report['rows'][0]['status'], 'complete')
        self.assertEqual(report['rows'][1]['status'], 'failed')
        with patch.object(study, 'metadata') as network:
            with self.assertRaises(ValueError):
                study.run(self.db, 'new-name', DIGEST)
            network.assert_not_called()

    def test_identity_drift_removes_aggregate(self):
        report, *_ = self.run_study(metadata=[{'model': study.MODEL, 'digest': DIGEST}, {'model': study.MODEL, 'digest': 'b' * 64}])
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertEqual(report['identity_failure'], 'digest_drift')
        self.assertNotIn('counts', report)
        self.assertEqual(len(report['rows']), 8)

    def test_source_drift_suppresses_aggregate(self):
        with patch.object(study, '_source_hashes', side_effect=[{'file': 'before'}, {'file': 'after'}]):
            report, *_ = self.run_study()
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertEqual(report['source_failure'], 'source_drift')
        self.assertNotIn('counts', report)

    def test_failed_final_metadata_suppresses_aggregate(self):
        report, meta, _, calls = self.run_study(metadata=[{'model': study.MODEL, 'digest': DIGEST}, TimeoutError()])
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertEqual(meta.call_count, 2)
        self.assertEqual(calls.call_count, 8)
        self.assertNotIn('counts', report)

    def test_wrong_initial_digest_no_generation(self):
        report, meta, preload, calls = self.run_study(metadata=[{'model': study.MODEL, 'digest': 'b' * 64}] * 2)
        self.assertEqual(report['status'], 'failed_consumed')
        preload.assert_not_called()
        calls.assert_not_called()

    def test_output_reserved_before_network(self):
        output = Path(self.temp.name) / 'report.json'
        output.write_text('existing')
        with patch.object(study, 'run') as run:
            with self.assertRaises(FileExistsError):
                study.main(['--database', self.db, '--run-id', 'run', '--output', str(output), '--expected-digest', DIGEST])
            run.assert_not_called()
        self.assertEqual(output.read_text(), 'existing')

    def test_keyboard_interrupt_consumes_and_checkpoints(self):
        with patch.object(study, 'metadata', return_value={'model': study.MODEL, 'digest': DIGEST}) as meta, \
             patch.object(study, 'preload', return_value={}), \
             patch.object(study.LocalInferenceAdapter, 'respond', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                study.run(self.db, 'run', DIGEST)
        self.assertEqual(meta.call_count, 2)
        with sqlite3.connect(self.db) as db:
            report = json.loads(db.execute('SELECT report FROM cpu_memory_evidence').fetchone()[0])
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertEqual(report['rows'][0]['status'], 'failed')

    def test_marker_boundary_and_abstention_not_semantic_score(self):
        self.assertFalse(study._hit('MEZP-3618', 'MEZP-3618-FAKE'))
        self.assertTrue(study._hit('MEZP-3618', 'Code: MEZP-3618.'))
        def respond(*args):
            result = self.respond(*args)
            case, arm, _ = self.calls[-1]
            if arm == 'control':
                result['output'] = study.CASES[case][1] + ' ' + study.CASES[case][3] + ' unknown'
            return result
        report, *_ = self.run_study(respond)
        self.assertEqual(report['counts']['control_unsupported_target_codes'], 4)
        self.assertEqual(report['counts']['control_decoy_mentions'], 4)
        self.assertEqual(report['counts']['control_lexical_abstention_indicators'], 4)


if __name__ == '__main__':
    unittest.main()
