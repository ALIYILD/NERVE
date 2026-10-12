import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from wsgiref.util import setup_testing_defaults

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.service import MemoryService, MemoryGrant, synthetic_scope
from nerve_awim.memory_gateway.client import MemoryClient
from nerve_awim.oidc_v27 import PinnedOIDCVerifier
try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    jwt = None


@unittest.skipIf(jwt is None, 'PyJWT[crypto] required for real signature tests')
class MemoryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key()))
        jwk.update(kid='synthetic-memory', alg='RS256')
        cls.verifier = PinnedOIDCVerifier(issuer='https://identity.test', audience='memory', jwks={'keys': [jwk]})

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.auth = MemoryAuthority()
        self.actor = self.auth.issue('tenant-a', 'agent-a', permissions=('read', 'propose', 'approve', 'delete'))
        self.ledger = TrustedMemoryLedger(Path(self.temp.name) / 'memory.db', self.auth)
        self.gateway = MemoryGateway(self.ledger)
        self.scope = synthetic_scope('tenant-a', 'agent-a', application='clinical', user='alice',
            clinic='synthetic-clinic', patient='synthetic-patient', session='session-a')
        self.grant = MemoryGrant('alice', self.actor, self.scope, 'synthetic-clinic',
                                 'synthetic-patient', frozenset({'reader', 'writer', 'admin'}))
        self.service = MemoryService(self.gateway, verifier=self.verifier, grants=[self.grant])

    def token(self, **claims):
        now = int(time.time())
        data = dict(sub='alice', iss='https://identity.test', aud='memory', iat=now-1, exp=now+60,
                    roles=['nerve-memory-reader', 'nerve-memory-writer', 'nerve-memory-admin'])
        data.update(claims)
        return jwt.encode(data, self.key, algorithm='RS256', headers={'kid': 'synthetic-memory'})

    def request(self, path='/v1/memory/query', method='POST', body=None, token=None, **overrides):
        if body is None:
            body = dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient', query='fixture', limit=5)
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        env = {}
        setup_testing_defaults(env)
        env.update(PATH_INFO=path, REQUEST_METHOD=method, CONTENT_TYPE='application/json',
                   CONTENT_LENGTH=str(len(raw)), HTTP_AUTHORIZATION='Bearer ' + (token or self.token()))
        env['wsgi.input'] = io.BytesIO(raw)
        env.update(overrides)
        captured = []
        response = b''.join(self.service(env, lambda status, headers: captured.append((status, dict(headers)))))
        return int(captured[0][0].split()[0]), json.loads(response), captured[0][1]

    def propose(self):
        body = dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient',
                    content='fixture verified evidence', source_id='fixture-source')
        status, result, _ = self.request('/v1/memory/experiences', body=body)
        self.assertEqual(status, 201)
        return result['memory_id']

    def approve(self, mid):
        self.gateway.decide(self.actor, mid, scope=self.scope, approve=True, evaluator_id='offline-review')

    def test_pending_then_approved_provenance_and_review(self):
        mid = self.propose()
        self.assertEqual(self.request()[1]['records'], [])
        self.approve(mid)
        code, data, headers = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(data['records'][0]['source_id'], 'fixture-source')
        self.assertTrue(data['review_required'])
        self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_invalid_signed_identity(self):
        for token in (self.token(exp=int(time.time())-1), self.token(aud='other'),
                      self.token(iss='https://evil.test'), self.token()+'x'):
            self.assertEqual(self.request(token=token)[0], 401)

    def test_authentication_precedes_body_read(self):
        class Unreadable:
            def read(self, *_):
                raise AssertionError('unauthenticated read')
        self.assertEqual(self.request(token='invalid', **{'wsgi.input': Unreadable()})[0], 401)

    def test_signed_role_and_host_grant_intersection(self):
        self.assertEqual(self.request(token=self.token(roles=[]))[0], 403)
        self.assertEqual(self.request(token=self.token(sub='other'))[0], 403)

    def test_patient_clinic_and_tenant_override_denied(self):
        body = dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient', query='fixture', limit=5)
        for name in ('patient_id', 'clinic_id'):
            self.assertEqual(self.request(body={**body, name: 'synthetic-other'})[0], 403)
        self.assertEqual(self.request(body={**body, 'tenant_id': 'other'})[0], 400)

    def test_context_and_tenant_isolation(self):
        from nerve_awim.memory_gateway.contracts import MemoryScope
        for actor, scope in ((self.actor, MemoryScope('tenant-a', 'agent-a', 'different-context')),
                             (self.auth.issue('tenant-b', 'agent-a', permissions=('read','propose','approve')),
                              MemoryScope('tenant-b', 'agent-a', self.scope.context))):
            mid = self.gateway.propose(actor, scope=scope, content='fixture foreign', source_id='foreign')
            self.gateway.decide(actor, mid, scope=scope, approve=True, evaluator_id='review')
        self.assertEqual(self.request()[1]['records'], [])

    def test_revoke_and_delete(self):
        mid = self.propose()
        self.approve(mid)
        base = dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient')
        self.assertEqual(self.request('/v1/memory/revoke', body={**base, 'memory_id': mid})[0], 200)
        self.assertEqual(self.request()[1]['records'], [])
        self.assertEqual(self.request('/v1/memory/records/'+mid, method='DELETE', body=base)[0], 200)

    def test_admin_cannot_delete_another_context(self):
        from nerve_awim.memory_gateway.contracts import MemoryScope
        mid = self.gateway.propose(self.actor, scope=MemoryScope('tenant-a','agent-a','other'),
                                   content='fixture secret', source_id='source')
        base = dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient')
        self.assertIn(self.request('/v1/memory/records/'+mid, method='DELETE', body=base)[0], (403,404))

    def test_revoked_capability_denies_health(self):
        self.auth.revoke(self.actor)
        self.assertEqual(self.request('/v1/memory/health', method='GET')[0], 403)

    def test_duplicate_fields_body_and_content_type(self):
        self.assertEqual(self.request(body=b'{"patient_id":1,"patient_id":2}')[0], 400)
        self.assertEqual(self.request(CONTENT_LENGTH='999999999')[0], 413)
        self.assertEqual(self.request(CONTENT_LENGTH='')[0], 411)
        self.assertEqual(self.request(CONTENT_TYPE='text/plain')[0], 415)

    def test_rate_limit(self):
        self.service.limit = 1
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request()[0], 429)

    def test_unsupported_routes_and_inference(self):
        self.assertEqual(self.request('/v1/memory/approve')[0], 404)
        self.assertEqual(self.request('/v1/inference/respond', body=dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient'))[0], 501)

    def test_feedback_never_approves(self):
        body = dict(clinic_id='synthetic-clinic', patient_id='synthetic-patient',
                    content='fixture experience', source_id='feedback-source')
        self.assertEqual(self.request('/v1/memory/feedback', body=body)[1]['status'], 'pending')
        self.assertEqual(self.request()[1]['records'], [])

    def test_health_metrics_capabilities(self):
        for path in ('health','metrics','capabilities'):
            self.assertEqual(self.request('/v1/memory/'+path, method='GET')[0], 200)

    def test_unavailable_store_health_is_503(self):
        Path(self.ledger.path).write_bytes(b'corrupted synthetic sqlite fixture')
        self.assertEqual(self.request('/v1/memory/health', method='GET')[0], 503)

    def test_sanitised_unexpected_error(self):
        from unittest.mock import patch
        with patch.object(self.gateway, 'retrieve', side_effect=RuntimeError('SECRET-PAYLOAD')):
            code, result, _ = self.request()
        self.assertEqual(code, 503)
        self.assertNotIn('SECRET-PAYLOAD', json.dumps(result))

    def test_loopback_reference_client_end_to_end(self):
        from threading import Thread
        from wsgiref.simple_server import make_server, WSGIRequestHandler
        class QuietHandler(WSGIRequestHandler):
            def log_message(self, *_):
                pass
        mid = self.propose()
        self.approve(mid)
        with make_server('127.0.0.1', 0, self.service, handler_class=QuietHandler) as server:
            server.timeout = 3
            thread = Thread(target=server.handle_request, daemon=True)
            thread.start()
            client = MemoryClient('http://127.0.0.1:' + str(server.server_port),
                                  self.token(), allow_loopback_http=True)
            result = client.query(clinic_id='synthetic-clinic', patient_id='synthetic-patient', query='fixture')
            thread.join(timeout=4)
            self.assertFalse(thread.is_alive())
        self.assertEqual(result['records'][0]['memory_id'], mid)
        self.assertTrue(result['review_required'])

    def test_openapi_route_contract(self):
        spec = json.loads((Path(__file__).parents[1] / 'docs/galahad/openapi.json').read_text())
        for method, path in self.service.ROUTES:
            self.assertIn(method.lower(), spec['paths'][path])
            self.assertTrue(spec['paths'][path][method.lower()]['security'])


class MemoryClientTests(unittest.TestCase):
    def test_plain_http_and_origin_credentials_rejected(self):
        for url in ('http://remote.test', 'https://user:password@example.test', 'https://example.test/?x=y'):
            with self.assertRaises(ValueError):
                MemoryClient(url, 'token')
        MemoryClient('http://127.0.0.1:8000', 'token', allow_loopback_http=True)

    def test_arbitrary_route_rejected_before_network(self):
        client = MemoryClient('https://memory.test', 'token')
        with self.assertRaises(ValueError):
            client.request('GET', '//attacker.test')

    def test_scope_changes_for_every_clinical_dimension(self):
        fields = dict(application='app', user='user', clinic='synthetic-c', patient='synthetic-p', session='s')
        first = synthetic_scope('t', 'a', **fields)
        for field in fields:
            changed = {**fields, field: fields[field]+'2'}
            self.assertNotEqual(first.context, synthetic_scope('t', 'a', **changed).context)
