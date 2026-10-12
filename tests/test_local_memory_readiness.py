"""Readiness transport fixtures: never contact a local or remote model."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('readiness', Path(__file__).parents[1] / 'scripts/probe_local_memory_readiness.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
DIGEST = 'a' * 64


class LocalMemoryReadinessTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.preload = {'model': probe.MODEL, 'response': '', 'done': True,
                        'load_duration': 100, 'total_duration': 200}

    def transport(self, request, timeout):
        self.calls.append((request, timeout))
        if isinstance(request, str):
            self.assertEqual(timeout, 5)
            return io.BytesIO(json.dumps({'models': [{'name': probe.MODEL, 'digest': DIGEST}]}).encode())
        body = json.loads(request.data)
        if request.full_url.endswith('/api/generate'):
            self.assertEqual(timeout, 45)
            self.assertEqual(body, {'model': probe.MODEL, 'prompt': '', 'stream': False, 'keep_alive': '2m'})
            return io.BytesIO(json.dumps(self.preload).encode())
        self.assertEqual(timeout, getattr(self, 'expected_timeout', 30))
        self.assertEqual(body['max_tokens'], getattr(self, 'expected_tokens', 32))
        self.assertEqual(body['temperature'], 0)
        evidence = json.loads(body['messages'][1]['content'])
        record = json.loads(evidence['evidence_jsonl'])
        self.assertEqual(record['source_id'], 'readiness-source')
        self.assertEqual(record['evidence'], 'Synthetic readiness marker is READY42.')
        self.assertNotIn('READY42', evidence['query'])
        return io.BytesIO(json.dumps({'model': probe.MODEL, 'choices': [{'finish_reason': 'stop',
               'message': {'role': 'assistant', 'content': 'READY42 readiness-source'}}],
               'usage': {'prompt_tokens': 100, 'completion_tokens': 8, 'total_tokens': 108}}).encode())

    def test_single_preload_and_real_gateway_probe_success(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=self.transport):
            report = probe.run(DIGEST)
        self.assertEqual(report['status'], 'ready', report)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(report['probe']['diagnostic_score'], 1)
        self.assertEqual(report['preload']['load_duration_nanoseconds'], 100)
        self.assertTrue(report['diagnostic_only'])
        self.assertEqual(report['accepted_completions'], 1)
        self.assertTrue(report['preload_attempted'])
        self.assertTrue(report['inference_attempted'])
        self.assertEqual(len(report['source_sha256']), 4)

    def test_preload_invalid_or_generated_content_never_infers(self):
        for invalid in ({}, {'done': False}, {'model': 'other'}, {'response': 'generated'},
                        {'load_duration': -1}, {'total_duration': True}):
            self.calls.clear()
            self.preload = {'model': probe.MODEL, 'response': '', 'done': True}
            self.preload.update(invalid)
            if invalid == {}:
                self.preload = {}
            with patch('urllib.request.OpenerDirector.open', side_effect=self.transport):
                report = probe.run(DIGEST)
            self.assertEqual(report['failure_stage'], 'preload')
            self.assertEqual(report['failure_reason'], 'invalid_response')
            self.assertEqual(len(self.calls), 2)
            self.assertNotIn('probe', report)

    def test_oversized_preload_rejected(self):
        with patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'x' * 65537)):
            with self.assertRaises(ValueError):
                probe.preload()

    def test_preload_timeout_no_retry_and_sanitized(self):
        with patch.object(probe, 'metadata', return_value={'model': probe.MODEL, 'digest': DIGEST}), patch(
                'urllib.request.OpenerDirector.open', side_effect=TimeoutError('sensitive')) as network:
            report = probe.run(DIGEST)
        self.assertEqual(network.call_count, 1)
        self.assertEqual(report['failure_stage'], 'preload')
        self.assertEqual(report['failure_reason'], 'timeout')
        self.assertGreaterEqual(report['failure_stage_seconds'], 0)
        self.assertTrue(report['preload_attempted'])
        self.assertFalse(report['inference_attempted'])
        self.assertEqual(report['accepted_completions'], 0)
        self.assertNotIn('sensitive', json.dumps(report))

    def test_digest_mismatch_never_preloads(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=self.transport):
            report = probe.run('b' * 64)
        self.assertEqual(report['failure_stage'], 'metadata_before')
        self.assertEqual(len(self.calls), 1)

    def test_digest_drift_discards_output(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=self.transport), patch.object(probe, 'metadata', side_effect=[
                {'model': probe.MODEL, 'digest': DIGEST}, {'model': probe.MODEL, 'digest': 'b' * 64}]):
            report = probe.run(DIGEST)
        self.assertEqual(report['failure_stage'], 'metadata_after')
        self.assertNotIn('probe', report)

    def test_inference_timeout_retains_stage_and_does_not_retry(self):
        def transport(request, timeout):
            if not isinstance(request, str) and request.full_url.endswith('/v1/chat/completions'):
                raise TimeoutError('sensitive')
            return self.transport(request, timeout)
        with patch('urllib.request.OpenerDirector.open', side_effect=transport) as network:
            report = probe.run(DIGEST)
        self.assertEqual(network.call_count, 3)
        self.assertEqual(report['failure_stage'], 'approved_probe')
        self.assertEqual(report['failure_reason'], 'timeout')
        self.assertNotIn('sensitive', json.dumps(report))

    def test_redirect_and_proxy_protection(self):
        with patch.object(probe, 'build_opener') as build:
            build.return_value.open.side_effect = HTTPError('secret', 302, 'secret', {}, None)
            with self.assertRaises(HTTPError):
                probe.preload()
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], probe._NoRedirect)
        self.assertIsNone(handlers[1].redirect_request(None, None, 302, '', {}, 'https://example.org'))

    def test_cli_reserves_before_network_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            path.write_text('keep')
            with patch.object(probe, 'run') as run:
                with self.assertRaises(FileExistsError):
                    probe.main(['--output', str(path), '--expected-digest', DIGEST])
                run.assert_not_called()
            self.assertEqual(path.read_text(), 'keep')

    def test_invalid_digest_never_contacts_network(self):
        with patch('urllib.request.OpenerDirector.open') as network:
            for digest in ('', 'short', 'A' * 64, None):
                with self.assertRaises(ValueError):
                    probe.run(digest)
            network.assert_not_called()

    def test_cpu_research_explicit_budget_and_gateway_execution(self):
        self.expected_timeout, self.expected_tokens = 90, 128
        with patch('urllib.request.OpenerDirector.open', side_effect=self.transport):
            report = probe.run(DIGEST, cpu_research=True)
        self.assertEqual(report['status'], 'ready', report)
        self.assertEqual(report['runtime_profile'], 'cpu_research')
        self.assertEqual(report['inference_timeout_seconds'], 90)
        self.assertEqual(report['max_output_tokens'], 128)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(report['accepted_completions'], 1)

    def test_invalid_cpu_choice_prevents_network(self):
        with patch('urllib.request.OpenerDirector.open') as network:
            for choice in ('true', 1, None):
                with self.assertRaises(ValueError):
                    probe.run(DIGEST, cpu_research=choice)
            network.assert_not_called()

    def test_output_limit_detail_is_preserved_without_accepting_answer(self):
        def transport(request, timeout):
            response = self.transport(request, timeout)
            if not isinstance(request, str) and request.full_url.endswith('/v1/chat/completions'):
                data = json.loads(response.getvalue())
                data['choices'][0]['finish_reason'] = 'length'
                return io.BytesIO(json.dumps(data).encode())
            return response
        with patch('urllib.request.OpenerDirector.open', side_effect=transport):
            report = probe.run(DIGEST)
        self.assertEqual(report['failure_detail'], 'output_limit')
        self.assertEqual(report['accepted_completions'], 0)
        self.assertNotIn('probe', report)
