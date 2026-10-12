#!/usr/bin/env python3
"""Eight-call, one-use synthetic local-model evidence smoke study (no training)."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from urllib.request import build_opener, ProxyHandler

from nerve_awim.memory_gateway.inference import LocalInferenceAdapter, _NoRedirect
from nerve_awim.memory_gateway.contracts import MemoryRequest, MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger

MODEL = 'qwen2.5-coder:1.5b'
ORIGIN = 'http://127.0.0.1:11434'
# Random-looking frozen synthetic facts, not externally sourced knowledge.
CASES = (('AX17', 'VEXQ-7319', 'BZ82', 'KULM-4826'),
         ('CP34', 'JARN-9264', 'DQ59', 'WOSP-1538'),
         ('ER62', 'PYFT-5083', 'FS71', 'NUDC-6742'),
         ('GT95', 'HBIK-2467', 'HU08', 'ZREL-8195'))


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def metadata(origin=ORIGIN):
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(origin + '/api/tags', timeout=5) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError('oversized model metadata')
    value = json.loads(raw)
    if type(value) is not dict or type(value.get('models')) is not list:
        raise ValueError('invalid model metadata')
    found = [m for m in value['models'] if type(m) is dict and m.get('name') == MODEL]
    if len(found) != 1 or not re.fullmatch('[0-9a-f]{64}', str(found[0].get('digest', ''))):
        raise ValueError('missing or ambiguous immutable model digest')
    return {'model': MODEL, 'digest': found[0]['digest']}


def _claim(database, run_id, protocol):
    if str(database) == ':memory:' or not re.fullmatch('[A-Za-z0-9_.-]{1,80}', run_id):
        raise ValueError('durable database and bounded run id required')
    with sqlite3.connect(database, timeout=5) as db:
        db.execute('CREATE TABLE IF NOT EXISTS local_model_studies (run_id TEXT PRIMARY KEY, dataset TEXT UNIQUE, protocol TEXT, status TEXT)')
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT count(*) FROM local_model_studies').fetchone()[0] >= 10000:
            raise ValueError('claim capacity exhausted')
        try:
            db.execute('INSERT INTO local_model_studies VALUES (?,?,?,?)',
                       (run_id, protocol['dataset_sha256'], json.dumps(protocol, sort_keys=True), 'consumed'))
        except sqlite3.IntegrityError:
            raise ValueError('run or dataset already consumed') from None


def run(database, run_id, expected_digest, *, _origin=ORIGIN):
    """Origin override is test-only; CLI has no endpoint/model override."""
    if not re.fullmatch('[0-9a-f]{64}', expected_digest):
        raise ValueError('full operator-pinned SHA256 required')
    protocol = {'version': 'local-model-evidence-v1', 'dataset_sha256': _hash(CASES),
                'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'dependency_sha256': {name: hashlib.sha256((Path(__file__).parents[1] / 'src/nerve_awim' / name).read_bytes()).hexdigest()
                                      for name in ('memory_gateway/inference.py', 'memory_gateway/gateway.py',
                                                   'memory_gateway/policy.py', 'memory_v18.py', 'memory_retrieval_v18.py')},
                'model': MODEL, 'expected_digest': expected_digest,
                'max_calls': 8, 'max_output_tokens': 128, 'temperature': 0,
                'timeout_seconds': 30, 'cases': CASES}
    _claim(database, run_id, protocol)
    rows = []
    report = {'protocol': protocol, 'run_id': run_id, 'rows': rows,
              'environment': {'python': platform.python_version(), 'platform': platform.platform()},
              'persistent_kv_restored': False, 'weight_training': False,
              'automatic_learning': False, 'synthetic_only': True,
              'score_definition': 'exact expected code token AND exact supplied source_id token inclusion; not semantic answer correctness',
              'control': 'approved equal-length irrelevant fact, same model and token cap',
              'limitation': 'four public synthetic cases; no statistical or general intelligence improvement claim'}
    try:
        before = metadata(_origin)
        if before['digest'] != expected_digest:
            raise ValueError('model digest mismatch')
        report['metadata_before'] = before
        adapter = LocalInferenceAdapter(base_url=_origin, model=MODEL, max_output_tokens=128, timeout_seconds=30)
        with tempfile.TemporaryDirectory(prefix='nerve-local-smoke-') as directory:
            authority = MemoryAuthority()
            writer = authority.issue('synthetic', 'smoke', permissions=('read', 'propose', 'approve'))
            reader = authority.issue('synthetic', 'smoke', permissions=('read',))
            gateway = MemoryGateway(TrustedMemoryLedger(Path(directory) / 'memory.sqlite', authority))
            for i, (target, expected, decoy, other) in enumerate(CASES):
                query = f'In the synthetic registry, what is the access code for object {target}? Return only the code and source_id; abstain if unsupported.'
                for arm in (('relevant', 'control') if i % 2 == 0 else ('control', 'relevant')):
                    scope = MemoryScope('synthetic', 'smoke', f'case-{i}-{arm}')
                    source = f'fixture-source-{i}'
                    obj, code = (target, expected) if arm == 'relevant' else (decoy, other)
                    content = f'The synthetic registry lists object {obj} with access code {code}.'
                    mid = gateway.propose(writer, scope=scope, content=content, source_id=source)
                    gateway.decide(writer, mid, scope=scope, approve=True, evaluator_id='synthetic-host')
                    request = MemoryRequest(scope, query, limit=1)
                    if len(gateway.retrieve(reader, request).records) != 1:
                        raise ValueError('arm must provide exactly one approved source')
                    start = time.perf_counter()
                    row = {'case': i, 'arm': arm, 'source_id': source, 'expected_code': expected}
                    rows.append(row)
                    try:
                        result = adapter.respond(gateway, reader, request)
                        if (result['status'] != 'generated_requires_review'
                                or set(result['usage']) != {'prompt_tokens', 'completion_tokens', 'total_tokens'}
                                or result['usage']['total_tokens'] != result['usage']['prompt_tokens'] + result['usage']['completion_tokens']):
                            raise ValueError('real completion with measured usage required')
                        output = result['output']
                        code_hit = bool(re.search(r'(?<![A-Za-z0-9_-])' + re.escape(expected) + r'(?![A-Za-z0-9_-])', output))
                        citation = bool(re.search(r'(?<![A-Za-z0-9_-])' + re.escape(source) + r'(?![A-Za-z0-9_-])', output))
                        row.update(output=output, usage=result['usage'], code_hit=code_hit,
                                   citation_hit=citation, score=int(code_hit and citation), status='complete')
                    except Exception as exc:
                        row.update(status='failed', error_type=type(exc).__name__, score=0)
                        raise
                    finally:
                        row['end_to_end_seconds'] = time.perf_counter() - start
        after = metadata(_origin)
        report['metadata_after'] = after
        if after != before:
            raise ValueError('model digest changed during study')
        if len(rows) != 8:
            raise ValueError('incomplete matched study')
        report.update(status='complete', scores={arm: sum(r['score'] for r in rows if r['arm'] == arm)
                                                 for arm in ('relevant', 'control')})
    except Exception as exc:
        report.update(status='failed_consumed', error_type=type(exc).__name__)
    with sqlite3.connect(database) as db:
        db.execute('UPDATE local_model_studies SET status=? WHERE run_id=?', (report['status'], run_id))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('database', 'output', 'run-id', 'expected-digest'):
        parser.add_argument('--' + arg, required=True)
    args = parser.parse_args()
    if Path(args.database).resolve() == Path(args.output).resolve():
        parser.error('output and claim database must differ')
    with open(args.output, 'x') as output:
        report = run(args.database, args.run_id, args.expected_digest)
        json.dump(report, output, indent=2)
        output.write('\n')
    print(json.dumps({key: report[key] for key in ('status', 'scores') if key in report}))
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
