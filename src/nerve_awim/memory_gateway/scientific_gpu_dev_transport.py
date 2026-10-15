"""Versioned 7B development transport; historical 1.5B policies stay immutable."""
import json
import re
import time
from urllib.request import Request, build_opener, ProxyHandler

from . import scientific_candidate_v3 as candidate
from . import scientific_structured_tasks as structured
from .inference import _NoRedirect

compact = candidate.compact
grammar = candidate.grammar

MODEL = 'qwen2.5-coder:7b'
ORIGIN = 'http://127.0.0.1:11434'
SEED = 20261015
BASELINE_VERSION = 'six-field-schema-baseline-v1'


def prepare(query, evidence, *, arm='candidate'):
    fixed = candidate.prepare(query, evidence, arm=arm)
    if arm == 'baseline':
        fixed.update(baseline_contract=BASELINE_VERSION,
            system=structured.INSTRUCTION,
            user=json.dumps({'query': query, 'evidence': evidence}, sort_keys=True),
            schema=structured.SCHEMA)
    return fixed


def _checked(prepared):
    if prepared.get('baseline_contract') is not None:
        fixed = prepare(prepared['query'], prepared['evidence'], arm='baseline')
        if fixed != prepared:
            raise ValueError('baseline_binding_changed')
        return fixed
    return candidate._checked(prepared)


def decode(raw, prepared):
    fixed = _checked(prepared)
    if fixed.get('baseline_contract') == BASELINE_VERSION:
        value = structured.parse(raw)
        if value['status'] == 'answer' and re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,12})?', value['value']) is None:
            raise ValueError('numeric_measurement_required')
        return value
    return candidate.decode(raw, fixed)


def schema_valid(raw, prepared):
    fixed = _checked(prepared)
    if fixed.get('baseline_contract') == BASELINE_VERSION:
        try:
            structured.parse_shape(raw)
            return True
        except ValueError:
            return False
    return candidate.schema_valid(raw, fixed)


def _request(path, payload=None, timeout=30):
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(ORIGIN + path,
        data=None if payload is None else json.dumps(payload, allow_nan=False).encode(),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError('bounded_response_required')
    return json.loads(raw, object_pairs_hook=candidate.compact._object)


def metadata():
    models = _request('/api/tags', timeout=5)['models']
    matches = [m for m in models if m['name'] == MODEL]
    if len(matches) != 1 or re.fullmatch('[0-9a-f]{64}', matches[0]['digest']) is None:
        raise ValueError('immutable_model_identity_required')
    return {'model': MODEL, 'digest': matches[0]['digest']}


def runtime_version():
    value = _request('/api/version', timeout=5)['version']
    if not isinstance(value, str) or re.fullmatch('[A-Za-z0-9._+-]{1,80}', value) is None:
        raise ValueError('runtime_identity_required')
    return value


def preload():
    start = time.perf_counter()
    value = _request('/api/generate', {'model': MODEL, 'prompt': '', 'stream': False,
                                       'keep_alive': '2m'}, timeout=45)
    if value.get('model') != MODEL or value.get('done') is not True or value.get('response') != '':
        raise ValueError('empty_preload_required')
    return {'wall_seconds': time.perf_counter() - start}


def run(prepared, *, authorize, timeout_seconds=30):
    if not callable(authorize) or timeout_seconds != 30:
        raise ValueError('bounded_authorized_transport_required')
    fixed = _checked(prepared)
    binding = json.dumps(fixed, sort_keys=True)
    authorize()
    if json.dumps(_checked(prepared), sort_keys=True) != binding:
        raise ValueError('request_changed')
    payload = {'model': MODEL, 'temperature': 0, 'seed': SEED, 'stream': False,
        'max_tokens': 128, 'messages': [{'role': 'system', 'content': fixed['system']},
                                      {'role': 'user', 'content': fixed['user']}]}
    if fixed['schema'] is not None:
        payload['response_format'] = {'type': 'json_schema', 'json_schema': {
            'name': 'scientific_measurement', 'strict': True, 'schema': fixed['schema']}}
    value = _request('/v1/chat/completions', payload)
    if value.get('model') != MODEL or len(value.get('choices', [])) != 1:
        raise ValueError('response_identity_changed')
    choice = value['choices'][0]
    message = choice['message']
    raw = message.get('content')
    if (choice['finish_reason'] not in ('stop', 'length') or message.get('role') != 'assistant'
        or message.get('tool_calls') or message.get('function_call')
        or not isinstance(raw, str) or not 1 <= len(raw) <= 16384):
        raise ValueError('bounded_completion_required')
    usage = {k: value['usage'][k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
    if (any(type(v) is not int or v < 0 for v in usage.values()) or usage['completion_tokens'] > 128
        or usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']):
        raise ValueError('measured_usage_required')
    try:
        authorize()
        if json.dumps(_checked(prepared), sort_keys=True) != binding:
            raise ValueError('request_changed')
    except Exception as error:
        error.unscored_raw_response = dict(raw_output=raw, usage=usage,
            finish_reason=choice['finish_reason'], reason='post_response_authorization_failed')
        raise
    return dict(raw_output=raw, usage=usage, finish_reason=choice['finish_reason'],
        model=MODEL, origin=ORIGIN, model_calls=1, model_sampling_seed=SEED,
        input_sha256=fixed['input_sha256'], review_required=True, synthetic_only=True)
