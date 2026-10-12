"""Metadata-only operations evidence. No credentials, scopes or source payloads."""
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
from uuid import uuid4

from .contracts import MemoryMetrics

GATES = ('cpu', 'security', 'api', 'faults')
LIFECYCLE_EVENTS = frozenset(('scope_revoked', 'scope_deleted', 'source_revoked', 'source_deleted', 'provider_invalidation_failed'))

def build_audit_event(event, status):
    if type(event) is not str or event not in LIFECYCLE_EVENTS or type(status) is not str or status not in ('success', 'partial', 'failed'):
        raise ValueError('fixed lifecycle event and status required')
    return {'event': event, 'status': status, 'trace_id': uuid4().hex, 'created_at': int(time.time())}



def prometheus_metrics(counters):
    expected = asdict(MemoryMetrics())
    if type(counters) is not dict or set(counters) != set(expected):
        raise ValueError('exact gateway counters required')
    lines = []
    for name in sorted(expected):
        value = counters[name]
        if type(value) is not int or not 0 <= value <= 2**63 - 1:
            raise ValueError('nonnegative bounded integer counters required')
        metric = 'nerve_memory_' + name + '_total'
        lines.extend(('# TYPE ' + metric + ' counter', metric + ' ' + str(value)))
    return '\n'.join(lines) + '\n'


def atomic_json(path, value):
    """Atomic local artifact replacement, mode 0600; not encrypted storage."""
    raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b'\n'
    if len(raw) > 65536:
        raise ValueError('bounded evidence artifact required')
    target = Path(path)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix='.memory-evidence-')
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def make_manifest(gate, revision, source_sha256, checks, elapsed_seconds):
    value = {'schema': 1, 'gate': gate, 'revision': revision, 'created_at': int(time.time()),
             'checks': checks, 'elapsed_seconds': elapsed_seconds, 'source_sha256': source_sha256}
    validate_manifest(value)
    return value


def validate_manifest(value):
    if (type(value) is not dict or set(value) != {'schema', 'gate', 'revision', 'created_at', 'checks', 'elapsed_seconds', 'source_sha256'}
            or type(value['schema']) is not int or value['schema'] != 1 or value['gate'] not in GATES
            or type(value['revision']) is not str or not re.fullmatch('[0-9a-f]{40}', value['revision'])
            or type(value['source_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', value['source_sha256'])
            or type(value['created_at']) is not int or value['created_at'] < 0
            or type(value['elapsed_seconds']) not in (int, float)
            or not math.isfinite(value['elapsed_seconds']) or value['elapsed_seconds'] < 0
            or type(value['checks']) is not list or not 1 <= len(value['checks']) <= 30):
        raise ValueError('invalid operations manifest')
    names = set()
    for check in value['checks']:
        if (type(check) is not dict or set(check) != {'name', 'passed', 'count'}
                or type(check['name']) is not str or not re.fullmatch('[a-z0-9_]{1,64}', check['name'])
                or check['name'] in names or type(check['passed']) is not bool
                or type(check['count']) is not int or not 1 <= check['count'] <= 100000):
            raise ValueError('invalid check evidence')
        names.add(check['name'])
    return value


def read_manifest(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate evidence key')
            result[key] = value
        return result
    with Path(path).open('rb') as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError('evidence limit exceeded')
    return validate_manifest(json.loads(raw, object_pairs_hook=unique))


FAULT_CHECKS = frozenset(('restart', 'corrupt_database', 'unavailable_database', 'quota', 'failed_invalidation'))


def readiness(manifests, *, revision, source_sha256, now=None, max_age_seconds=86400):
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 604800:
        raise ValueError('evidence lifetime must be one second to seven days')
    if type(revision) is not str or not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('exact revision required')
    if type(source_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', source_sha256):
        raise ValueError('source fingerprint required')
    now = int(time.time()) if now is None else now
    if type(now) is not int or now < 0:
        raise ValueError('invalid clock')
    states = {gate: 'missing' for gate in GATES}
    seen = set()
    for value in manifests:
        validate_manifest(value)
        gate = value['gate']
        if gate in seen:
            raise ValueError('duplicate gate evidence')
        seen.add(gate)
        names = {c['name'] for c in value['checks']}
        required = FAULT_CHECKS if gate == 'faults' else {'unittest_suite'}
        if value['revision'] != revision:
            states[gate] = 'wrong_revision'
        elif value['source_sha256'] != source_sha256:
            states[gate] = 'changed_worktree'
        elif not 0 <= now - value['created_at'] <= max_age_seconds:
            states[gate] = 'stale_or_future'
        elif names != required:
            states[gate] = 'incomplete_checks'
        elif not all(c['passed'] for c in value['checks']):
            states[gate] = 'failed'
        else:
            states[gate] = 'pass'
    return {'cpu_research_ready': all(s == 'pass' for s in states.values()), 'gates': states,
            'gpu_restore': 'blocked_no_hardware_evidence', 'licence': 'unverified',
            'clinical': 'prohibited_without_separate_governance', 'deployed': False,
            'evidence_trust': 'operator_owned_local_manifests_not_signed_attestations'}
