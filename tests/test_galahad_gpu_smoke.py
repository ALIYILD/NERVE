"""Probe transport tests use a synthetic HTTP fixture, never a GPU runtime."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
from pathlib import Path
from threading import Thread
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('runtime_probe', Path(__file__).parents[1] / 'scripts/galahad_gpu_smoke.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def completion(cached=0):
    return {'model': 'synthetic-model', 'choices': [{'text': 'synthetic-answer',
        'logprobs': {'tokens': ['synthetic-token'], 'token_logprobs': [-0.125]}}],
        'usage': {'prompt_tokens': 1024, 'completion_tokens': 1, 'total_tokens': 1025,
                  'prompt_tokens_details': {'cached_tokens': cached}}}


class RuntimeProbeTests(unittest.TestCase):
    def test_origin_policy_and_no_redirect_forwarding(self):
        for origin in ('http://example.com', 'http://localhost:8000', 'https://a:b@example.com',
                       'https://example.com/path', 'https://example.com/?credential=x'):
            with self.assertRaises(ValueError):
                probe.endpoint_origin(origin, True)
        self.assertEqual(probe.endpoint_origin('http://127.0.0.1:8000', True), 'http://127.0.0.1:8000')
        self.assertIsNone(probe._NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.test'))

    def test_prompt_is_bounded_run_specific_and_reproducible(self):
        first = probe.request_fixture('a'*32, 'synthetic-model')
        self.assertEqual(first, probe.request_fixture('a'*32, 'synthetic-model'))
        self.assertNotEqual(first, probe.request_fixture('b'*32, 'synthetic-model'))
        self.assertLess(len(first['prompt']), 8192)
        self.assertEqual(first['max_tokens'], 16)

    def test_selected_metrics_omit_labels_and_ambiguous_processes(self):
        result = probe.parse_metrics('process_start_time_seconds{worker="secret-a"} 10\n'
            'process_start_time_seconds{worker="secret-b"} 20\n'
            'vllm:prefix_cache_hits_total{model="private"} 5\n'
            'unrelated_secret_metric 99\n')
        self.assertIsNone(result['process_start_time_seconds'])
        self.assertEqual(result['vllm:prefix_cache_hits_total'], 5)
        self.assertNotIn('private', json.dumps(result))

    def test_missing_logprobs_and_cached_usage_are_unknown_not_success(self):
        value = completion()
        del value['choices'][0]['logprobs']
        del value['usage']['prompt_tokens_details']
        report = probe.response_observation(value)
        self.assertIsNone(report['selected_token_logprobs_sha256'])
        self.assertIsNone(report['cached_tokens_reported'])
        self.assertNotIn('synthetic-answer', json.dumps(report))

    def test_malformed_usage_and_duplicate_json_rejected(self):
        for cached in (True, -1, 1025, '100'):
            with self.assertRaises(ValueError):
                probe.response_observation(completion(cached))
        with self.assertRaises(ValueError):
            probe._parse_json('{"model":"a","model":"b"}')
        with self.assertRaises(ValueError):
            probe._parse_json('{"value":NaN}')

    def test_real_http_capture_and_comparison_do_not_claim_gpu_or_galahad(self):
        class Fixture(BaseHTTPRequestHandler):
            process_start = 100
            requests = []
            def log_message(self, *_):
                pass
            def do_GET(self):
                self.send_response(200); self.end_headers()
                self.wfile.write(f'process_start_time_seconds {self.process_start}\n'.encode())
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.requests.append((self.path, self.headers.get('Authorization'), body))
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps(completion(1024 if len(self.requests) > 1 else 0)).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            options = dict(endpoint=f'http://127.0.0.1:{server.server_port}',
                model='synthetic-model', model_revision='fixture-revision-1', run_id='a'*32,
                allow_loopback_http=True, token='private-test-token', timeout=2)
            cold = probe.capture(**options, phase='cold')
            Fixture.process_start = 200  # Simulated telemetry; not an engine restart.
            restored = probe.capture(**options, phase='after-restart')
            report = probe.compare(cold, restored)
            self.assertTrue(report['output_matches'])
            self.assertTrue(report['selected_token_logprobs_match'])
            self.assertTrue(report['reported_server_process_start_increased'])
            self.assertTrue(report['after_reports_cached_tokens'])
            self.assertEqual(report['kv_release_gate'], 'blocked')
            self.assertFalse(report['full_engine_restart_verified'])
            self.assertFalse(report['tensor_identity_verified'])
            self.assertFalse(report['galahad_attribution_verified'])
            self.assertEqual(Fixture.requests[0][0], '/v1/completions')
            self.assertEqual(Fixture.requests[0][1], 'Bearer private-test-token')
            self.assertEqual(Fixture.requests[0][2], Fixture.requests[1][2])
            self.assertNotIn('private-test-token', json.dumps(cold))
            self.assertNotIn('synthetic-answer', json.dumps(cold))
            tampered = deepcopy(restored)
            tampered['request_sha256'] = 'b'*64
            with self.assertRaises(ValueError):
                probe.compare(cold, tampered)
            with self.assertRaises(ValueError):
                probe.compare(restored, cold)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_cli_never_overwrites_evidence_or_echoes_network_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'observation.json'
            output.write_text('keep')
            args = ['capture', '--endpoint', 'https://example.test', '--model', 'test',
                    '--model-revision', 'fixed', '--run-id', 'a'*32, '--phase', 'cold', '--output', str(output)]
            with patch.object(probe, 'capture') as capture, redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(args), 2)
                capture.assert_not_called()
            self.assertEqual(output.read_text(), 'keep')
            output.unlink()
            stream = io.StringIO()
            with patch.object(probe, 'capture', side_effect=RuntimeError('secret-key')), redirect_stdout(stream):
                self.assertEqual(probe.main(args), 2)
            self.assertNotIn('secret-key', stream.getvalue())
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
