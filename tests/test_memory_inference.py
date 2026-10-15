"""Local HTTP contract fixtures; these tests do NOT execute a real LLM/GPU."""
import io
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nerve_awim.memory_gateway.inference import LocalInferenceAdapter
from nerve_awim.memory_gateway.contracts import MemoryRequest, MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


class InferenceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.auth = MemoryAuthority()
        self.actor = self.auth.issue('tenant', 'agent', permissions=('read', 'propose', 'approve', 'delete'))
        self.ledger = TrustedMemoryLedger(Path(self.temp.name) / 'memory.db', self.auth)
        self.gateway = MemoryGateway(self.ledger)
        self.scope = MemoryScope('tenant', 'agent', 'synthetic')
        self.request = MemoryRequest(self.scope, 'fixture')
        self.mid = self.gateway.propose(self.actor, scope=self.scope, content='fixture source evidence', source_id='source')
        self.gateway.decide(self.actor, self.mid, scope=self.scope, approve=True, evaluator_id='review')
        self.adapter = LocalInferenceAdapter(base_url='http://127.0.0.1:9001', model='fixture-model')

    def response(self, **changes):
        value = dict(model='fixture-model', choices=[dict(finish_reason='stop', message=dict(role='assistant',
            content='Synthetic fixture summary [source]'))], usage=dict(prompt_tokens=20, completion_tokens=5))
        value.update(changes)
        return value

    def transport(self, value=None, callback=None):
        value = self.response() if value is None else value
        def call(request, timeout):
            self.payload = json.loads(request.data)
            if callback:
                callback()
            return io.BytesIO(json.dumps(value).encode())
        return patch.object(self.adapter._opener, 'open', side_effect=call)

    def test_scoped_evidence_and_fixed_messages_prefill_only(self):
        with self.transport():
            result = self.adapter.respond(self.gateway, self.actor, self.request)
        self.assertEqual(self.payload['model'], 'fixture-model')
        self.assertEqual([m['role'] for m in self.payload['messages']], ['system', 'user'])
        self.assertIn('fixture source evidence', self.payload['messages'][1]['content'])
        self.assertTrue(result['review_required'])
        self.assertFalse(result['persistent_kv_restored'])
        self.assertEqual(result['records'][0]['source_id'], 'source')

    def test_no_evidence_abstains_without_network(self):
        with patch.object(self.adapter._opener, 'open') as call:
            result = self.adapter.respond(self.gateway, self.actor, MemoryRequest(self.scope, 'missing'))
            self.assertEqual(result['status'], 'abstained')
            call.assert_not_called()

    def test_revoked_source_discards_generated_output(self):
        with self.transport(callback=lambda: self.gateway.revoke(self.actor, self.mid,
                             scope=self.scope, evaluator_id='revoker')):
            with self.assertRaises(PermissionError):
                self.adapter.respond(self.gateway, self.actor, self.request)

    def test_durable_scope_revoked_during_inference_discards_output(self):
        with self.transport(callback=lambda: self.gateway.revoke_scope(self.actor,
                             scope=self.scope, evaluator_id='revoker')):
            with self.assertRaises(PermissionError):
                self.adapter.respond(self.gateway, self.actor, self.request)

    def test_concurrency_budget_fails_without_network_or_retry(self):
        for _ in range(4):
            self.assertTrue(self.adapter._slots.acquire(blocking=False))
        try:
            with patch.object(self.adapter._opener, 'open') as call:
                with self.assertRaisesRegex(RuntimeError, '^inference_unavailable$'):
                    self.adapter.respond(self.gateway, self.actor, self.request)
                call.assert_not_called()
        finally:
            for _ in range(4):
                self.adapter._slots.release()

    def test_revoked_actor_discards_generated_output(self):
        with self.transport(callback=lambda: self.auth.revoke(self.actor)):
            with self.assertRaises(PermissionError):
                self.adapter.respond(self.gateway, self.actor, self.request)

    def test_changed_model_tool_calls_role_and_finish_reason_rejected(self):
        responses = [self.response(model='other'), self.response(choices=[dict(finish_reason='tool_calls',
            message=dict(role='assistant', content='fixture', tool_calls=[{'function':'unsafe'}]))]),
            self.response(choices=[dict(finish_reason='stop', message=dict(role='system', content='fixture'))]),
            self.response(choices=[dict(finish_reason='length', message=dict(role='assistant', content='fixture'))])]
        for response in responses:
            self.adapter = LocalInferenceAdapter(base_url='http://127.0.0.1:9001', model='fixture-model')
            with self.subTest(response=response), self.transport(response):
                with self.assertRaisesRegex(RuntimeError, '^inference_unavailable$'):
                    self.adapter.respond(self.gateway, self.actor, self.request)

    def test_failures_open_circuit_without_retry_then_cooldown(self):
        with patch.object(self.adapter._opener, 'open', side_effect=TimeoutError('SENSITIVE')) as call:
            with patch('nerve_awim.memory_gateway.inference.time.monotonic', return_value=100):
                for _ in range(5):
                    with self.assertRaisesRegex(RuntimeError, '^inference_unavailable$'):
                        self.adapter.respond(self.gateway, self.actor, self.request)
                self.assertEqual(call.call_count, 3)
        with patch('nerve_awim.memory_gateway.inference.time.monotonic', return_value=131), self.transport():
            self.assertEqual(self.adapter.respond(self.gateway, self.actor, self.request)['status'], 'generated_requires_review')

    def test_oversized_response_and_usage_cap_rejected(self):
        with patch.object(self.adapter._opener, 'open', return_value=io.BytesIO(b'x'*65537)):
            with self.assertRaises(RuntimeError):
                self.adapter.respond(self.gateway, self.actor, self.request)
        with self.transport(self.response(usage={'completion_tokens': 9999})):
            with self.assertRaises(RuntimeError):
                self.adapter.respond(self.gateway, self.actor, self.request)

    def test_only_host_literal_loopback_and_bounded_config(self):
        for url in ('http://localhost:8000', 'https://127.0.0.1:8000', 'http://example.com:8000',
                    'http://127.0.0.1', 'http://user:pass@127.0.0.1:8000', 'http://127.0.0.1:8000/path'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                LocalInferenceAdapter(base_url=url, model='fixture')
        for fields in ({'max_output_tokens': True}, {'max_output_tokens': 2049}, {'timeout_seconds': float('nan')},
                       {'timeout_seconds':31}, {'model':'bad\nmodel'}):
            with self.assertRaises(ValueError):
                LocalInferenceAdapter(**dict(base_url='http://127.0.0.1:8000', model='fixture', **fields)
                    if 'model' not in fields else dict(base_url='http://127.0.0.1:8000', **fields))

    def test_real_loopback_http_contract_and_no_redirect(self):
        fixture = self
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                calls.append(self.path)
                fixture.payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if getattr(self.server, 'redirect', False):
                    self.send_response(307)
                    self.send_header('Location', '/redirect-target')
                    self.end_headers()
                else:
                    raw = json.dumps(fixture.response()).encode()
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = Thread(target=server.serve_forever, kwargs={'poll_interval':0.05}, daemon=True)
            thread.start()
            try:
                self.adapter = LocalInferenceAdapter(base_url='http://127.0.0.1:'+str(server.server_port), model='fixture-model')
                self.assertEqual(self.adapter.respond(self.gateway, self.actor, self.request)['kv_status'], 'prefill')
                server.redirect = True
                with self.assertRaises(RuntimeError):
                    self.adapter.respond(self.gateway, self.actor, self.request)
                self.assertEqual(calls, ['/v1/chat/completions', '/v1/chat/completions'])
            finally:
                server.shutdown()
                thread.join(2)


# Reuse signed-identity fixtures without inheriting/repeating the unrelated suite.
import test_memory_service as service_fixtures
import test_memory_runtime as runtime_fixtures


@unittest.skipIf(service_fixtures.jwt is None, 'PyJWT[crypto] required')
class InferenceServiceContractTests(unittest.TestCase):
    setUpClass = classmethod(service_fixtures.MemoryServiceTests.setUpClass.__func__)
    setUp = service_fixtures.MemoryServiceTests.setUp
    token = service_fixtures.MemoryServiceTests.token
    request = service_fixtures.MemoryServiceTests.request
    propose = service_fixtures.MemoryServiceTests.propose
    approve = service_fixtures.MemoryServiceTests.approve

    def body(self):
        return dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient', query='fixture', limit=5)

    def test_configured_service_response_and_default_501(self):
        self.assertEqual(self.request('/v1/inference/respond', body=self.body())[0], 501)
        self.service.inference = LocalInferenceAdapter(base_url='http://127.0.0.1:9001', model='fixture-model')
        code, result, _ = self.request('/v1/inference/respond', body=self.body())
        self.assertEqual(code, 200)
        self.assertEqual(result['status'], 'abstained')
        self.assertTrue(self.request('/v1/memory/capabilities', method='GET')[1]['inference'])

    def test_scope_errors_precede_inference_and_provider_errors_sanitised(self):
        from unittest.mock import Mock
        adapter = Mock()
        self.service.inference = adapter
        self.assertEqual(self.request('/v1/inference/respond', body={**self.body(), 'patient_id':'synthetic-other'})[0],403)
        self.assertEqual(self.request('/v1/inference/respond', body={**self.body(), 'model':'attacker'})[0],400)
        adapter.respond.assert_not_called()
        adapter.respond.side_effect = RuntimeError('PRIVATE-PROVIDER-ERROR')
        code, result, _ = self.request('/v1/inference/respond', body=self.body())
        self.assertEqual(code, 503)
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_scope_revocation_blocks_reads_but_permits_admin_purge(self):
        mid = self.propose()
        self.approve(mid)
        base = dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient')
        code, result, _ = self.request('/v1/memory/scopes/revoke', body=base)
        self.assertEqual(code, 200)
        self.assertEqual(result['status'], 'scope_revoked')
        self.assertEqual(self.request('/v1/memory/health', method='GET')[0], 403)
        self.assertEqual(self.request('/v1/inference/respond', body=self.body())[0], 403)
        self.assertEqual(self.request('/v1/memory/query')[0], 403)
        code, result, _ = self.request('/v1/memory/scopes/current', method='DELETE', body=base)
        self.assertEqual(code, 200)
        self.assertFalse(result['backup_erasure_verified'])
        self.assertEqual(self.request('/v1/memory/query')[0], 403)

    def test_actual_inference_and_scope_responses_match_openapi(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('jsonschema required for OpenAPI response validation')
        spec = json.loads((Path(__file__).parents[1] / 'docs/galahad/openapi.json').read_text())
        def validate(name, result):
            jsonschema.validate(result, {'$ref':'#/components/schemas/'+name,
                                         'components':spec['components']})
        self.service.inference = LocalInferenceAdapter(base_url='http://127.0.0.1:9001', model='fixture-model')
        code, result, _ = self.request('/v1/inference/respond', body=self.body())
        self.assertEqual(code,200)
        validate('InferenceResult', result)
        validate('Capabilities', self.request('/v1/memory/capabilities', method='GET')[1])
        base = dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient')
        validate('ScopeRevocationResult', self.request('/v1/memory/scopes/revoke', body=base)[1])
        validate('ScopeDeletionResult', self.request('/v1/memory/scopes/current', method='DELETE', body=base)[1])

    def test_scope_admin_routes_enforce_roles_and_exact_context(self):
        base = dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient')
        for path, method in (('/v1/memory/scopes/revoke','POST'),('/v1/memory/scopes/current','DELETE')):
            self.assertEqual(self.request(path, method=method, body=base,
                             token=self.token(roles=['nerve-memory-reader']))[0],403)
            self.assertEqual(self.request(path, method=method, body={**base,'patient_id':'synthetic-other'})[0],403)
            self.assertEqual(self.request(path, method=method, body={**base,'tenant_id':'other'})[0],400)

    def test_service_discards_output_after_token_expiry(self):
        from unittest.mock import Mock
        import time
        now = int(time.time())
        token = self.token(exp=now+30)
        adapter = Mock()
        self.service.inference = adapter
        with patch('nerve_awim.memory_gateway.service.time.time', return_value=now) as clock:
            def expire(*_):
                clock.return_value = now + 30
                return {'output':'must not be returned'}
            adapter.respond.side_effect = expire
            code, result, _ = self.request('/v1/inference/respond', body=self.body(), token=token)
        self.assertEqual(code,401)
        self.assertNotIn('output', result)


@unittest.skipIf(runtime_fixtures.jwt is None, 'PyJWT[crypto] required')
class InferenceRuntimeContractTests(unittest.TestCase):
    setUpClass = classmethod(runtime_fixtures.MemoryRuntimeTests.setUpClass.__func__)
    setUp = runtime_fixtures.MemoryRuntimeTests.setUp
    save = runtime_fixtures.MemoryRuntimeTests.save

    def test_invalid_inference_config_rejected_before_ledger_creation(self):
        from nerve_awim.memory_gateway.runtime import load_runtime
        self.config['inference'] = dict(base_url='http://remote.test:8000', model='fixture-model',
                                        max_output_tokens=256, timeout_seconds=5)
        with self.assertRaises(ValueError):
            load_runtime(self.save())
        self.assertFalse((self.root / 'memory.db').exists())
        self.config['inference']['base_url'] = 'http://127.0.0.1:9001'
        runtime = load_runtime(self.save())
        self.assertIsInstance(runtime.service.inference, LocalInferenceAdapter)
