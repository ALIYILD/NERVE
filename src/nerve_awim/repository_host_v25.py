"""Authenticated WSGI shadow pilot. Pure repository tools; no remote control API.

Run behind a trusted TLS proxy on loopback. The host owns grants, OIDC keys,
bootstrap and draining. Never place untrusted handlers in this process.
"""
from dataclasses import dataclass
import json
from threading import RLock
import time

from .agent_learning_v12 import AgentTask
from .governed_learning_v20 import _id
from .oidc_v27 import PinnedOIDCVerifier
from .repository_agents_v20 import CONTEXT
from .shadow_learning_v21 import ShadowLearning


@dataclass(frozen=True)
class HostGrant:
    subject: str
    tenant: str
    agent: str
    roles: frozenset[str]


class RepositoryHost:
    def __init__(self, engine, *, verifier, grants, bootstrap=False, capacity=32,
                 requests_per_minute=60):
        if type(verifier) is not PinnedOIDCVerifier:
            raise TypeError('operator-pinned OIDC verifier required')
        if engine._baseline != {CONTEXT: 'ast-inventory'}:
            raise ValueError('repository pilot requires the strong AST baseline')
        if type(requests_per_minute) is not int or not 1 <= requests_per_minute <= 600:
            raise ValueError('request limit must be between one and 600')
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError('queue capacity must be between one and 128')
        grants = tuple(grants)
        if not 1 <= len(grants) <= 64:
            raise ValueError('one to 64 configured principals required')
        self.grants = {}
        for grant in grants:
            if (type(grant) is not HostGrant or type(grant.subject) is not str
                    or not 1 <= len(grant.subject) <= 256 or grant.subject in self.grants
                    or type(grant.roles) is not frozenset or not grant.roles
                    or not grant.roles <= {'runtime', 'auditor'}):
                raise ValueError('unique principal with explicit runtime/auditor grants required')
            _id(grant.tenant)
            _id(grant.agent)
            self.grants[grant.subject] = grant
        self.engine, self.verifier = engine, verifier
        self.limit, self._buckets = requests_per_minute, {}
        self._lock, self.adapters, self.bindings, self.auditors = RLock(), {}, {}, {}
        # Configured grants are validated before any database mutation.
        for scope in sorted({(g.tenant, g.agent) for g in grants}):
            operator = engine.authority.issue(*scope, 'operator')
            try:
                try:
                    state = engine.status(operator)
                except LookupError:
                    if not bootstrap:
                        raise ValueError('scope needs explicit offline bootstrap') from None
                    state = engine.bootstrap(operator)
                # No implicitly adopted promoted release, including after restart.
                self._validate_deployment(scope, state)
                self.bindings[scope] = state['active_release']
            finally:
                engine.authority.revoke(operator)
            runtime = engine.authority.issue(*scope, 'runtime')
            trainer = engine.authority.issue(*scope, 'trainer')
            self.auditors[scope] = engine.authority.issue(*scope, 'auditor')
            self.adapters[scope] = ShadowLearning(engine, runtime=runtime, trainer=trainer,
                                                  capacity=capacity)

    def drain(self, *, limit=32):
        """Trusted host worker only; no client-callable training/approval endpoint."""
        with self._lock:
            return {scope: adapter.drain(limit=limit) for scope, adapter in self.adapters.items()}

    @staticmethod
    def _response(start_response, status, data):
        body = json.dumps(data, allow_nan=False, separators=(',', ':')).encode()
        start_response(status, [('Content-Type', 'application/json'),
                               ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'),
                               ('X-Content-Type-Options', 'nosniff')])
        return [body]

    def __call__(self, environ, start_response):
        # One host owner at a time, including its off-request-path drain worker.
        with self._lock:
            try:
                status, data = self._request(environ)
            except Exception:
                # Do not leak submitted source, tokens, database paths or traces.
                status, data = '503 Service Unavailable', {'error': 'task_service_unavailable'}
        return self._response(start_response, status, data)

    def _request(self, env):
        path, method = env.get('PATH_INFO', ''), env.get('REQUEST_METHOD', '')
        routes = {('/v1/tasks', 'POST'): 'runtime', ('/v1/evidence', 'GET'): 'auditor',
                  ('/v1/readiness', 'GET'): 'auditor'}
        role = routes.get((path, method))
        if role is None or env.get('QUERY_STRING'):
            return '404 Not Found', {'error': 'route_not_found'}
        header = env.get('HTTP_AUTHORIZATION', '')
        if not isinstance(header, str) or not header.startswith('Bearer ') or len(header) > 16384:
            return '401 Unauthorized', {'error': 'invalid_identity'}
        now = int(time.time())
        identity = self.verifier.verify(header[7:], now)
        if (identity is None or identity.issuer != self.verifier.issuer
                or identity.audience != self.verifier.audience or identity.expires_at <= now):
            return '401 Unauthorized', {'error': 'invalid_identity'}
        grant = self.grants.get(identity.subject)
        if grant is None or role not in grant.roles or 'nerve-' + role not in identity.roles:
            return '403 Forbidden', {'error': 'scope_or_role_denied'}
        window = int(time.monotonic() // 60)
        old_window, count = self._buckets.get(identity.subject, (window, 0))
        count = count if old_window == window else 0
        if count >= self.limit:
            return '429 Too Many Requests', {'error': 'request_limit'}
        self._buckets[identity.subject] = (window, count + 1)
        scope = (grant.tenant, grant.agent)
        adapter = self.adapters[scope]
        if role == 'auditor':
            if path == '/v1/readiness':
                result = self.readiness(scope)
                return ('200 OK' if result['ready'] else '503 Service Unavailable'), result
            return '200 OK', self._evidence(scope)
        if env.get('CONTENT_TYPE', '').split(';')[0].strip().lower() != 'application/json':
            return '415 Unsupported Media Type', {'error': 'json_required'}
        raw_length = env.get('CONTENT_LENGTH', '')
        if type(raw_length) is not str or not raw_length.isascii() or not raw_length.isdecimal():
            return '411 Length Required', {'error': 'content_length_required'}
        # Check string length before int conversion (including absurdly long values).
        if len(raw_length) > 8 or int(raw_length) > 20000:
            return '413 Payload Too Large', {'error': 'body_limit'}
        try:
            raw = env['wsgi.input'].read(int(raw_length))
            if len(raw) != int(raw_length):
                raise ValueError('incomplete body')
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('duplicate field')
                    result[key] = value
                return result
            body = json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
            if type(body) is not dict or set(body) != {'task_id', 'source'} or type(body['source']) is not str:
                raise ValueError('exact schema required')
            task = AgentTask(body['task_id'], CONTEXT, body['source'])
            self.engine._task(task)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return '400 Bad Request', {'error': 'invalid_task'}
        return '200 OK', self._execute_task(scope, task)

    def _validate_deployment(self, scope, state):
        if state['generation'] != 0 or state['routes'] != self.engine._baseline:
            raise ValueError('shadow host requires an unchanged initial baseline scope')

    def _evidence(self, scope):
        return self.adapters[scope].report(self.auditors[scope])

    def _execute_task(self, scope, task):
        result = self.adapters[scope].execute(task, expected_release=self.bindings[scope], expected_generation=0)
        return {**result, 'mode': 'shadow', 'learning': 'queued_best_effort', 'cost_usd': None}

    def _readiness_state(self, con, scope, state):
        if state['generation'] != 0 or state['active'] != self.bindings[scope]:
            raise ValueError('unreviewed release change')
        return {'mode': 'shadow', 'degraded': False}

    def readiness(self, scope):
        """Host-local check; HTTP callers must first pass auditor authentication."""
        if scope not in self.adapters:
            raise PermissionError('scope is not configured in this host')
        try:
            with self.engine._db() as con:
                con.execute('BEGIN')
                if con.execute('PRAGMA quick_check').fetchall()[0][0] != 'ok':
                    raise ValueError('database integrity failed')
                state = self.engine._state(con, scope)
                detail = self._readiness_state(con, scope, state)
            return {'ready': True, **detail}
        except Exception:
            return {'ready': False, 'reason': 'deployment_or_database_unavailable'}
