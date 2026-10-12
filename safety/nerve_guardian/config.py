"""Pure deployment schema checks: no filesystem, credential or network access."""
import math
import os
import re
from urllib.parse import urlsplit


def _object(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError('invalid configuration fields')


def _text(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 4096 or any(ord(c) < 32 for c in value):
        raise ValueError('bounded configuration string required')


def _label(value):
    _text(value)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', value):
        raise ValueError('bounded administrative identifier required')


def _path(value):
    _text(value)
    if not os.path.isabs(value) or os.path.normpath(value) != value or value == '/':
        raise ValueError('absolute normalized configuration path required')


def _number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('bounded configuration number required')


def _list(value, maximum, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError('bounded configuration list required')


def _https(value):
    _text(value)
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('HTTPS configuration URL required')
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('invalid HTTPS port')


def validate_config(config, kind=None):
    """Validate structure only; success does not establish deployment readiness."""
    if not isinstance(config, dict):
        raise ValueError('configuration object required')
    if kind is None:
        if ('tenants' in config) == ('sources' in config):
            raise ValueError('exactly one Guardian or Watchtower configuration required')
        kind = 'guardian' if 'tenants' in config else 'watchtower'
    _number(config.get('interval_seconds', 5), .25, 60)
    if kind == 'watchtower':
        _object(config, ('sources', 'report_path', 'interval_seconds'), ('sources', 'report_path'))
        _path(config['report_path'])
        _list(config['sources'], 128, 1)
        from .telemetry import _TABLES
        seen = set()
        for source in config['sources']:
            _object(source, ('path', 'tenant', 'source', 'tables', 'max_seconds'), ('path', 'tenant', 'source'))
            _path(source['path']); _label(source['tenant']); _label(source['source'])
            key = source['source']
            if key in seen or source['path'] == config['report_path']:
                raise ValueError('duplicate source or report overwrites input')
            seen.add(key)
            tables = source.get('tables', ['gl_events'])
            _list(tables, len(_TABLES), 1)
            if any(not isinstance(t, str) or t not in _TABLES for t in tables) or len(set(tables)) != len(tables):
                raise ValueError('unique allowlisted tables required')
            _number(source.get('max_seconds', .1), .001, 2)
    elif kind == 'guardian':
        _object(config, ('armed', 'state_directory', 'anchor_directory', 'enforcement_directory', 'interval_seconds',
                         'dashboard_url', 'portal_port', 'owners', 'notifications', 'tenants', 'identity'),
                        ('state_directory', 'anchor_directory', 'enforcement_directory', 'tenants'))
        if type(config.get('armed', False)) is not bool:
            raise ValueError('armed must be a boolean')
        directories = [config[key] for key in ('state_directory', 'anchor_directory', 'enforcement_directory')]
        for path in directories: _path(path)
        if any(a == b or a.startswith(b + '/') or b.startswith(a + '/') for i, a in enumerate(directories) for b in directories[i+1:]):
            raise ValueError('independent state directories must not overlap')
        if 'dashboard_url' in config: _https(config['dashboard_url'])
        port = config.get('portal_port', 8787)
        if type(port) is not int or not 1 <= port <= 65535: raise ValueError('invalid portal port')
        tenants = config['tenants']
        if not isinstance(tenants, dict) or not 1 <= len(tenants) <= 128: raise ValueError('bounded tenant inventory required')
        units = set()
        for tenant, entry in tenants.items():
            _label(tenant)
            _object(entry, ('units', 'watchtower_report', 'telemetry_sources', 'protected_files'), ('units',))
            _list(entry['units'], 128, 1)
            for unit in entry['units']:
                _object(unit, ('name', 'clinical', 'shared'), ('name',))
                name = unit['name']; _text(name)
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*\.service', name) or len(name) > 255:
                    raise ValueError('literal service name required')
                if name in units or any(s in name.lower() for s in ('guardian', 'watchtower')):
                    raise ValueError('duplicate or observer workload prohibited')
                if any(unit.get(flag, False) is not False for flag in ('clinical', 'shared')):
                    raise ValueError('clinical/shared workloads prohibited')
                units.add(name)
            sources = entry.get('telemetry_sources', [])
            _list(sources, 128)
            for source in sources: _label(source)
            if len(set(sources)) != len(sources): raise ValueError('duplicate telemetry source')
            if 'watchtower_report' in entry: _path(entry['watchtower_report'])
            elif sources: raise ValueError('telemetry sources require a report')
            pins = entry.get('protected_files', {})
            if not isinstance(pins, dict) or len(pins) > 128: raise ValueError('bounded protected file pins required')
            for path, digest in pins.items():
                _path(path)
                if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest): raise ValueError('SHA256 pin required')
        owners = config.get('owners', {})
        if not isinstance(owners, dict) or len(owners) > 128: raise ValueError('bounded owners required')
        for owner, tenant in owners.items():
            _text(owner); _label(tenant)
            if tenant not in tenants: raise ValueError('owner tenant absent from inventory')
        if 'identity' in config:
            identity = config['identity']
            _object(identity, ('issuer', 'audience', 'public_key_files', 'mfa_acr'), ('issuer', 'audience', 'public_key_files'))
            _https(identity['issuer']); _text(identity['audience'])
            keys = identity['public_key_files']
            if not owners or not isinstance(keys, dict) or not 1 <= len(keys) <= 32: raise ValueError('owner identities and pinned keys required')
            for kid, path in keys.items(): _text(kid); _path(path)
            _list(identity.get('mfa_acr', []), 32)
            for acr in identity.get('mfa_acr', []): _text(acr)
        channels = config.get('notifications', {})
        _object(channels, ('email', 'telegram'))
        for channel, entry in channels.items():
            _object(entry, ('endpoint', 'secret_path', 'recipient', 'sender'), ('endpoint', 'secret_path', 'recipient'))
            _https(entry['endpoint']); _path(entry['secret_path']); _text(entry['recipient'])
            if channel == 'telegram' and entry['endpoint'] != 'https://api.telegram.org': raise ValueError('Telegram endpoint must be pinned')
            if channel == 'email': _text(entry.get('sender'))
            elif 'sender' in entry: raise ValueError('Telegram sender is not configurable')
    else:
        raise ValueError('unknown configuration kind')
    return {'valid_schema': True, 'kind': kind, 'armed': config.get('armed', False), 'production_readiness': 'unverified'}
