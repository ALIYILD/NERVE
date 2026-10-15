#!/usr/bin/env python3
"""Eight real completions, scored before/after deterministic synthetic registry grounding."""
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
from nerve_awim.memory_gateway.grounding import RegistryGroundingTask
from nerve_awim.memory_gateway.grounding_v2 import GroundedRegistryAdapterV2
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_v1 = _load('grounded_study_v1_helpers', 'benchmark_grounded_registry.py')
_bench = _v1._bench
_ready = _v1._ready
MODEL, ORIGIN, metadata, _claim, preload = _bench.MODEL, _bench.ORIGIN, _bench.metadata, _bench._claim, _ready.preload
CASES = (('AL35', 'ZNKT-8204', 'BM72', 'HRQU-1569'),
         ('CN86', 'DWFA-3971', 'DO21', 'YVSC-6408'),
         ('EP49', 'GJIM-5826', 'FQ63', 'BXLO-9137'),
         ('GR18', 'UPHE-2640', 'HS94', 'MAZR-7053'))


def judge_output(output, *, target, expected, source, arm):
    """Independent frozen answer contract; does not call the guard's parser."""
    if type(output) is not str:
        return False
    if arm == 'control':
        return output.strip().lower() in {
            'abstain', 'unknown', 'unsupported',
            'unsupported registry answer; abstaining.',
            'no approved evidence available; abstaining.'}
    if arm != 'relevant':
        raise ValueError('unknown arm')
    # A short answer inherits the explicit query entity. A sentence must name
    # that entity exactly. Correct citation is mandatory; no arbitrary prose.
    patterns = (
        re.escape(expected) + r' (?:[Ss]ource_id: )?' + re.escape(source) + r'\.?',
        re.escape(expected) + r', [Ss]ource_id: ' + re.escape(source),
        r'The access code for object ' + re.escape(target) + r' is ' + re.escape(expected)
        + r'\. [Ss]ource_id: ' + re.escape(source) + r'\.?')
    return any(re.fullmatch(pattern, output) is not None for pattern in patterns)


RecordingAdapter = _v1.RecordingAdapter
_source_hashes = _v1._source_hashes


def _persist(database, run_id, report):
    with sqlite3.connect(database, timeout=5) as db:
        db.execute('CREATE TABLE IF NOT EXISTS grounded_registry_evidence_v2 (run_id TEXT PRIMARY KEY, report TEXT NOT NULL)')
        db.execute('INSERT OR REPLACE INTO grounded_registry_evidence_v2 VALUES (?,?)', (run_id, json.dumps(report, sort_keys=True)))
        db.execute('UPDATE local_model_studies SET status=? WHERE run_id=?', (report['status'], run_id))


def run(database, run_id, expected_digest):
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}', expected_digest):
        raise ValueError('full operator-pinned SHA256 required')
    root = Path(__file__).parents[1]
    sources = [Path(__file__), Path(__file__).with_name('benchmark_grounded_registry.py'), Path(__file__).with_name('benchmark_local_memory.py'),
               Path(__file__).with_name('probe_local_memory_readiness.py')]
    sources += [root / 'src/nerve_awim' / name for name in
                ('memory_gateway/grounding_v2.py', 'memory_gateway/grounding.py', 'memory_gateway/inference.py', 'memory_gateway/gateway.py', 'memory_gateway/policy.py',
                 'memory_gateway/contracts.py', 'memory_v18.py', 'memory_retrieval_v18.py')]
    protocol = {'version': 'grounded-registry-v2', 'dataset_sha256': _bench._hash(CASES), 'cases': CASES,
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
              'score_definition': 'V2 frozen independent full-match contract (space or comma-space code/citation separator): correct target entity (explicit or query-implied), exact code and source citation; control approved abstention forms only. Strict synthetic contract accuracy, not general semantic correctness.',
              'control_definition': 'Approved equal-character-length irrelevant object fact. Raw and guarded outputs are evaluated on the SAME completion; no extra inference.',
              'limitation': 'Four fresh public synthetic cases. Raw versus v2 guard on same completion only; no v1 same-case baseline, general intelligence, training, or performance improvement claim.'}
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
        recorder = RecordingAdapter(adapter)
        guarded = GroundedRegistryAdapterV2(recorder)
        with tempfile.TemporaryDirectory(prefix='nerve-grounded-evidence-') as directory:
            authority = MemoryAuthority()
            writer = authority.issue('synthetic', 'cpu-study', permissions=('read', 'propose', 'approve'))
            reader = authority.issue('synthetic', 'cpu-study', permissions=('read',))
            gateway = MemoryGateway(TrustedMemoryLedger(Path(directory) / 'memory.sqlite', authority))
            for i, (target, expected, decoy, other) in enumerate(CASES):
                task = RegistryGroundingTask(target)
                query = task.query
                for arm in (('relevant', 'control') if i % 2 == 0 else ('control', 'relevant')):
                    scope = MemoryScope('synthetic', 'cpu-study', f'case-{i}-{arm}')
                    source = f'grounded-v2-source-{i}'
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
                        result = guarded.respond(gateway, reader, request, task=task)
                        usage = result['usage']
                        if (result['status'] not in ('generated_requires_review', 'abstained')
                                or set(usage) != {'prompt_tokens', 'completion_tokens', 'total_tokens'}
                                or any(type(v) is not int or v < 0 for v in usage.values())
                                or usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']
                                or type(result['output']) is not str):
                            raise ValueError('measured real completion required')
                        raw = recorder.last['output']
                        score_args = dict(target=target, expected=expected, source=source, arm=arm)
                        row.update(status='complete', raw_output=raw, guarded_output=result['output'], usage=usage,
                                   grounding=result['grounding'],
                                   raw_correct=judge_output(raw, **score_args),
                                   guarded_correct=judge_output(result['output'], **score_args))
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
                f'{arm}_{version}_correct': sum(r[version + '_correct'] for r in report['rows'] if r['arm'] == arm)
                for arm in ('relevant', 'control') for version in ('raw', 'guarded')}
            report['counts']['citations_added'] = sum(r['grounding']['citation_added'] for r in report['rows'])

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
