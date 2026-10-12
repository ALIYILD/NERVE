"""Strict operator-owned synthetic runtime configuration; never request input.

Configuration and public signing keys are validated before touching the ledger.
The returned gateway remains trusted host infrastructure, not an agent API.
"""
from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

from ..memory_v18 import MemoryAuthority, TrustedMemoryLedger
from ..oidc_v27 import PinnedOIDCVerifier
from .galahad_adapter import GalahadKVProvider
from .gateway import MemoryGateway
from .null_kv_adapter import NullKVProvider
from .service import MemoryGrant, MemoryService, synthetic_scope
from .session import BoundMemorySession


_CONFIG_FIELDS = {'version', 'synthetic_only', 'ledger_path', 'provider',
                  'max_records_per_scope', 'oidc', 'grants'}
_GRANT_FIELDS = {'subject', 'tenant_id', 'agent_id', 'application', 'user',
                 'clinic_id', 'patient_id', 'session_id', 'roles'}


def _exact(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise ValueError('exact configuration schema required')


def _text(value, limit):
    if type(value) is not str or not 1 <= len(value) <= limit or any(ord(c) < 32 for c in value):
        raise ValueError('bounded configuration text required')
    return value


def _read_json(path, *, limit):
    # Bounded read also protects against files changing between stat and read.
    with Path(path).open('rb') as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('configuration size limit')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate configuration key')
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError('nonfinite configuration number')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=nonfinite)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('invalid configuration JSON') from exc


def _path(value, base_dir):
    path = Path(_text(value, 4096))
    return (base_dir / path).resolve() if not path.is_absolute() else path.resolve()


def _public_verifier(oidc, base_dir):
    _exact(oidc, {'issuer', 'audience', 'jwks_path'})
    issuer = _text(oidc['issuer'], 2048)
    parsed = urlsplit(issuer)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ValueError('pinned HTTPS issuer required')
    audience = _text(oidc['audience'], 256)
    path = _path(oidc['jwks_path'], base_dir)
    jwks = _read_json(path, limit=65536)
    _exact(jwks, {'keys'})
    if type(jwks['keys']) is not list or not 1 <= len(jwks['keys']) <= 16:
        raise ValueError('bounded public JWKS required')
    seen = set()
    for key in jwks['keys']:
        if (type(key) is not dict or not {'kty', 'kid', 'n', 'e'} <= set(key)
                or not set(key) <= {'kty', 'kid', 'n', 'e', 'alg', 'use', 'key_ops'}
                or key['kty'] != 'RSA' or key.get('alg', 'RS256') != 'RS256'
                or key.get('use', 'sig') != 'sig'
                or key.get('key_ops', ['verify']) != ['verify']):
            raise ValueError('public RSA signing keys only; private key material forbidden')
        kid = _text(key['kid'], 128)
        _text(key['n'], 2048)
        _text(key['e'], 16)
        if kid in seen:
            raise ValueError('duplicate public key ID')
        seen.add(kid)
    verifier = PinnedOIDCVerifier(issuer=issuer, audience=audience, jwks=jwks)
    if any(key.key_size < 2048 for key in verifier.keys.values()):
        raise ValueError('RSA signing keys must be at least 2048 bits')
    return verifier, path


@dataclass(frozen=True)
class MemoryRuntime:
    service: MemoryService
    gateway: MemoryGateway
    sessions: MappingProxyType


def build_runtime(config, *, base_dir, required_subject=None):
    """Trusted host factory. All config and grants validate before DB creation."""
    _exact(config, _CONFIG_FIELDS)
    if type(config['version']) is not int or config['version'] != 1 or config['synthetic_only'] is not True:
        raise ValueError('version 1 synthetic-only runtime required')
    if config['provider'] not in ('null', 'galahad'):
        raise ValueError('unsupported memory provider')
    quota = config['max_records_per_scope']
    if type(quota) is not int or not 1 <= quota <= 10000:
        raise ValueError('bounded scope quota required')
    base_dir = Path(base_dir).resolve()
    ledger_path = _path(config['ledger_path'], base_dir)
    if not ledger_path.parent.is_dir() or (ledger_path.exists() and not ledger_path.is_file()):
        raise ValueError('existing ledger parent directory required')
    verifier, jwks_path = _public_verifier(config['oidc'], base_dir)
    if ledger_path == jwks_path:
        raise ValueError('ledger and key file must be separate')
    grants = config['grants']
    if type(grants) is not list or not 1 <= len(grants) <= 64:
        raise ValueError('one to 64 configured principals required')
    validated, subjects = [], set()
    for grant in grants:
        _exact(grant, _GRANT_FIELDS)
        subject = _text(grant['subject'], 256)
        if subject in subjects:
            raise ValueError('unique subject grants required')
        subjects.add(subject)
        roles = grant['roles']
        if (type(roles) is not list or not 1 <= len(roles) <= 3
                or any(type(role) is not str for role in roles)
                or len(set(roles)) != len(roles) or not set(roles) <= {'reader', 'writer', 'admin'}):
            raise ValueError('explicit reader/writer/admin roles required')
        scope = synthetic_scope(grant['tenant_id'], grant['agent_id'],
            application=grant['application'], user=grant['user'], clinic=grant['clinic_id'],
            patient=grant['patient_id'], session=grant['session_id'])
        validated.append((subject, scope, grant['clinic_id'], grant['patient_id'], frozenset(roles)))
    if required_subject is not None:
        _text(required_subject, 256)
        if not any(subject == required_subject and roles & {'reader', 'writer'}
                   for subject, _, _, _, roles in validated):
            raise ValueError('configured reader or writer subject required')
    # Everything above is read-only. Neither invalid late grants nor bad keys
    # may leave a new database or mutate an existing ledger.
    authority = MemoryAuthority()
    host_grants = []
    for subject, scope, clinic, patient, roles in validated:
        permissions = {'read'}
        if 'writer' in roles:
            permissions.add('propose')
        if 'admin' in roles:
            permissions.update(('approve', 'delete'))
        actor = authority.issue(scope.tenant_id, scope.agent_id, permissions=permissions)
        host_grants.append(MemoryGrant(subject, actor, scope, clinic, patient, roles))
    provider = NullKVProvider() if config['provider'] == 'null' else GalahadKVProvider()
    ledger = TrustedMemoryLedger(ledger_path, authority)
    gateway = MemoryGateway(ledger, provider=provider, max_records_per_scope=quota)
    service = MemoryService(gateway, verifier=verifier, grants=host_grants)
    sessions = {grant.subject: BoundMemorySession(gateway, grant.actor, grant.scope,
                can_read='reader' in grant.roles, can_propose='writer' in grant.roles)
                for grant in host_grants if grant.roles & {'reader', 'writer'}}
    return MemoryRuntime(service, gateway, MappingProxyType(sessions))


def load_runtime(config_path, *, required_subject=None):
    """Read a bounded, duplicate-free JSON config relative to its directory."""
    path = Path(config_path).resolve()
    config = _read_json(path, limit=131072)
    if type(config) is dict and 'ledger_path' in config:
        if _path(config['ledger_path'], path.parent) == path:
            raise ValueError('configuration and ledger must be separate')
    return build_runtime(config, base_dir=path.parent, required_subject=required_subject)
