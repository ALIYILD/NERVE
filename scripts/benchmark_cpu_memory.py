#!/usr/bin/env python3
"""One-use, eight-request synthetic matched evidence study on the CPU profile."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import re
import sqlite3
import tempfile
import time

from nerve_awim.memory_gateway.inference import LocalInferenceAdapter, InferenceUnavailable, _failure_reason
from nerve_awim.memory_gateway.contracts import MemoryRequest, MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_bench = _load('cpu_study_claims', 'benchmark_local_memory.py')
_ready = _load('cpu_study_readiness', 'probe_local_memory_readiness.py')
MODEL, ORIGIN, metadata, _claim, preload = _bench.MODEL, _bench.ORIGIN, _bench.metadata, _bench._claim, _ready.preload
CASES = (('JV24', 'MEZP-3618', 'KW63', 'QAHN-7952'),
         ('LX48', 'TUFG-2849', 'MY15', 'RCWD-6307'),
         ('NZ76', 'BOSK-9173', 'PA32', 'IELV-4526'),
         ('QB89', 'DYXR-5681', 'RC57', 'WJUM-3094'))


def _hit(value, output):
    return bool(re.search(r'(?<![A-Za-z0-9_-])' + re.escape(value) + r'(?![A-Za-z0-9_-])', output))


def _source_hashes(root, sources):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}


def _persist(database, run_id, report):
    with sqlite3.connect(database, timeout=5) as db:
        db.execute('CREATE TABLE IF NOT EXISTS cpu_memory_evidence (run_id TEXT PRIMARY KEY, report TEXT NOT NULL)')
        db.execute('INSERT OR REPLACE INTO cpu_memory_evidence VALUES (?,?)', (run_id, json.dumps(report, sort_keys=True)))
        db.execute('UPDATE local_model_studies SET status=? WHERE run_id=?', (report['status'], run_id))


def run(database, run_id, expected_digest):
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}', expected_digest):
        raise ValueError('full operator-pinned SHA256 required')
    root = Path(__file__).parents[1]
    sources = [Path(__file__), Path(__file__).with_name('benchmark_local_memory.py'),
               Path(__file__).with_name('probe_local_memory_readiness.py')]
    sources += [root / 'src/nerve_awim' / name for name in
                ('memory_gateway/inference.py', 'memory_gateway/gateway.py', 'memory_gateway/policy.py',
                 'memory_gateway/contracts.py', 'memory_v18.py', 'memory_retrieval_v18.py')]
    protocol = {'version': 'cpu-memory-evidence-v1', 'dataset_sha256': _bench._hash(CASES), 'cases': CASES,
                'source_sha256': _source_hashes(root, sources),
                'model': MODEL, 'origin': ORIGIN, 'expected_digest': expected_digest, 'runtime_profile': 'cpu_research',
                'max_inference_calls': 8, 'max_preload_calls': 1, 'max_metadata_calls': 2,
                'max_output_tokens': 128, 'inference_socket_timeout_seconds': 90,
                'preload_socket_timeout_seconds': 45, 'temperature': 0,
                'timeout_limit': 'socket timeout, not a hard total wall-clock deadline'}
    _claim(database, run_id, protocol)
    report = {'protocol': protocol, 'run_id': run_id, 'status': 'running', 'rows': [],
              'environment': {'python': platform.python_version(), 'platform': platform.platform()},
              'synthetic_only': True, 'weight_training': False, 'automatic_learning': False,
              'persistent_kv_restored': False, 'inference_attempts': 0, 'preload_attempts': 0,
              'score_definition': 'Relevant grounded extraction requires exact target code and supplied source_id token inclusion; not semantic correctness.',
              'control_definition': 'Approved equal-character-length irrelevant fact; unsupported target and decoy mentions are separate flags. Abstention indicator is lexical only, not semantic correctness.',
              'limitation': 'Four public synthetic cases; no general intelligence, training, or performance improvement claim.'}
    stage, before = 'metadata_before', None
    _persist(database, run_id, report)
    try:
        before = metadata()
        report['metadata_before'] = before
        if before['digest'] != expected_digest:
            raise ValueError('digest mismatch')
        stage = 'preload'
        report['preload_attempts'] = 1
        _persist(database, run_id, report)
        report['preload'] = preload()
        adapter = LocalInferenceAdapter(base_url=ORIGIN, model=MODEL, max_output_tokens=128,
                                        timeout_seconds=90, runtime_profile='cpu_research')
        with tempfile.TemporaryDirectory(prefix='nerve-cpu-evidence-') as directory:
            authority = MemoryAuthority()
            writer = authority.issue('synthetic', 'cpu-study', permissions=('read', 'propose', 'approve'))
            reader = authority.issue('synthetic', 'cpu-study', permissions=('read',))
            gateway = MemoryGateway(TrustedMemoryLedger(Path(directory) / 'memory.sqlite', authority))
            for i, (target, expected, decoy, other) in enumerate(CASES):
                query = f'In the synthetic registry, what is the access code for object {target}? Return only the code and source_id; abstain if unsupported.'
                for arm in (('relevant', 'control') if i % 2 == 0 else ('control', 'relevant')):
                    scope = MemoryScope('synthetic', 'cpu-study', f'case-{i}-{arm}')
                    source = f'cpu-source-{i}'
                    obj, code = (target, expected) if arm == 'relevant' else (decoy, other)
                    content = f'The synthetic registry lists object {obj} with access code {code}.'
                    mid = gateway.propose(writer, scope=scope, content=content, source_id=source)
                    gateway.decide(writer, mid, scope=scope, approve=True, evaluator_id='synthetic-host')
                    request = MemoryRequest(scope, query, limit=1)
                    if len(gateway.retrieve(reader, request).records) != 1:
                        raise ValueError('exactly one approved scoped fact required')
                    stage = 'inference'
                    row = {'case': i, 'arm': arm, 'source_id': source, 'expected_code': expected,
                           'decoy_code': other, 'status': 'attempted', 'fact_characters': len(content)}
                    report['rows'].append(row)
                    report['inference_attempts'] += 1
                    _persist(database, run_id, report)
                    start = time.perf_counter()
                    try:
                        result = adapter.respond(gateway, reader, request)
                        usage = result['usage']
                        if (result['status'] != 'generated_requires_review'
                                or set(usage) != {'prompt_tokens', 'completion_tokens', 'total_tokens'}
                                or any(type(v) is not int or v < 0 for v in usage.values())
                                or usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']
                                or type(result['output']) is not str):
                            raise ValueError('measured real completion required')
                        output = result['output']
                        target_hit, citation = _hit(expected, output), _hit(source, output)
                        row.update(status='complete', output=output, usage=usage,
                                   target_code_hit=target_hit, citation_hit=citation,
                                   decoy_code_present=_hit(other, output),
                                   abstention_indicator=bool(re.search(r'\b(?:unknown|unsupported|abstain|not available|not provided|cannot determine)\b', output, re.I)))
                        if arm == 'relevant':
                            row['grounded_extraction'] = target_hit and citation
                        else:
                            row['unsupported_target_code'] = target_hit
                    except BaseException as error:
                        row.update(status='failed', failure_reason=error.reason if isinstance(error, InferenceUnavailable) else _failure_reason(error))
                        if isinstance(error, InferenceUnavailable) and error.detail is not None:
                            row['failure_detail'] = error.detail
                        raise
                    finally:
                        row['end_to_end_seconds'] = time.perf_counter() - start
                        _persist(database, run_id, report)
        if len(report['rows']) != 8 or any(r['status'] != 'complete' for r in report['rows']):
            raise ValueError('eight complete matched requests required')
        report['status'] = 'awaiting_identity_check'
    except BaseException as error:
        report.update(status='failed_consumed', failure_stage=stage,
                      failure_reason=error.reason if isinstance(error, InferenceUnavailable) else _failure_reason(error))
        if isinstance(error, InferenceUnavailable) and error.detail is not None:
            report['failure_detail'] = error.detail
        if not isinstance(error, Exception):
            _persist(database, run_id, report)
            raise
    finally:
        # One post-run lookup also records identity after an inference/preload failure.
        if before is not None:
            try:
                after = metadata()
                report['metadata_after'] = after
                if after != before:
                    report.update(status='failed_consumed', identity_failure='digest_drift')
            except Exception as error:
                report.update(status='failed_consumed', identity_failure=_failure_reason(error))
        try:
            report['source_sha256_after'] = _source_hashes(root, sources)
            if report['source_sha256_after'] != protocol['source_sha256']:
                report.update(status='failed_consumed', source_failure='source_drift')
        except Exception as error:
            report.update(status='failed_consumed', source_failure=_failure_reason(error))
        if report['status'] == 'awaiting_identity_check':
            report['status'] = 'complete'
            report['counts'] = {
                'relevant_grounded_extractions': sum(r.get('grounded_extraction', False) for r in report['rows']),
                'control_unsupported_target_codes': sum(r.get('unsupported_target_code', False) for r in report['rows']),
                'control_decoy_mentions': sum(r['decoy_code_present'] for r in report['rows'] if r['arm'] == 'control'),
                'control_lexical_abstention_indicators': sum(r['abstention_indicator'] for r in report['rows'] if r['arm'] == 'control')}
        _persist(database, run_id, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('database', 'run-id', 'output', 'expected-digest'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    if Path(args.database).resolve() == Path(args.output).resolve():
        parser.error('output and database must differ')
    with open(args.output, 'x') as stream:
        report = run(args.database, args.run_id, args.expected_digest)
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('status', 'counts', 'failure_reason') if k in report}))
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
