#!/usr/bin/env python3
"""Real HTTP evidence capture against an operator-run inference endpoint.

This never launches/restarts a runtime or verifies a proprietary licence. The
historical smoke filename does NOT mean tensor restoration is established.
Capture and compare succeed independently of the BLOCKED full KV release gate.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCHEMA = 'nerve-runtime-observation-v1'
PHASES = ('cold', 'warm', 'after-restart')
METRICS = frozenset(('process_start_time_seconds', 'vllm:prefix_cache_hits_total',
    'vllm:external_prefix_cache_hits_total', 'vllm:prompt_tokens_cached_total',
    'vllm:prefix_cache_hits', 'vllm:external_prefix_cache_hits', 'vllm:prompt_tokens_cached'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _text(value, maximum):
    if type(value) is not str or not 1 <= len(value) <= maximum or any(ord(c) < 32 for c in value):
        raise ValueError('invalid_bounded_text')
    return value


def endpoint_origin(endpoint, allow_loopback_http=False):
    parsed = urlsplit(_text(endpoint, 2048))
    if (parsed.username or parsed.password or parsed.query or parsed.fragment
            or not parsed.hostname or parsed.path not in ('', '/')
            or parsed.scheme not in ('http', 'https')):
        raise ValueError('https_origin_required')
    if parsed.scheme == 'http' and not (allow_loopback_http and parsed.hostname in ('127.0.0.1', '::1')):
        raise ValueError('plaintext_requires_literal_loopback')
    # Force validation of malformed ports before any request.
    parsed.port
    return endpoint.rstrip('/')


def request_fixture(run_id, model):
    if type(run_id) is not str or re.fullmatch('[a-f0-9]{32}', run_id) is None:
        raise ValueError('run_id_requires_32_lowercase_hex_characters')
    _text(model, 256)
    # Run-specific synthetic corpus; never reads patient files or user text.
    rows = [f'Synthetic record {i}: code {hashlib.sha256((run_id+str(i)).encode()).hexdigest()[:12]}.'
            for i in range(96)]
    prompt = '\n'.join(['Synthetic memory probe. Read these records:', *rows,
                        'Repeat only the code of synthetic record 47:'])
    return {'model': model, 'prompt': prompt, 'max_tokens': 16, 'temperature': 0,
            'seed': 19, 'logprobs': 1}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _fetch(opener, url, token, timeout, body=None):
    headers = {'Accept': 'application/json' if body is not None else 'text/plain'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    raw = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        raw = json.dumps(body, allow_nan=False).encode()
    with opener.open(Request(url, data=raw, headers=headers), timeout=timeout) as response:
        payload = response.read(1048577)
        if len(payload) > 1048576:
            raise ValueError('runtime_response_too_large')
        return payload.decode('utf-8')


def _parse_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError('nonfinite_json')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def parse_metrics(raw):
    selected = {}
    for line in raw.splitlines():
        match = re.fullmatch(r'([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{[^\n]*\})?\s+([-+0-9.eE]+)(?:\s+\d+)?', line)
        if match is None or match[1] not in METRICS:
            continue
        value = float(match[2])
        if not math.isfinite(value) or value < 0:
            continue
        selected.setdefault(match[1], []).append(value)
    # Multiple starts mean an aggregated endpoint; never pick an arbitrary PID.
    return {key: (values[0] if key == 'process_start_time_seconds' and len(values) == 1
                  else None if key == 'process_start_time_seconds' else sum(values))
            for key, values in selected.items()}


def response_observation(response):
    if type(response) is not dict or type(response.get('choices')) is not list or len(response['choices']) != 1:
        raise ValueError('invalid_completion_choices')
    choice = response['choices'][0]
    if type(choice) is not dict or type(choice.get('text')) is not str:
        raise ValueError('invalid_completion_text')
    usage = response.get('usage')
    if type(usage) is not dict:
        raise ValueError('missing_runtime_usage')
    counts = {}
    for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        value = usage.get(name)
        if type(value) is not int or value < 0:
            raise ValueError('invalid_runtime_usage')
        counts[name] = value
    if counts['total_tokens'] != counts['prompt_tokens'] + counts['completion_tokens']:
        raise ValueError('inconsistent_runtime_usage')
    details = usage.get('prompt_tokens_details')
    cached = details.get('cached_tokens') if type(details) is dict else None
    if cached is not None and (type(cached) is not int or not 0 <= cached <= counts['prompt_tokens']):
        raise ValueError('invalid_cached_token_count')
    logs = choice.get('logprobs')
    # This fingerprint is selected-token logprob data, NEVER all model logits.
    log_digest = None
    if type(logs) is dict and type(logs.get('tokens')) is list and type(logs.get('token_logprobs')) is list:
        tokens, probs = logs['tokens'], logs['token_logprobs']
        if (tokens and len(tokens) == len(probs) and all(type(t) is str for t in tokens)
                and all(type(p) in (float, int) and math.isfinite(p) for p in probs)):
            log_digest = digest({'tokens': tokens, 'token_logprobs': probs})
    return {'usage': counts, 'cached_tokens_reported': cached,
            'output_sha256': digest(choice['text']), 'selected_token_logprobs_sha256': log_digest}


def capture(*, endpoint, model, model_revision, run_id, phase,
            allow_loopback_http=False, token='', timeout=30):
    origin = endpoint_origin(endpoint, allow_loopback_http)
    _text(model_revision, 256)
    if model_revision.lower() in ('unknown', 'latest', 'main', 'master', 'none'):
        raise ValueError('immutable_model_revision_required')
    if phase not in PHASES or type(timeout) not in (int, float) or not 0 < timeout <= 60:
        raise ValueError('invalid_capture_options')
    if type(token) is not str or any(ord(c) < 32 for c in token) or len(token) > 16384:
        raise ValueError('invalid_bearer_credential')
    request = request_fixture(run_id, model)
    opener = build_opener(_NoRedirect())
    def metrics():
        try:
            return {'status': 'observed', 'values': parse_metrics(_fetch(opener, origin+'/metrics', token, timeout))}
        except Exception:
            return {'status': 'unavailable', 'values': {}}
    before = metrics()
    start = time.perf_counter()
    response = _parse_json(_fetch(opener, origin+'/v1/completions', token, timeout, request))
    elapsed = time.perf_counter() - start
    if type(response) is not dict or response.get('model') != model:
        raise ValueError('runtime_model_mismatch')
    observation = response_observation(response)
    after = metrics()
    return {'schema': SCHEMA, 'status': 'http_observation_captured', 'phase': phase,
            'endpoint_sha256': digest(origin), 'model': model, 'model_revision_operator_supplied': model_revision,
            'run_id': run_id, 'request_sha256': digest(request),
            'captured_unix_seconds': time.time(), 'wall_latency_seconds': elapsed,
            'metrics_before': before, 'metrics_after': after, **observation,
            'synthetic_only': True, 'sample_size': 1, 'ttft_seconds': None,
            'gpu_hardware_verified': False, 'licence_verified': False,
            'tensor_identity_verified': False, 'galahad_attribution_verified': False,
            'kv_release_gate': 'blocked'}


def compare(before, after):
    for item in (before, after):
        if type(item) is not dict or item.get('schema') != SCHEMA or item.get('status') != 'http_observation_captured':
            raise ValueError('capture_artifact_required')
        for key in ('request_sha256', 'endpoint_sha256', 'output_sha256'):
            if type(item.get(key)) is not str or re.fullmatch('[a-f0-9]{64}', item[key]) is None:
                raise ValueError('invalid_capture_digest')
        if item.get('phase') not in PHASES:
            raise ValueError('invalid_capture_phase')
        stamp = item.get('captured_unix_seconds')
        if type(stamp) not in (float, int) or not math.isfinite(stamp) or stamp <= 0:
            raise ValueError('invalid_capture_time')
    if after['captured_unix_seconds'] <= before['captured_unix_seconds']:
        raise ValueError('captures_not_chronological')
    for key in ('run_id', 'request_sha256', 'model', 'model_revision_operator_supplied', 'endpoint_sha256'):
        if before.get(key) != after.get(key) or not before.get(key):
            raise ValueError('incomparable_captures')
    def stable_start(item):
        starts = [item.get('metrics_'+side, {}).get('values', {}).get('process_start_time_seconds')
                  for side in ('before', 'after')]
        return starts[0] if starts[0] is not None and starts[0] == starts[1] else None
    left, right = stable_start(before), stable_start(after)
    changed = (right > left if type(left) in (int, float) and type(right) in (int, float)
               and math.isfinite(left) and math.isfinite(right) else None)
    cached = after.get('cached_tokens_reported')
    logs = before.get('selected_token_logprobs_sha256'), after.get('selected_token_logprobs_sha256')
    return {'status': 'observations_compared', 'sample_size_per_phase': 1,
            'before_phase': before.get('phase'), 'after_phase': after.get('phase'),
            'output_matches': before.get('output_sha256') == after.get('output_sha256'),
            'selected_token_logprobs_match': logs[0] == logs[1] if all(logs) else None,
            'reported_server_process_start_increased': changed,
            'after_reports_cached_tokens': type(cached) is int and cached > 0,
            'full_engine_restart_verified': False, 'tensor_identity_verified': False,
            'galahad_attribution_verified': False, 'kv_release_gate': 'blocked',
            'limitations': ['server_process_metric_is_not_gpu_worker_restart_attestation',
                'cache_tokens_may_be_ordinary_prefix_cache', 'selected_logprobs_are_not_full_logits',
                'model_revision_is_operator_supplied', 'single_samples_do_not_establish_speedup']}


def _write_new(path, report):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    cap = commands.add_parser('capture', help='one synthetic request to an existing operator-approved endpoint')
    for name in ('endpoint', 'model', 'model-revision', 'run-id', 'phase', 'output'):
        cap.add_argument('--'+name, required=True, **({'choices': PHASES} if name == 'phase' else {}))
    cap.add_argument('--allow-loopback-http', action='store_true')
    cap.add_argument('--bearer-env', help='environment variable containing endpoint credential; never persisted')
    cap.add_argument('--timeout', type=float, default=30)
    cmp = commands.add_parser('compare')
    cmp.add_argument('--before', required=True)
    cmp.add_argument('--after', required=True)
    cmp.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if Path(args.output).exists():
            raise ValueError('output_already_exists')
        if args.command == 'capture':
            token = os.environ[args.bearer_env] if args.bearer_env else ''
            report = capture(endpoint=args.endpoint, model=args.model, model_revision=args.model_revision,
                run_id=args.run_id, phase=args.phase, allow_loopback_http=args.allow_loopback_http,
                token=token, timeout=args.timeout)
        else:
            def read(path):
                with Path(path).open('r', encoding='utf-8') as handle:
                    raw = handle.read(1048577)
                if len(raw) > 1048576:
                    raise ValueError('artifact_size_limit')
                return _parse_json(raw)
            report = compare(read(args.before), read(args.after))
        _write_new(args.output, report)
        print(json.dumps({'status': report['status'], 'kv_release_gate': report['kv_release_gate']}))
        return 0
    except Exception:
        print(json.dumps({'status': 'probe_failed', 'error': 'invalid_input_or_runtime_unavailable',
                          'kv_release_gate': 'blocked'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
