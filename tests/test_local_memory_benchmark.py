"""Transport fixtures only: these tests never contact an actual local model."""
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('local_memory_benchmark', Path(__file__).parents[1] / 'scripts/benchmark_local_memory.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
DIGEST = 'a' * 64


class LocalMemoryStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'claim.sqlite'
        self.calls = []

    def transport(self, request, timeout):
        if isinstance(request, str):
            self.assertTrue(request.endswith('/api/tags'))
            return io.BytesIO(json.dumps({'models': [{'name': bench.MODEL, 'digest': DIGEST}]}).encode())
        payload = json.loads(request.data)
        self.calls.append(payload)
        self.assertEqual(payload['max_tokens'], 128)
        self.assertEqual(payload['temperature'], 0)
        evidence = json.loads(payload['messages'][1]['content'])
        record = json.loads(evidence['evidence_jsonl'].strip())
        output = record['evidence'] + ' ' + record['source_id']
        return io.BytesIO(json.dumps({'model': bench.MODEL, 'choices': [{'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': output}}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}}).encode())

    def test_exact_eight_calls_both_arms_and_no_answer_in_control(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=self.transport):
            report = bench.run(self.database, 'first', DIGEST)
        self.assertEqual(report['status'], 'complete', report)
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(report['scores'], {'relevant': 4, 'control': 0})
        self.assertEqual([r['arm'] for r in report['rows']], ['relevant', 'control', 'control', 'relevant'] * 2)
        for row, payload in zip(report['rows'], self.calls):
            data = json.loads(payload['messages'][1]['content'])
            self.assertNotIn(row['expected_code'], data['query'])
            if row['arm'] == 'control':
                self.assertNotIn(row['expected_code'], json.dumps(payload))
        with patch('urllib.request.OpenerDirector.open') as network:
            with self.assertRaisesRegex(ValueError, 'already consumed'):
                bench.run(self.database, 'renamed', DIGEST)
            network.assert_not_called()

    def test_preflight_pin_mismatch_consumes_dataset_without_completion(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=self.transport):
            report = bench.run(self.database, 'bad-pin', 'b' * 64)
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertEqual(self.calls, [])
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT status FROM local_model_studies').fetchone()[0], 'failed_consumed')

    def test_postflight_digest_drift_invalidates_entire_study(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=self.transport), patch.object(bench, 'metadata',
                side_effect=[{'model': bench.MODEL, 'digest': DIGEST}, {'model': bench.MODEL, 'digest': 'b' * 64}]):
            report = bench.run(self.database, 'drift', DIGEST)
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertNotIn('scores', report)

    def test_error_stops_without_retry_and_is_sanitised(self):
        with patch.object(bench, 'metadata', return_value={'model': bench.MODEL, 'digest': DIGEST}), patch(
                'urllib.request.OpenerDirector.open', side_effect=TimeoutError('secret')) as network:
            report = bench.run(self.database, 'timeout', DIGEST)
        self.assertEqual(network.call_count, 1)
        self.assertEqual(report['status'], 'failed_consumed')
        self.assertNotIn('secret', json.dumps(report))

    def test_metadata_rejects_malformed_missing_duplicate_and_oversized(self):
        for data in ({}, {'models': []}, {'models': [{'name': bench.MODEL, 'digest': 'short'}]},
                     {'models': [{'name': bench.MODEL, 'digest': DIGEST}] * 2}):
            with patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(json.dumps(data).encode())):
                with self.assertRaises(ValueError):
                    bench.metadata()
        with patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'x' * 262145)):
            with self.assertRaises(ValueError):
                bench.metadata()

    def test_invalid_pin_and_memory_claim_rejected_before_network(self):
        with patch('urllib.request.OpenerDirector.open') as network:
            for digest in ('', 'abc', 'A' * 64):
                with self.assertRaises(ValueError):
                    bench.run(self.database, 'invalid', digest)
            with self.assertRaises(ValueError):
                bench.run(':memory:', 'invalid', DIGEST)
            network.assert_not_called()
