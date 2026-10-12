#!/usr/bin/env python3
"""One preload and one approved synthetic probe; diagnostic, never an experiment.

Empty-prompt preloading follows https://docs.ollama.com/faq. No retries,
downloads, global settings, model unloads, or benchmark dataset reuse.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import re
import tempfile
import time
from urllib.request import Request, build_opener, ProxyHandler

from nerve_awim.memory_gateway.inference import LocalInferenceAdapter, InferenceUnavailable, _NoRedirect, _failure_reason
from nerve_awim.memory_gateway.contracts import MemoryRequest, MemoryScope
from nerve_awim.memory_gateway.gateway import MemoryGateway
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger

_spec = importlib.util.spec_from_file_location('readiness_benchmark_metadata', Path(__file__).with_name('benchmark_local_memory.py'))
_bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bench)
MODEL, ORIGIN, metadata = _bench.MODEL, _bench.ORIGIN, _bench.metadata


def preload():
    payload = {'model': MODEL, 'prompt': '', 'stream': False, 'keep_alive': '2m'}
    request = Request(ORIGIN + '/api/generate', data=json.dumps(payload).encode(), method='POST',
                      headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    start = time.perf_counter()
    with opener.open(request, timeout=45) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError('oversized preload response')
    result = json.loads(raw)
    if (type(result) is not dict or result.get('model') != MODEL
            or result.get('done') is not True or result.get('response') != ''):
        raise ValueError('invalid preload response')
    measured = {'wall_seconds': time.perf_counter() - start}
    for name in ('load_duration', 'total_duration'):
        if name in result:
            if type(result[name]) is not int or result[name] < 0:
                raise ValueError('invalid preload duration')
            measured[name + '_nanoseconds'] = result[name]
    return measured


def run(expected_digest):
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}', expected_digest):
        raise ValueError('full operator-pinned SHA256 required')
    report = {'version': 'local-memory-readiness-v2', 'model': MODEL,
              'expected_digest': expected_digest, 'synthetic_only': True,
              'diagnostic_only': True, 'persistent_kv_restored': False,
              'environment': {'python': platform.python_version(), 'platform': platform.platform()},
              'source_sha256': {str(path.relative_to(Path(__file__).parents[1])): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in (Path(__file__), Path(__file__).with_name('benchmark_local_memory.py'),
                                             Path(__file__).parents[1] / 'src/nerve_awim/memory_gateway/inference.py',
                                             Path(__file__).parents[1] / 'src/nerve_awim/memory_gateway/gateway.py')},
              'preload_attempted': False, 'inference_attempted': False, 'accepted_completions': 0,
              'weight_training': False, 'max_preload_calls': 1, 'max_inference_calls': 1,
              'preload_timeout_seconds': 45, 'inference_timeout_seconds': 30,
              'max_output_tokens': 32, 'limitation': 'single readiness probe; not accuracy or improvement evidence'}
    stage = 'metadata_before'
    stage_started = time.perf_counter()
    try:
        before = metadata()
        report['metadata_before'] = before
        if before['digest'] != expected_digest:
            raise ValueError('digest mismatch')
        stage = 'preload'
        stage_started = time.perf_counter()
        report['preload_attempted'] = True
        report['preload'] = preload()
        stage = 'approved_probe'
        stage_started = time.perf_counter()
        adapter = LocalInferenceAdapter(base_url=ORIGIN, model=MODEL, max_output_tokens=32, timeout_seconds=30)
        with tempfile.TemporaryDirectory(prefix='nerve-readiness-') as directory:
            authority = MemoryAuthority()
            writer = authority.issue('synthetic', 'readiness', permissions=('read', 'propose', 'approve'))
            reader = authority.issue('synthetic', 'readiness', permissions=('read',))
            gateway = MemoryGateway(TrustedMemoryLedger(Path(directory) / 'memory.sqlite', authority))
            scope = MemoryScope('synthetic', 'readiness', 'probe')
            mid = gateway.propose(writer, scope=scope, content='Synthetic readiness marker is READY42.', source_id='readiness-source')
            gateway.decide(writer, mid, scope=scope, approve=True, evaluator_id='synthetic-host')
            request = MemoryRequest(scope, 'What is synthetic readiness marker? Return value and source_id.', limit=1)
            start = time.perf_counter()
            report['inference_attempted'] = True
            result = adapter.respond(gateway, reader, request)
            elapsed = time.perf_counter() - start
            usage = result['usage']
            if (result['status'] != 'generated_requires_review'
                    or set(usage) != {'prompt_tokens', 'completion_tokens', 'total_tokens'}
                    or usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']):
                raise ValueError('measured completion required')
        # Do not publish generated output/score unless immutable identity survives.
        stage = 'metadata_after'
        stage_started = time.perf_counter()
        after = metadata()
        report['metadata_after'] = after
        if after != before:
            raise ValueError('digest drift')
        output = result['output']
        hits = [bool(re.search(r'(?<![A-Za-z0-9_-])' + re.escape(value) + r'(?![A-Za-z0-9_-])', output))
                for value in ('READY42', 'readiness-source')]
        report.update(status='ready', accepted_completions=1, probe={'output': output, 'usage': usage,
                      'wall_seconds': elapsed, 'marker_hit': hits[0], 'source_hit': hits[1],
                      'diagnostic_score': int(all(hits)), 'review_required': True})
    except Exception as error:
        report.update(status='not_ready', failure_stage=stage,
                      failure_stage_seconds=time.perf_counter() - stage_started,
                      failure_reason=error.reason if isinstance(error, InferenceUnavailable) else _failure_reason(error))
        if isinstance(error, InferenceUnavailable) and getattr(error, 'detail', None) is not None:
            report['failure_detail'] = error.detail
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--expected-digest', required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch('[0-9a-f]{64}', args.expected_digest):
        parser.error('full operator-pinned SHA256 required')
    # Reserve the evidence file before any network activity.
    with open(args.output, 'x') as output:
        report = run(args.expected_digest)
        json.dump(report, output, indent=2)
        output.write('\n')
    print(json.dumps({key: report[key] for key in ('status', 'failure_stage', 'failure_reason', 'failure_detail') if key in report}))
    return 0 if report['status'] == 'ready' else 1


if __name__ == '__main__':
    raise SystemExit(main())
