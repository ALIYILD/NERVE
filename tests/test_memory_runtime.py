"""Operator config, local server and signed synthetic runtime integration."""
import copy
import io
import json
from pathlib import Path
import socket
import tempfile
from threading import Thread
import time
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from nerve_awim.memory_gateway.runtime import build_runtime, load_runtime
from nerve_awim.memory_gateway.client import MemoryClient
from scripts.serve_memory_gateway import create_server, main
try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    jwt = None


@unittest.skipIf(jwt is None, 'PyJWT[crypto] required')
class MemoryRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key()))
        cls.public_key.update(kid='synthetic-runtime', alg='RS256')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.keys = self.root / 'jwks.json'
        self.keys.write_text(json.dumps({'keys': [self.public_key]}))
        self.config = dict(version=1, synthetic_only=True, ledger_path='memory.db', provider='null',
            max_records_per_scope=5, oidc=dict(issuer='https://identity.test', audience='memory', jwks_path='jwks.json'),
            grants=[dict(subject='alice', tenant_id='tenant-a', agent_id='agent-a', application='clinical',
                user='alice', clinic_id='synthetic-clinic', patient_id='synthetic-patient', session_id='s1',
                roles=['reader', 'writer', 'admin'])])

    def save(self):
        path = self.root / 'config.json'
        path.write_text(json.dumps(self.config))
        return path

    def token(self):
        now = int(time.time())
        return jwt.encode(dict(sub='alice', iss='https://identity.test', aud='memory', iat=now-1,
            exp=now+60, roles=['nerve-memory-reader', 'nerve-memory-writer', 'nerve-memory-admin']),
            self.key, algorithm='RS256', headers={'kid': 'synthetic-runtime'})

    def test_required_session_subject_validated_before_database_mutation(self):
        self.config['grants'].append(dict(self.config['grants'][0], subject='admin-only', roles=['admin']))
        path = self.save()
        ledger = self.root / 'memory.db'
        for subject in ('missing', 'admin-only', '', 'x' * 257, 7, False):
            for existing in (False, True):
                with self.subTest(subject=subject, existing=existing):
                    sentinel = b'existing ledger must remain untouched'
                    if existing:
                        ledger.write_bytes(sentinel)
                    try:
                        with self.assertRaises(ValueError):
                            load_runtime(path, required_subject=subject)
                        if existing:
                            self.assertEqual(ledger.read_bytes(), sentinel)
                        else:
                            self.assertFalse(ledger.exists())
                    finally:
                        if existing:
                            ledger.unlink()
        runtime = load_runtime(path, required_subject='alice')
        self.assertIn('alice', runtime.sessions)

    def test_build_runtime_required_subject_checked_before_database_creation(self):
        with self.assertRaises(ValueError):
            build_runtime(self.config, base_dir=self.root, required_subject='missing')
        self.assertFalse((self.root / 'memory.db').exists())

    def test_factory_wires_service_gateway_sessions_and_relative_paths(self):
        runtime = load_runtime(self.save())
        self.assertTrue((self.root / 'memory.db').is_file())
        self.assertIs(runtime.service.gateway, runtime.gateway)
        self.assertEqual(runtime.gateway.max_records_per_scope, 5)
        self.assertEqual(runtime.gateway.health()['status'], 'ready')
        self.assertEqual(set(runtime.sessions), {'alice'})
        self.assertIsInstance(runtime.sessions['alice'].query('fixture'), dict)
        with self.assertRaises(TypeError):
            runtime.sessions['other'] = runtime.sessions['alice']

    def test_invalid_config_never_creates_database(self):
        variants = []
        for field, value in [('version', True), ('synthetic_only', False), ('provider', 'unknown'),
                             ('max_records_per_scope', True), ('max_records_per_scope', 10001),
                             ('grants', []), ('secret', 'forbidden')]:
            config = copy.deepcopy(self.config)
            config[field] = value
            variants.append(config)
        for field, value in [('roles', ['reader', 'reader']), ('roles', ['root']),
                             ('clinic_id', 'real-clinic'), ('patient_id', 'real-patient'),
                             ('tenant_id', '../escape'), ('subject', '')]:
            config = copy.deepcopy(self.config)
            config['grants'].append({**config['grants'][0], 'subject': 'second', field: value})
            variants.append(config)
        config = copy.deepcopy(self.config)
        config['grants'].append(dict(config['grants'][0]))
        variants.append(config)
        for config in variants:
            with self.subTest(config=config):
                with self.assertRaises((ValueError, TypeError)):
                    build_runtime(config, base_dir=self.root)
                self.assertFalse((self.root / 'memory.db').exists())

    def test_invalid_config_does_not_mutate_existing_file(self):
        ledger = self.root / 'memory.db'
        sentinel = b'unchanged existing file; not a database'
        ledger.write_bytes(sentinel)
        self.config['grants'].append({**self.config['grants'][0], 'subject': 'bob', 'roles': ['root']})
        with self.assertRaises(ValueError):
            load_runtime(self.save())
        self.assertEqual(ledger.read_bytes(), sentinel)

    def test_private_or_invalid_jwks_rejected_before_database(self):
        cases = [dict(self.public_key, d='private-key-forbidden'), dict(self.public_key, use='enc'),
                 dict(self.public_key, key_ops=['sign']), dict(self.public_key, n='invalid'),
                 dict(self.public_key, alg='HS256')]
        for key in cases:
            with self.subTest(key=set(key)):
                self.keys.write_text(json.dumps({'keys': [key]}))
                with self.assertRaises(Exception):
                    load_runtime(self.save())
                self.assertFalse((self.root / 'memory.db').exists())

    def test_duplicate_oversized_and_nonfinite_json_rejected(self):
        path = self.root / 'config.json'
        for raw in (b'{"version":1,"version":1}', b' ' * 131073, b'{"version":NaN}'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                load_runtime(path)
            self.assertFalse((self.root / 'memory.db').exists())

    def test_bad_issuer_and_key_paths_rejected(self):
        for issuer in ('http://identity.test', 'https://user:secret@identity.test', 'https://identity.test?x=y'):
            self.config['oidc']['issuer'] = issuer
            with self.assertRaises(ValueError):
                load_runtime(self.save())
            self.assertFalse((self.root / 'memory.db').exists())

    def test_ledger_cannot_overwrite_config_or_jwks(self):
        for name in ('config.json', 'jwks.json'):
            self.config['ledger_path'] = name
            path = self.save()
            before = (self.root / name).read_bytes()
            with self.assertRaises(ValueError):
                load_runtime(path)
            self.assertEqual((self.root / name).read_bytes(), before)

    def test_roles_bound_to_session_permissions(self):
        self.config['grants'] = [dict(self.config['grants'][0], subject=role, roles=[role])
                                 for role in ('reader', 'writer', 'admin')]
        runtime = load_runtime(self.save())
        self.assertEqual(set(runtime.sessions), {'reader', 'writer'})
        with self.assertRaises(PermissionError):
            runtime.sessions['reader'].propose('fixture', 'source')
        with self.assertRaises(PermissionError):
            runtime.sessions['writer'].query('fixture')
        self.assertEqual(runtime.sessions['writer'].propose('fixture', 'source')['status'], 'pending')

    def test_galahad_selection_reports_blocked_without_enabling_restore(self):
        self.config['provider'] = 'galahad'
        runtime = load_runtime(self.save())
        health = runtime.gateway.health()
        self.assertEqual(health['status'], 'ready')
        self.assertEqual(health['kv']['status'], 'blocked')
        self.assertFalse(health['runtime_restore_enabled'])
        result = runtime.sessions['alice'].query('fixture')
        self.assertEqual(result['kv_status'], 'prefill')

    def test_check_initialises_without_listening_and_invalid_options_leave_no_db(self):
        path = self.save()
        with patch('scripts.serve_memory_gateway.create_server') as server:
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['--config', str(path), '--check']), 0)
            server.assert_not_called()
        self.assertEqual(json.loads(out.getvalue())['status'], 'ready')
        self.config['ledger_path'] = 'invalid-options.db'
        path = self.save()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--config', str(path), '--read-timeout', '0']), 2)
        self.assertFalse((self.root / 'invalid-options.db').exists())

    def test_server_rejects_non_loopback_and_unbounded_limits(self):
        for options in ({'host': '0.0.0.0'}, {'host': 'localhost'}, {'port': -1},
                        {'read_timeout': 31}, {'max_workers': 65}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                create_server(lambda *_: [], **options)

    def test_server_advertises_threads_and_enforces_worker_bound(self):
        from threading import Event
        entered, release = Event(), Event()
        observations = []
        def app(env, start_response):
            observations.append(env['wsgi.multithread'])
            entered.set()
            release.wait(3)
            start_response('200 OK', [('Content-Length', '2')])
            return [b'ok']
        with create_server(app, port=0, read_timeout=1, max_workers=1) as server:
            worker = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
            worker.start()
            try:
                with socket.create_connection(('127.0.0.1', server.server_port), timeout=2) as first:
                    first.sendall(b'GET / HTTP/1.0\r\n\r\n')
                    self.assertTrue(entered.wait(2))
                    with socket.create_connection(('127.0.0.1', server.server_port), timeout=2) as overflow:
                        self.assertEqual(overflow.recv(1024), b'')
                    release.set()
                    self.assertIn(b'200', first.recv(1024))
            finally:
                release.set()
                server.shutdown()
                worker.join(timeout=2)
        self.assertEqual(observations, [True])

    def test_threaded_server_signed_query_and_socket_timeout(self):
        runtime = load_runtime(self.save())
        with create_server(runtime.service, port=0, read_timeout=0.3, max_workers=2) as server:
            worker = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
            worker.start()
            try:
                # A partial request occupies one worker; independent signed query completes.
                with socket.create_connection(('127.0.0.1', server.server_port), timeout=2) as stalled:
                    stalled.sendall(b'POST /v1/memory/query HTTP/1.1\r\n')
                    client = MemoryClient('http://127.0.0.1:' + str(server.server_port), self.token(),
                                          allow_loopback_http=True, timeout=2)
                    result = client.query(clinic_id='synthetic-clinic', patient_id='synthetic-patient', query='fixture')
                    self.assertTrue(result['review_required'])
                    self.assertEqual(stalled.recv(1024), b'')
            finally:
                server.shutdown()
                worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
