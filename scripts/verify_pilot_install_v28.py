"""Installation smoke test using temporary local identities, never real credentials."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import select
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]


def verify():
    if sys.version_info[:2] != (3, 12) or platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise RuntimeError('this installation drill targets Linux x86_64 and Python 3.12')
    if sys.prefix == sys.base_prefix or not Path(jwt.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('run in a clean virtual environment with its own installed dependencies')
    dependencies = {name: importlib.metadata.version(name) for name in ('PyJWT', 'cryptography', 'cffi', 'pycparser')}
    env = {'PATH': os.defpath, 'PYTHONPATH': str(ROOT/'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    key.update(kid='temporary-test-key', alg='RS256')
    now = int(time.time())
    token = jwt.encode({'sub': 'installation-test', 'iss': 'https://installation.invalid',
        'aud': 'nerve-installation-test', 'iat': now-1, 'exp': now+300,
        'roles': ['nerve-runtime', 'nerve-auditor']}, private, algorithm='RS256', headers={'kid': key['kid']})
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        config = folder/'identity.json'
        config.write_text(json.dumps({'issuer': 'https://installation.invalid', 'audience': 'nerve-installation-test',
            'jwks': {'keys': [key]}, 'grants': [{'subject': 'installation-test', 'tenant': 'test',
                                               'agent': 'repository', 'roles': ['runtime', 'auditor']}]}))
        database, backup, restored = [folder/name for name in ('pilot.db', 'backup.db', 'restored.db')]
        def command(script, *args):
            run = subprocess.run([sys.executable, str(ROOT/'scripts'/script), *map(str, args)],
                env=env, cwd=folder, capture_output=True, text=True, timeout=15)
            if run.returncode:
                raise RuntimeError('packaged command failed: '+script)
            return json.loads(run.stdout)
        def stop(process):
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
                raise RuntimeError('packaged service did not stop gracefully')
            if process.returncode != 0:
                raise RuntimeError('packaged service did not exit cleanly')
        def start(path, bootstrap=False):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            args = [sys.executable, str(ROOT/'scripts'/'serve_repository_host_v25.py'),
                    '--config', str(config), '--database', str(path), '--port', str(port)]
            if bootstrap:
                args.append('--bootstrap')
            process = subprocess.Popen(args, env=env, cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                ready, _, _ = select.select([process.stdout], [], [], 10)
                if not ready or 'listening on 127.0.0.1' not in process.stdout.readline():
                    raise RuntimeError('packaged service startup failed')
            except BaseException:
                process.kill()
                process.communicate(timeout=5)
                raise
            return process, port
        def call(port, route, body=None, auth=True):
            headers = {'Content-Type': 'application/json'}
            if auth:
                headers['Authorization'] = 'Bearer '+token
            request = Request(f'http://127.0.0.1:{port}'+route,
                data=json.dumps(body).encode() if body is not None else None, headers=headers)
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        process, port = start(database, bootstrap=True)
        try:
            assert call(port, '/v1/readiness')['ready']
            try:
                call(port, '/v1/readiness', auth=False)
                raise AssertionError('unauthenticated readiness accepted')
            except HTTPError as exc:
                assert exc.code == 401
                exc.close()
            result = call(port, '/v1/tasks', {'task_id': 'installed-task',
                'source': 'def outer():\n    def nested(): pass'})
            assert result['value'] == ['outer'] and result['strategy'] == 'ast-inventory'
            assert call(port, '/v1/evidence')['actual_active_outcomes'][0]['hits'] == 1
            release = result['release']
        finally:
            stop(process)
        assert command('serve_repository_host_v25.py', '--config', config, '--database', database, '--check')['ready']
        command('manage_repository_store_v27.py', 'backup', '--source', database, '--destination', backup)
        command('manage_repository_store_v27.py', 'restore', '--source', backup, '--destination', restored)
        process, port = start(restored)
        try:
            assert call(port, '/v1/readiness')['ready']
            assert call(port, '/v1/evidence')['actual_active_outcomes'][0]['hits'] == 1
            result = call(port, '/v1/tasks', {'task_id': 'recovered-task', 'source': 'def recovered(): pass'})
            assert result['value'] == ['recovered'] and result['release'] == release
        finally:
            stop(process)
    return {'status': 'packaged_installation_verified', 'dependencies': dependencies,
            'checks': ['signed_http', 'unauthorised_denial', 'task_output', 'shadow_evidence',
                       'startup_check', 'backup_restore', 'restarted_release', 'graceful_stop'],
            'scope': 'temporary loopback service and generated test identities; no public deployment'}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))
