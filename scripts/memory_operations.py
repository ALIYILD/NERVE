"""Offline synthetic operations checks; no server deployment or clinical data."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time

from nerve_awim.memory_gateway.contracts import MemoryScope, MemoryRequest, MemoryMetrics
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_gateway.null_kv_adapter import NullKVProvider
from nerve_awim.memory_gateway.observability import atomic_json, make_manifest, readiness, read_manifest, prometheus_metrics
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger

ROOT = Path(__file__).resolve().parents[1]


def fingerprint():
    digest = sha256()
    for directory in ('src', 'scripts', 'tests', '.github', 'deploy'):
        for path in sorted((ROOT/directory).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                digest.update(str(path.relative_to(ROOT)).encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def revision():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=5).strip()


def faults():
    checks = []
    with tempfile.TemporaryDirectory() as directory:
        authority = MemoryAuthority()
        actor = authority.issue('synthetic-tenant', 'synthetic-agent', permissions=('read', 'propose', 'approve', 'delete'))
        scope = MemoryScope('synthetic-tenant', 'synthetic-agent', 'synthetic-context')
        path = Path(directory)/'memory.sqlite'
        ledger = TrustedMemoryLedger(path, authority)
        gateway = MemoryGateway(ledger, max_records_per_scope=1)
        mid = gateway.propose(actor, scope=scope, content='synthetic calibration fixture', source_id='fixture')
        gateway.decide(actor, mid, scope=scope, approve=True, evaluator_id='synthetic-host')
        reopened = MemoryGateway(TrustedMemoryLedger(path, authority), max_records_per_scope=1)
        checks.append({'name': 'restart', 'passed': len(reopened.retrieve(actor, MemoryRequest(scope, 'calibration')).records) == 1, 'count': 1})
        limited = False
        try:
            reopened.propose(actor, scope=scope, content='synthetic extra fixture', source_id='extra')
        except ValueError:
            limited = True
        checks.append({'name': 'quota', 'passed': limited, 'count': 1})
        class FailedProvider(NullKVProvider):
            def invalidate(self, scope):
                raise OSError('synthetic unavailable provider')
        reopened.provider = FailedProvider()
        result = reopened.revoke(actor, mid, scope=scope, evaluator_id='synthetic-host')
        checks.append({'name': 'failed_invalidation', 'passed': result['cache_purge_confirmed'] is False
                       and not reopened.retrieve(actor, MemoryRequest(scope, 'calibration')).records, 'count': 1})
        # Temporary fixture only. No supplied or real operator store is touched.
        backup = path.with_suffix('.backup')
        path.rename(backup)
        checks.append({'name': 'unavailable_database', 'passed': reopened.health()['status'] == 'unavailable' and not path.exists(), 'count': 1})
        path.write_bytes(b'not a sqlite database: synthetic corruption')
        denied = False
        try:
            reopened.retrieve(actor, MemoryRequest(scope, 'calibration'))
        except sqlite3.Error:
            denied = True
        checks.append({'name': 'corrupt_database', 'passed': denied and reopened.health()['status'] == 'unavailable', 'count': 1})
    return checks


def verify(gate):
    command = [sys.executable, str(ROOT/'scripts/verify_galahad.py'), gate]
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT/'src')},
                            capture_output=True, text=True, timeout=1800)
    output = result.stderr + result.stdout
    counts = re.findall(r'Ran (\d+) tests?', output)
    skips = re.findall(r'\bskipped=(\d+)', output)
    return [{'name': 'unittest_suite', 'passed': result.returncode == 0 and bool(counts)
             and not any(int(count) > 0 for count in skips),
             'count': max(1, sum(map(int, counts)))}]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('faults', 'verify', 'readiness', 'metrics'))
    parser.add_argument('--gate', choices=('cpu', 'security', 'api'))
    parser.add_argument('--output')
    parser.add_argument('--evidence', nargs='*', default=[])
    parser.add_argument('--counters')
    args = parser.parse_args(argv)
    if args.operation == 'metrics':
        if not args.counters:
            parser.error('--counters required')
        with open(args.counters, 'rb') as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            parser.error('counter input too large')
        print(prometheus_metrics(json.loads(raw)), end='')
        return 0
    if args.operation == 'readiness':
        if len(args.evidence) > 4:
            parser.error('at most four gate manifests')
        report = readiness([read_manifest(p) for p in args.evidence], revision=revision(), source_sha256=fingerprint())
        if args.output:
            atomic_json(args.output, report)
        print(json.dumps(report, sort_keys=True))
        return 0 if report['cpu_research_ready'] else 2
    if not args.output or (args.operation == 'verify' and args.gate is None):
        parser.error('--output required; verify also requires --gate')
    started = time.monotonic()
    before = fingerprint()
    try:
        checks = faults() if args.operation == 'faults' else verify(args.gate)
    except subprocess.TimeoutExpired:
        checks = [{'name': 'unittest_suite', 'passed': False, 'count': 1}]
    if before != fingerprint():
        parser.error('source changed during verification; rerun on stable checkout')
    manifest = make_manifest('faults' if args.operation == 'faults' else args.gate,
                             revision(), before, checks, round(time.monotonic() - started, 6))
    atomic_json(args.output, manifest)
    print(json.dumps({'gate': manifest['gate'], 'passed': all(c['passed'] for c in checks), 'checks': len(checks)}))
    return 0 if all(c['passed'] for c in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
