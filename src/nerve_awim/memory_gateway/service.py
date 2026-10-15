"""Synthetic-only WSGI boundary. Deploy only behind an operator-owned TLS proxy."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from threading import RLock
import time

from ..memory_v18 import MemoryActor, _id
from ..oidc_v27 import PinnedOIDCVerifier
from .contracts import MemoryRequest, MemoryScope


def synthetic_scope(tenant_id, agent_id, *, application, user, clinic, patient, session):
    """Host-only exact clinical scope; caller IDs never confer permission."""
    values = (application, user, clinic, patient, session)
    for value in values:
        _id(value, 'synthetic scope')
    if not clinic.startswith('synthetic-') or not patient.startswith('synthetic-'):
        raise ValueError('synthetic fixture identifiers required')
    context = 'clinical-' + sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()
    return MemoryScope(tenant_id, agent_id, context)


@dataclass(frozen=True)
class MemoryGrant:
    subject: str
    actor: MemoryActor
    scope: MemoryScope
    clinic_id: str
    patient_id: str
    roles: frozenset[str]


class MemoryService:
    """Offline grants intersect signed roles; no issuer or approval endpoints."""
    ROUTES = {
        ('GET', '/v1/memory/capabilities'): 'reader',
        ('GET', '/v1/memory/health'): 'reader',
        ('GET', '/v1/memory/metrics'): 'admin',
        ('POST', '/v1/memory/query'): 'reader',
        ('POST', '/v1/memory/experiences'): 'writer',
        ('POST', '/v1/memory/feedback'): 'writer',
        ('POST', '/v1/memory/revoke'): 'admin',
        ('POST', '/v1/memory/scopes/revoke'): 'admin',
        ('DELETE', '/v1/memory/scopes/current'): 'admin',
        ('POST', '/v1/inference/respond'): 'reader',
    }

    def __init__(self, gateway, *, verifier, grants, requests_per_minute=60, inference=None):
        if type(verifier) is not PinnedOIDCVerifier:
            raise TypeError('operator-pinned OIDC verifier required')
        if type(requests_per_minute) is not int or not 1 <= requests_per_minute <= 600:
            raise ValueError('bounded rate limit required')
        self.gateway, self.verifier = gateway, verifier
        self.inference = inference
        self.grants = {}
        for grant in grants:
            if (type(grant) is not MemoryGrant or type(grant.subject) is not str
                    or not 1 <= len(grant.subject) <= 256 or grant.subject in self.grants
                    or type(grant.roles) is not frozenset or not grant.roles
                    or not grant.roles <= {'reader', 'writer', 'admin'}
                    or type(grant.actor) is not MemoryActor
                    or type(grant.scope) is not MemoryScope
                    or (grant.actor.tenant_id, grant.actor.agent_id) !=
                    (grant.scope.tenant_id, grant.scope.agent_id)):
                raise ValueError('unique explicit scoped host grant required')
            for value in (grant.clinic_id, grant.patient_id):
                _id(value, 'clinical fixture')
                if not value.startswith('synthetic-'):
                    raise ValueError('synthetic fixtures only')
            self.grants[grant.subject] = grant
        if not 1 <= len(self.grants) <= 64:
            raise ValueError('one to 64 host grants required')
        self.limit, self._buckets, self._lock = requests_per_minute, {}, RLock()

    def __call__(self, environ, start_response):
        try:
            status, result = self._request(environ)
        except PermissionError:
            status, result = 403, {'error': 'scope_or_role_denied'}
        except LookupError:
            status, result = 404, {'error': 'memory_not_found'}
        except (ValueError, TypeError, UnicodeError, RecursionError):
            status, result = 400, {'error': 'invalid_request'}
        except Exception:
            status, result = 503, {'error': 'memory_service_unavailable'}
        names = {200: 'OK', 201: 'Created', 400: 'Bad Request', 401: 'Unauthorized',
                 403: 'Forbidden', 404: 'Not Found', 411: 'Length Required',
                 413: 'Payload Too Large', 415: 'Unsupported Media Type',
                 429: 'Too Many Requests', 501: 'Not Implemented', 503: 'Service Unavailable'}
        raw = json.dumps(result, allow_nan=False, separators=(',', ':')).encode()
        start_response(f'{status} {names[status]}', [('Content-Type', 'application/json'),
                       ('Content-Length', str(len(raw))), ('Cache-Control', 'no-store'),
                       ('X-Content-Type-Options', 'nosniff')])
        return [raw]

    def _request(self, env):
        method, path = env.get('REQUEST_METHOD'), env.get('PATH_INFO', '')
        role = self.ROUTES.get((method, path))
        record_id = None
        if method == 'DELETE' and path.startswith('/v1/memory/records/'):
            record_id = path[len('/v1/memory/records/'):]
            _id(record_id, 'memory ID')
            role = 'admin'
        if role is None or env.get('QUERY_STRING'):
            return 404, {'error': 'route_not_found'}
        header = env.get('HTTP_AUTHORIZATION', '')
        if type(header) is not str or not header.startswith('Bearer ') or len(header) > 16384:
            return 401, {'error': 'invalid_identity'}
        now = int(time.time())
        identity = self.verifier.verify(header[7:], now)
        if (identity is None or identity.issuer != self.verifier.issuer
                or identity.audience != self.verifier.audience or identity.expires_at <= now):
            return 401, {'error': 'invalid_identity'}
        grant = self.grants.get(identity.subject)
        if grant is None or role not in grant.roles or 'nerve-memory-' + role not in identity.roles:
            return 403, {'error': 'scope_or_role_denied'}
        # Recheck capability revocation even for metadata-only requests.
        maintenance = role == 'admin' and (record_id is not None or path in
            ('/v1/memory/scopes/revoke', '/v1/memory/scopes/current'))
        permission = {'reader': 'read', 'writer': 'propose',
                      'admin': 'delete' if record_id or path.endswith('/scopes/current') else
                      'approve' if path.endswith('/scopes/revoke') else 'read'}[role]
        self.gateway._require(grant.actor, grant.scope, permission, allow_revoked=maintenance)
        # Only shared rate accounting is serialized. Never hold this lock
        # across client reads, identity verification or gateway/provider I/O.
        with self._lock:
            window = int(time.monotonic() // 60)
            previous, count = self._buckets.get(identity.subject, (window, 0))
            count = count if previous == window else 0
            if count >= self.limit:
                return 429, {'error': 'request_limit'}
            self._buckets[identity.subject] = window, count + 1
        if method == 'GET':
            if path.endswith('/capabilities'):
                return 200, {'version': 'v1', 'synthetic_only': True, 'inference': self.inference is not None,
                             'review_required': True, 'approval_endpoint': False}
            if path.endswith('/metrics'):
                return 200, self.gateway.metrics(grant.actor, grant.scope)
            health = self.gateway.health()
            return (200 if health.get('status') == 'ready' else 503), health
        if env.get('CONTENT_TYPE', '').split(';')[0].strip().lower() != 'application/json':
            return 415, {'error': 'json_required'}
        length = env.get('CONTENT_LENGTH', '')
        if type(length) is not str or not length.isascii() or not length.isdecimal():
            return 411, {'error': 'content_length_required'}
        if len(length) > 8 or int(length) > 12000:
            return 413, {'error': 'body_limit'}
        raw = env['wsgi.input'].read(int(length))
        # Uploads can stall after initial authentication. Expiry and local
        # capability revocation must still win before parsing or acting.
        if identity.expires_at <= int(time.time()):
            return 401, {'error': 'invalid_identity'}
        self.gateway._require(grant.actor, grant.scope, permission, allow_revoked=maintenance)
        if len(raw) != int(length):
            raise ValueError('incomplete body')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate JSON field')
                result[key] = value
            return result
        body = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        if type(body) is not dict:
            raise ValueError('object required')
        if body.get('clinic_id') != grant.clinic_id or body.get('patient_id') != grant.patient_id:
            raise PermissionError('clinical context denied')
        base = {'clinic_id', 'patient_id'}
        if path in ('/v1/memory/scopes/revoke', '/v1/memory/scopes/current'):
            if set(body) != base:
                raise ValueError('exact scope lifecycle schema required')
            if method == 'DELETE':
                return 200, self.gateway.delete_scope(grant.actor, scope=grant.scope)
            return 200, self.gateway.revoke_scope(grant.actor, scope=grant.scope,
                                                 evaluator_id='api-host-review')
        if path == '/v1/inference/respond':
            if self.inference is None:
                if set(body) not in (base, base | {'query', 'limit'}):
                    raise ValueError('exact inference schema required')
                return 501, {'error': 'inference_not_implemented', 'synthetic_only': True}
            if set(body) != base | {'query', 'limit'}:
                raise ValueError('exact inference schema required')
            result = self.inference.respond(self.gateway, grant.actor,
                MemoryRequest(grant.scope, body['query'], limit=body['limit']))
            if identity.expires_at <= int(time.time()):
                return 401, {'error': 'invalid_identity'}
            self.gateway._require(grant.actor, grant.scope, 'read')
            return 200, result
        if path.endswith('/query'):
            if set(body) != base | {'query', 'limit'}:
                raise ValueError('exact query schema required')
            result = self.gateway.retrieve(grant.actor, MemoryRequest(grant.scope, body['query'], limit=body['limit']))
            # Trusted records are evidence data, not instructions or clinical decisions.
            return 200, {'records': [asdict(record) for record in result.records],
                         'kv_status': result.kv_status, 'fallback_reason': result.fallback_reason,
                         'source_digest': result.source_digest, 'review_required': True,
                         'synthetic_only': True}
        if path.endswith('/experiences') or path.endswith('/feedback'):
            if set(body) != base | {'content', 'source_id'}:
                raise ValueError('exact proposal schema required')
            memory_id = self.gateway.propose(grant.actor, scope=grant.scope,
                content=body['content'], source_id=body['source_id'], kind='episodic')
            return 201, {'memory_id': memory_id, 'status': 'pending', 'synthetic_only': True}
        if record_id:
            if set(body) != base:
                raise ValueError('exact deletion schema required')
            return 200, self.gateway.delete(grant.actor, record_id, scope=grant.scope)
        if set(body) != base | {'memory_id'}:
            raise ValueError('exact revocation schema required')
        return 200, self.gateway.revoke(grant.actor, body['memory_id'], scope=grant.scope,
                                       evaluator_id='api-host-review')
