#!/usr/bin/env python3
"""One-command synthetic NERVE runtime/HTTP/agent/restart/revocation workflow.

Keys and stores are temporary. Nothing is published, promoted or installed.
"""
import argparse
import json
from pathlib import Path
import tempfile
from threading import Thread
import time
from urllib.error import HTTPError

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from nerve_awim.agent_bridge_v13 import DemoAgentBridge
from nerve_awim.memory_gateway.client import MemoryClient
from nerve_awim.memory_gateway.runtime import load_runtime
from serve_memory_gateway import create_server


def run_demo(provider='null'):
    with tempfile.TemporaryDirectory(prefix='nerve-memory-demo-') as directory:
        root = Path(directory)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        public.update(kid='temporary-synthetic-demo', alg='RS256')
        (root / 'public-jwks.json').write_text(json.dumps({'keys': [public]}))
        config = {'version': 1, 'synthetic_only': True, 'ledger_path': 'verified.sqlite',
                  'provider': provider, 'max_records_per_scope': 1000,
                  'oidc': {'issuer': 'https://synthetic.identity.test', 'audience': 'nerve-memory',
                           'jwks_path': 'public-jwks.json'},
                  'grants': [{'subject': 'synthetic-host', 'tenant_id': 'synthetic-tenant',
                              'agent_id': 'synthetic-agent', 'application': 'demo', 'user': 'fixture',
                              'clinic_id': 'synthetic-clinic', 'patient_id': 'synthetic-patient',
                              'session_id': 'fixture-session', 'roles': ['reader', 'writer', 'admin']}]}
        config_path = root / 'runtime.json'
        config_path.write_text(json.dumps(config))
        runtime = load_runtime(config_path)
        grant = runtime.service.grants['synthetic-host']
        now = int(time.time())
        token = jwt.encode({'iss': config['oidc']['issuer'], 'aud': 'nerve-memory',
                            'sub': 'synthetic-host', 'iat': now-1, 'exp': now+120,
                            'roles': ['nerve-memory-reader', 'nerve-memory-writer', 'nerve-memory-admin']},
                           key, algorithm='RS256', headers={'kid': public['kid']})
        server = create_server(runtime.service, port=0)
        thread = Thread(target=server.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
        thread.start()
        try:
            client = MemoryClient(f'http://127.0.0.1:{server.server_port}', token,
                                  allow_loopback_http=True)
            scope_fields = {'clinic_id': 'synthetic-clinic', 'patient_id': 'synthetic-patient'}
            hint = {'schema': 'nerve-demo-strategy-v1', 'task': 'email-normalization',
                    'extract': 'json-field', 'normalise': 'trim-lower'}
            pending = client.request('POST', '/v1/memory/experiences', dict(scope_fields,
                content=json.dumps(hint), source_id='fixed-synthetic-strategy'))
            assert pending['status'] == 'pending'
            assert client.query(**scope_fields, query='email normalization')['records'] == []
            # Trusted host evaluates this exact fixed allowlisted fixture. This
            # operation is intentionally absent from HTTP and MCP tool schemas.
            assert json.loads(runtime.gateway.ledger.status(grant.actor, pending['memory_id']).content) == hint
            runtime.gateway.decide(grant.actor, pending['memory_id'], scope=grant.scope,
                                   approve=True, evaluator_id='fixed-synthetic-host-review')
            queried = client.query(**scope_fields, query='email normalization')
            assert queried['records'][0]['memory_id'] == pending['memory_id']
            bridge = DemoAgentBridge(root / 'legacy.sqlite',
                                     memory_session=runtime.sessions['synthetic-host'])
            result = bridge.run_pipeline(task_id='synthetic-one',
                email_document=json.dumps({'email': '  FIXTURE@EXAMPLE.COM  '}))
            assert result['result'] == 'fixture@example.com'
            assert result['verified_memory']['status'] == 'used'
            outcome = runtime.gateway.ledger.status(grant.actor, result['outcome_memory']['memory_id'])
            assert outcome.status == 'pending' and 'fixture@example.com' not in outcome.content.lower()
            parallel = bridge.run_pipelines([
                {'task_id': 'synthetic-two', 'email_document': '{"email":" TWO@EXAMPLE.COM "}'},
                {'task_id': 'synthetic-three', 'email_document': '{"email":" THREE@EXAMPLE.COM "}'}])
            assert all(row['verified_memory']['status'] == 'used' for row in parallel)
            restarted = load_runtime(config_path)
            assert len(restarted.sessions['synthetic-host'].query('email normalization')['records']) == 1
            denied = False
            try:
                client.query(clinic_id='synthetic-clinic', patient_id='synthetic-other', query='email')
            except HTTPError as error:
                denied = error.code == 403
            assert denied
            revoked = client.request('POST', '/v1/memory/revoke', dict(scope_fields, memory_id=pending['memory_id']))
            assert revoked['status'] == 'revoked'
            assert restarted.sessions['synthetic-host'].query('email normalization')['records'] == []
            return {'status': 'passed', 'synthetic_only': True, 'http_signed_auth': True,
                    'pending_excluded': True, 'approved_strategy_used': True,
                    'parallel_jobs': len(parallel), 'outcomes_pending': True,
                    'scope_denial_verified': True, 'ledger_reopen_verified': True,
                    'revocation_visible_after_reopen': True, 'provider': provider,
                    'cache_purge_confirmed': revoked['cache_purge_confirmed'],
                    'kv_status': result['verified_memory']['kv_status'],
                    'provider_available': runtime.gateway.health()['kv']['available'],
                    'runtime_kv_restore_tested': False, 'deployed': False}
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=('null', 'galahad'), default='null')
    args = parser.parse_args()
    print(json.dumps(run_demo(args.provider), indent=2, sort_keys=True))
