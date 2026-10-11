import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults

from scripts.serve_repository_host_v25 import build_host
from nerve_awim.repository_host_v25 import HostGrant, RepositoryHost

try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    jwt = None


@unittest.skipIf(jwt is None, 'PyJWT[crypto] required')
class HostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key()))
        jwk.update(kid='host-test', alg='RS256')
        cls.config = {'issuer': 'https://identity.test', 'audience': 'nerve-host',
                      'jwks': {'keys': [jwk]}, 'grants': [
                          {'subject': 'alice', 'tenant': 'a', 'agent': 'repo', 'roles': ['runtime', 'auditor']},
                          {'subject': 'bob', 'tenant': 'b', 'agent': 'repo', 'roles': ['runtime', 'auditor']},
                          {'subject': 'reader', 'tenant': 'a', 'agent': 'repo', 'roles': ['auditor']}]}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'host.db'
        self.host = build_host(self.config, self.db, bootstrap=True)

    def token(self, **changes):
        now = int(time.time())
        claims = dict(sub='alice', iss='https://identity.test', aud='nerve-host',
                      exp=now + 120, iat=now - 1, roles=['nerve-runtime', 'nerve-auditor'])
        claims.update(changes)
        return jwt.encode(claims, self.key, algorithm='RS256', headers={'kid': 'host-test'})

    def request(self, body=None, *, path='/v1/tasks', method='POST', token=None, overrides=None):
        if body is None:
            body = {'task_id': 'first', 'source': '# PRIVATE-CONTENT\ndef top():\n    def nested(): pass\n'}
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        env = {}
        setup_testing_defaults(env)
        env.update(PATH_INFO=path, REQUEST_METHOD=method, CONTENT_TYPE='application/json',
                   CONTENT_LENGTH=str(len(raw)), HTTP_AUTHORIZATION='Bearer ' + (token or self.token()))
        env['wsgi.input'] = io.BytesIO(raw)
        env.update(overrides or {})
        captured = []
        result = b''.join(self.host(env, lambda status, headers: captured.append((status, dict(headers)))))
        return int(captured[0][0].split()[0]), json.loads(result), captured[0][1]

    def test_signed_task_then_off_path_learning(self):
        status, result, headers = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(result['value'], ['top'])
        self.assertEqual(result['strategy'], 'ast-inventory')
        self.assertFalse(result['feedback_written'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(self.host.adapters[('a', 'repo')].pending, 1)
        self.assertEqual(self.host.drain()[('a', 'repo')]['recorded'], 1)
        status, evidence, _ = self.request(path='/v1/evidence', method='GET')
        self.assertEqual(status, 200)
        self.assertEqual(evidence['actual_active_outcomes'][0]['hits'], 1)
        self.assertNotIn(b'PRIVATE-CONTENT', self.db.read_bytes())
        self.assertNotIn(self.token().encode(), self.db.read_bytes())

    def test_expired_wrong_issuer_audience_and_bad_signature(self):
        bad = [self.token(exp=int(time.time())-10), self.token(iss='https://evil.test'),
               self.token(aud='other'), self.token() + 'invalid']
        for token in bad:
            self.assertEqual(self.request(token=token)[0], 401)
        self.assertEqual(self.host.adapters[('a', 'repo')].pending, 0)

    def test_auth_checked_before_body_read(self):
        class Unreadable:
            def read(self, *_):
                raise AssertionError('must not read unauthenticated body')
        self.assertEqual(self.request(overrides={'HTTP_AUTHORIZATION': '', 'wsgi.input': Unreadable()})[0], 401)

    def test_unknown_subject_role_and_grant_escalation_denied(self):
        for claims in ({'sub': 'unknown'}, {'roles': ['nerve-operator']}, {'sub': 'reader'}):
            self.assertEqual(self.request(token=self.token(**claims))[0], 403)
        self.assertEqual(self.request(token=self.token(sub='reader'), path='/v1/evidence', method='GET')[0], 200)

    def test_payload_cannot_choose_tenant_context_or_strategy(self):
        for field in ('tenant', 'agent', 'context', 'strategy', 'roles'):
            self.assertEqual(self.request({'task_id': 'x', 'source': 'pass', field: 'b'})[0], 400)
        self.assertEqual(self.request(token=self.token(tenant='b', agent='other'))[0], 200)
        self.assertEqual(self.host.adapters[('a', 'repo')].pending, 1)
        self.assertEqual(self.host.adapters[('b', 'repo')].pending, 0)

    def test_tenant_evidence_isolation(self):
        self.request()
        self.host.drain()
        self.assertEqual(self.request(path='/v1/evidence', method='GET', token=self.token(sub='bob'))[1]['actual_active_outcomes'], [])

    def test_no_remote_control_or_drain_routes(self):
        for path in ('/v1/promote', '/v1/rollback', '/v1/train', '/v1/drain', '/v1/bootstrap'):
            self.assertEqual(self.request(path=path)[0], 404)
        self.assertEqual(self.request(overrides={'QUERY_STRING': 'tenant=b'})[0], 404)

    def test_length_content_type_and_exact_schema(self):
        for env, expected in [({'CONTENT_LENGTH': ''}, 411), ({'CONTENT_LENGTH': '-1'}, 411),
                              ({'CONTENT_LENGTH': '9999999999999999'}, 413),
                              ({'CONTENT_TYPE': 'text/plain'}, 415)]:
            self.assertEqual(self.request(overrides=env)[0], expected)
        for raw in (b'[]', b'{', b'{"task_id":"a","task_id":"b","source":"pass"}', b'\xff'):
            self.assertEqual(self.request(raw)[0], 400)
        self.assertEqual(self.request({'task_id': 'bad id', 'source': 'pass'})[0], 400)
        self.assertEqual(self.request({'task_id': 'x', 'source': 'a'*17000})[0], 400)
        self.assertEqual(self.request(overrides={'CONTENT_LENGTH': '19999'})[0], 400)

    def test_request_limit(self):
        self.host.limit = 1
        with patch('nerve_awim.repository_host_v25.time.monotonic', return_value=60):
            self.assertEqual(self.request()[0], 200)
            self.assertEqual(self.request()[0], 429)
        with patch('nerve_awim.repository_host_v25.time.monotonic', return_value=120):
            self.assertEqual(self.request()[0], 200)

    def test_handler_error_is_sanitised_and_counted(self):
        from nerve_awim.repository_agents_v20 import CONTEXT
        def broken(_):
            raise RuntimeError('PRIVATE-ERROR')
        self.host.engine._registry[(CONTEXT, 'ast-inventory')] = broken
        status, result, _ = self.request()
        self.assertEqual(status, 503)
        self.assertNotIn('PRIVATE-ERROR', json.dumps(result))
        self.host.drain()
        row = self.request(path='/v1/evidence', method='GET')[1]['actual_active_outcomes'][0]
        self.assertEqual(row['errors'], 1)
        self.assertNotIn(b'PRIVATE-ERROR', self.db.read_bytes())

    def test_restart_keeps_evidence_not_queued_source(self):
        self.request()
        self.host.drain()
        self.request({'task_id': 'lost', 'source': 'def lost(): pass'})
        self.host = build_host(self.config, self.db)
        evidence = self.request(path='/v1/evidence', method='GET')[1]
        self.assertEqual(evidence['actual_active_outcomes'][0]['tasks'], 1)
        self.assertEqual(evidence['pending_in_this_process'], 0)

    def test_changed_release_or_generation_fails_closed(self):
        with self.host.engine._db() as con:
            con.execute("UPDATE gl_state SET generation=1 WHERE tenant='a'")
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.host.adapters[('a', 'repo')].pending, 0)
        with self.assertRaises(ValueError):
            build_host(self.config, self.db)

    def test_no_implicit_bootstrap_and_no_duplicate_grants(self):
        with self.assertRaises(ValueError):
            build_host(self.config, Path(self.temp.name) / 'uninitialised.db')
        grant = HostGrant('duplicate', 'a', 'repo', frozenset({'runtime'}))
        with self.assertRaises(ValueError):
            RepositoryHost(self.host.engine, verifier=self.host.verifier, grants=[grant, grant])

    def test_overflow_keeps_result_and_reports_dropped(self):
        self.host.adapters[('a', 'repo')].capacity = 1
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request({'task_id': 'next', 'source': 'def next_fn(): pass'})[0], 200)
        self.assertEqual(self.host.adapters[('a', 'repo')].dropped, 1)

    def test_real_http_signed_request_and_denial(self):
        from threading import Thread
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from wsgiref.simple_server import make_server
        from scripts.serve_repository_host_v25 import PilotServer, QuietHandler
        server = make_server('127.0.0.1', 0, self.host, server_class=PilotServer, handler_class=QuietHandler)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/v1/tasks'
            body = json.dumps({'task_id': 'http-task', 'source': 'def wire_fn(): pass'}).encode()
            request = Request(url, data=body, headers={'Content-Type': 'application/json',
                                                      'Authorization': 'Bearer ' + self.token()})
            with urlopen(request, timeout=5) as response:
                self.assertEqual(json.load(response)['value'], ['wire_fn'])
            with self.assertRaises(HTTPError) as denied:
                urlopen(Request(url, data=body, headers={'Content-Type': 'application/json'}), timeout=5)
            self.assertEqual(denied.exception.code, 401)
            denied.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_submitted_code_is_parsed_never_executed(self):
        result = self.request({'task_id': 'non-executable',
                               'source': 'raise RuntimeError("MUST NOT RUN")\ndef found(): pass'})
        self.assertEqual(result[0], 200)
        self.assertEqual(result[1]['value'], ['found'])

    def test_duplicate_http_task_cannot_inflate_training(self):
        self.request()
        self.host.drain()
        self.request()
        self.assertEqual(self.host.drain()[('a', 'repo')]['rejected'], 1)
        evidence = self.request(path='/v1/evidence', method='GET')[1]
        self.assertEqual(evidence['actual_active_outcomes'][0]['tasks'], 1)

    def test_standalone_server_restart_preserves_http_evidence(self):
        import os
        import select
        import socket
        import subprocess
        import sys
        from urllib.request import Request, urlopen
        config = Path(self.temp.name) / 'public-config.json'
        config.write_text(json.dumps(self.config))
        # Reserve an ephemeral local port, then give it to the standalone CLI.
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        command = [sys.executable, 'scripts/serve_repository_host_v25.py',
                   '--config', str(config), '--database', str(self.db), '--port', str(port)]
        def start():
            process = subprocess.Popen(command, env={**os.environ, 'PYTHONPATH': 'src'},
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                ready, _, _ = select.select([process.stdout], [], [], 10)
                self.assertTrue(ready, 'server startup timeout')
                line = process.stdout.readline()
                self.assertIn('listening on 127.0.0.1', line)
                return process
            except BaseException:
                stop(process)
                raise
        def stop(process):
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
        def call(path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            request = Request(f'http://127.0.0.1:{port}' + path, data=data,
                              headers={'Content-Type': 'application/json',
                                       'Authorization': 'Bearer ' + self.token()})
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        process = start()
        try:
            value = call('/v1/tasks', {'task_id': 'standalone', 'source': 'def real_process(): pass'})
            self.assertEqual(value['value'], ['real_process'])
            evidence = call('/v1/evidence')
            self.assertEqual(evidence['actual_active_outcomes'][0]['tasks'], 1)
        finally:
            stop(process)
        process = start()
        try:
            evidence = call('/v1/evidence')
            self.assertEqual(evidence['actual_active_outcomes'][0]['hits'], 1)
            self.assertEqual(evidence['pending_in_this_process'], 0)
        finally:
            stop(process)
