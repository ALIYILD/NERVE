"""Opt-in local instruction smoke adapter; no downloads, tools or deployment.

Pinned artifacts and pre/post local-server observations are research provenance,
not per-response cryptographic attestation. The local server and filesystem are
trusted; concurrent model changes invalidate evidence. An entire verified GGUF
identifies the tokenizer artifact, not tokenization correctness or HF equivalence.
Zero cost means external provider fees only; local compute cost is unknown.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener
import uuid

from .cue_engine import ModelProfile, MAX_CUE_BYTES, _FORBIDDEN
from .cue_evaluation import ModelParity
from .cue_experiment import ProviderRequest, ProviderReceipt
from .llm_agent_v14 import _NoRedirect

ENDPOINT = 'http://127.0.0.1:11434'
RENDERER = 'qwen2-chatml-instruction-v1'
# Explicit no-tools/no-history subset of the observed Qwen2 ChatML template.
# The variable cue is a system instruction, never a fixed response-token prefix.
PROMPT_TEMPLATE = ('<|im_start|>system\n'
                   'Complete this public research task. Return only the final answer.\n'
                   'Optional reasoning instruction:\n{cue}<|im_end|>\n'
                   '<|im_start|>user\n{instruction}<|im_end|>\n'
                   '<|im_start|>assistant\n')
_SHA = re.compile(r'[a-f0-9]{64}')
_MODEL = re.compile(r'(?:[a-z0-9][a-z0-9_.-]*/)?[a-z0-9][a-z0-9_.-]*:[a-z0-9][a-z0-9_.-]*')
_MEASUREMENTS = ('prompt_eval_count', 'eval_count', 'total_duration', 'load_duration',
                 'prompt_eval_duration', 'eval_duration')
_ERROR_CATEGORIES = frozenset({
    'inspection_required', 'unsupported_local_endpoint', 'local_request_timeout',
    'local_http_error', 'local_connection_error', 'local_response_too_large',
    'local_response_invalid_json', 'local_response_error_or_invalid_shape',
    'local_response_unavailable_or_invalid', 'local_artifact_verification_failed',
    'invalid_model_inventory', 'expected_model_unavailable', 'server_model_identity_mismatch',
    'server_version_unavailable', 'local_completion_metadata_required',
    'frozen_local_identity_changed', 'frozen_local_configuration_changed',
    'local_call_budget_exhausted', 'invalid_generation_receipt',
    'observed_token_budget_violation', 'local_operation_failed',
    *('missing_generation_measurement_' + field for field in _MEASUREMENTS)})


class OllamaCueError(RuntimeError):
    """Categorical local research failure; never includes outputs or HTTP bodies."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _hash(value):
    return sha256(_canonical(value)).hexdigest()


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _json(raw):
    return json.loads(raw, object_pairs_hook=_strict_object,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def _digest(value):
    if type(value) is not str:
        raise ValueError('SHA256 digest required')
    normalized = value.removeprefix('sha256:')
    if not _SHA.fullmatch(normalized):
        raise ValueError('SHA256 digest required')
    return normalized


def _signature(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


class OllamaCueAdapter:
    """Read-only inspection by default; explicit enabled+permission permits calls.

    ``transport`` follows urllib's (Request, timeout) context-manager contract.
    It is a trusted test/integration seam. The default transport has no proxies
    or redirects and can address only the fixed local server.
    """
    def __init__(self, model, expected_digest, *, model_directory=None,
                 enabled=False, permission_granted=False, max_calls=8,
                 max_output_tokens=128, context_tokens=2048, seed=20261012,
                 temperature=0., timeout=30., max_response_bytes=2_000_000,
                 transport=None):
        if (type(model) is not str or not _MODEL.fullmatch(model) or len(model) > 128
                or model.endswith((':cloud', '-cloud'))):
            raise ValueError('explicit local model:tag required')
        if type(enabled) is not bool or type(permission_granted) is not bool:
            raise ValueError('strict opt-in and host permission required')
        for value, lower, upper in ((max_calls, 1, 256), (max_output_tokens, 1, 2048),
                                    (context_tokens, 512, 32768),
                                    (max_response_bytes, 1024, 4_000_000),
                                    (seed, 0, 2**31 - 1)):
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError('bounded local research settings required')
        if max_output_tokens >= context_tokens:
            raise ValueError('output budget must leave prompt capacity')
        for value, lower, upper in ((temperature, 0, 2), (timeout, .1, 120)):
            if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError('finite bounded sampling/timeout required')
        if transport is not None and not callable(transport):
            raise ValueError('trusted transport callback required')
        self.model, self.expected_digest = model, _digest(expected_digest)
        self.directory = Path(model_directory) if model_directory is not None else Path.home()/'.ollama/models'
        name, tag = model.rsplit(':', 1)
        namespace, name = name.split('/', 1) if '/' in name else ('library', name)
        self.manifest = self.directory/'manifests/registry.ollama.ai'/namespace/name/tag
        self.enabled, self.permission_granted = enabled, permission_granted
        self.max_calls, self.timeout = max_calls, float(timeout)
        self.max_response_bytes = max_response_bytes
        self.options = {'temperature': float(temperature), 'seed': seed,
            'num_predict': max_output_tokens, 'num_ctx': context_tokens,
            'top_k': 40, 'top_p': 1., 'min_p': 0., 'repeat_penalty': 1.,
            'repeat_last_n': 0, 'stop': []}
        self.transport = transport if transport is not None else build_opener(ProxyHandler({}), _NoRedirect()).open
        self._lock = Lock()
        self._snapshot = None
        self._profile = self._model_config = None
        self._calls = self._errors = self._truncations = 0
        self._measured_receipts = 0
        self._input_tokens = self._output_tokens = self._server_duration_ns = 0
        self._last_error = self._last_error_stage = self._stage = None

    def _failure(self, category):
        # Only controlled enum values can enter public diagnostics. Never use a
        # provider exception/body as a diagnostic, even from an injected adapter.
        self._last_error = category if type(category) is str and category in _ERROR_CATEGORIES else 'local_operation_failed'
        self._last_error_stage = self._stage
        return OllamaCueError(self._last_error)

    @property
    def profile(self):
        if self._profile is None:
            raise OllamaCueError('inspection_required')
        return self._profile

    @property
    def model_config(self):
        if self._model_config is None:
            raise OllamaCueError('inspection_required')
        return self._model_config

    def _request(self, path, payload=None):
        if path not in ('/api/version', '/api/tags', '/api/show', '/api/ps', '/api/generate'):
            raise OllamaCueError('unsupported_local_endpoint')
        request = Request(ENDPOINT + path, data=_canonical(payload) if payload is not None else None,
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            method='POST' if payload is not None else 'GET')
        try:
            with self.transport(request, timeout=self.timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                raise self._failure('local_response_too_large')
            try:
                result = _json(raw)
            except (ValueError, TypeError):
                raise self._failure('local_response_invalid_json') from None
            if type(result) is not dict or result.get('error'):
                raise self._failure('local_response_error_or_invalid_shape')
            return result
        except TimeoutError:
            raise self._failure('local_request_timeout') from None
        except HTTPError:
            raise self._failure('local_http_error') from None
        except URLError as error:
            category = 'local_request_timeout' if isinstance(error.reason, TimeoutError) else 'local_connection_error'
            raise self._failure(category) from None
        except OllamaCueError as error:
            raise self._failure(error.args[0] if error.args else None) from None
        except Exception:
            raise self._failure('local_response_unavailable_or_invalid') from None

    def _artifacts(self, *, verify_hashes):
        try:
            base = self.directory.resolve(strict=True)
            manifest = self.manifest.resolve(strict=True)
            if not manifest.is_relative_to(base) or manifest.stat().st_size > 65536:
                raise ValueError('invalid manifest path')
            before = _signature(manifest)
            raw = manifest.read_bytes()
            if sha256(raw).hexdigest() != self.expected_digest or _signature(manifest) != before:
                raise ValueError('manifest mismatch')
            value = _json(raw)
            layers = value['layers']
            if type(layers) is not list or not 1 <= len(layers) <= 32:
                raise ValueError('bounded manifest required')
            descriptors = list(layers)
            if 'config' in value:
                descriptors.append(value['config'])
            signatures = {str(manifest): before}
            model_digests = []
            for layer in descriptors:
                digest = _digest(layer['digest'])
                size = layer['size']
                if type(size) is not int or not 0 < size <= 100_000_000_000:
                    raise ValueError('invalid artifact size')
                blob = (self.directory/'blobs'/('sha256-' + digest)).resolve(strict=True)
                if not blob.is_relative_to(base) or not blob.is_file():
                    raise ValueError('invalid artifact path')
                initial = _signature(blob)
                if initial[2] != size:
                    raise ValueError('artifact size mismatch')
                if verify_hashes:
                    checksum = sha256()
                    with blob.open('rb') as stream:
                        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                            checksum.update(chunk)
                    if checksum.hexdigest() != digest:
                        raise ValueError('artifact digest mismatch')
                if _signature(blob) != initial:
                    raise ValueError('artifact changed during verification')
                signatures[str(blob)] = initial
                if layer.get('mediaType') == 'application/vnd.ollama.image.model':
                    with blob.open('rb') as stream:
                        if stream.read(4) != b'GGUF':
                            raise ValueError('local GGUF required')
                    model_digests.append(digest)
            if len(model_digests) != 1:
                raise ValueError('single local GGUF model required')
            return {'files': signatures, 'model_blob': model_digests[0]}
        except Exception:
            raise OllamaCueError('local_artifact_verification_failed') from None

    def _model_entry(self, result, *, required):
        models = result.get('models')
        if type(models) is not list or len(models) > 4096:
            raise OllamaCueError('invalid_model_inventory')
        matches = [m for m in models if type(m) is dict and
                   (m.get('name') == self.model or m.get('model') == self.model)]
        if not matches and not required:
            return None
        if len(matches) != 1:
            raise OllamaCueError('expected_model_unavailable')
        found = matches[0]
        try:
            if (_digest(found['digest']) != self.expected_digest
                    or found.get('remote_host') or found.get('remote_model')):
                raise ValueError('model identity mismatch')
        except (KeyError, ValueError):
            raise OllamaCueError('server_model_identity_mismatch') from None
        return found

    def _server_snapshot(self):
        version = self._request('/api/version').get('version')
        if type(version) is not str or not 1 <= len(version) <= 128:
            raise OllamaCueError('server_version_unavailable')
        self._model_entry(self._request('/api/tags'), required=True)
        show = self._request('/api/show', {'model': self.model, 'verbose': False})
        if (show.get('remote_host') or show.get('remote_model')
                or type(show.get('details')) is not dict or show['details'].get('format') != 'gguf'
                or show['details'].get('family') != 'qwen2'
                or 'completion' not in show.get('capabilities', [])
                or type(show.get('template')) is not str
                or any(marker not in show['template'] for marker in
                       ('<|im_start|>system', '<|im_start|>user', '<|im_start|>assistant', '<|im_end|>'))
                or type(show.get('model_info')) is not dict
                or show['model_info'].get('tokenizer.ggml.model') != 'gpt2'
                or show['model_info'].get('tokenizer.ggml.pre') != 'qwen2'):
            raise OllamaCueError('local_completion_metadata_required')
        return {'server_version': version, 'show_digest': _hash(show),
                'installed_template_digest': sha256(show['template'].encode()).hexdigest()}

    def _verify_snapshot(self, *, loaded=False):
        artifacts = self._artifacts(verify_hashes=False)
        server = self._server_snapshot()
        if artifacts != self._snapshot['artifacts'] or server != self._snapshot['server']:
            raise OllamaCueError('frozen_local_identity_changed')
        self._model_entry(self._request('/api/ps'), required=loaded)

    def inspect(self):
        """Hash installed artifacts and read metadata only; never generate/pull."""
        with self._lock:
            self._stage = 'inspection'
            artifacts = self._artifacts(verify_hashes=True)
            server = self._server_snapshot()
            self._model_entry(self._request('/api/ps'), required=False)
            observed = {'artifacts': artifacts, 'server': server}
            if self._snapshot is not None and observed != self._snapshot:
                raise OllamaCueError('frozen_local_identity_changed')
            self._snapshot = observed
            template = sha256(PROMPT_TEMPLATE.encode()).hexdigest()
            tokenizer_revision = _hash({'gguf_artifact': artifacts['model_blob'],
                                        'executor_version': server['server_version']})
            self._profile = ModelProfile('ollama-local-research', self.model, self.expected_digest,
                'gguf-embedded-artifact', tokenizer_revision, ('instruction',), template)
            self._model_config = ModelParity(self.profile.provider, self.model, self.profile.revision,
                self.profile.tokenizer, self.profile.tokenizer_revision, template, _hash(self.options),
                self.options['temperature'], self.options['num_predict'],
                _hash({'raw': True, 'context_tokens': self.options['num_ctx'], **server}), self.profile.key)
            self._stage = None
            return {'schema': 'nerve-cce-ollama-profile-v1', 'profile': asdict(self.profile),
                'model_config': asdict(self.model_config), 'model_blob_digest': artifacts['model_blob'],
                'manifest_digest': self.expected_digest, **server,
                'renderer': RENDERER,
                'tokenizer_identity': 'verified GGUF artifact plus executor; token IDs unverified',
                'attestation': 'observational local research only', 'model_calls': self._calls,
                'deployment_authorized': False}

    def __call__(self, request):
        with self._lock:
            if not self.enabled or not self.permission_granted:
                raise PermissionError('explicit local inference opt-in and host permission required')
            if not isinstance(request, ProviderRequest) or request.model != self.model_config:
                raise ValueError('frozen local model configuration required')
            if self.model != self.model_config.model or _hash(self.options) != self.model_config.sampling_digest:
                raise OllamaCueError('frozen_local_configuration_changed')
            if (type(request.task_id) is not str or not 1 <= len(request.task_id) <= 512
                    or type(request.instruction) is not str or not request.instruction.strip()
                    or len(request.instruction.encode()) > 4096
                    or type(request.cue_prefix) is not str or len(request.cue_prefix.encode()) > MAX_CUE_BYTES
                    or type(request.cost_cap_usd) not in (int, float)
                    or not math.isfinite(request.cost_cap_usd) or request.cost_cap_usd < 0):
                raise ValueError('bounded public research request required')
            if any(marker in value for value in (request.instruction, request.cue_prefix)
                   for marker in ('<|', '|>')):
                raise ValueError('raw task and cue cannot contain model control tokens')
            if request.arm == 'baseline':
                if request.cue_prefix or request.cue_mode or request.cue_digest:
                    raise ValueError('baseline must contain no cue')
            elif request.arm == 'candidate':
                if (request.cue_mode != 'instruction' or not request.cue_prefix.strip()
                        or type(request.cue_digest) is not str or not _SHA.fullmatch(request.cue_digest)
                        or _FORBIDDEN.search(request.cue_prefix)
                        or any(ord(c) < 32 and c not in '\n\t' for c in request.cue_prefix)):
                    raise ValueError('bounded instruction candidate required')
            else:
                raise ValueError('explicit experiment arm required')
            prompt = PROMPT_TEMPLATE.format(cue=request.cue_prefix, instruction=request.instruction)
            # For the supported gpt2 byte-level tokenizer family, UTF-8 bytes
            # conservatively bound ordinary input tokens; reserve additional
            # boundary tokens and the entire output cap. This is not an exact
            # tokenizer inspection or proof about arbitrary tokenizer families.
            if len(prompt.encode()) + self.options['num_predict'] + 32 > self.options['num_ctx']:
                raise ValueError('rendered prompt exceeds conservative context budget')
            if self._calls >= self.max_calls:
                raise OllamaCueError('local_call_budget_exhausted')
            self._stage = 'preflight'
            try:
                self._verify_snapshot()
            except OllamaCueError as error:
                raise self._failure(error.args[0] if error.args else None) from None
            self._calls += 1
            try:
                self._stage = 'generation'
                response = self._request('/api/generate', {'model': self.model, 'raw': True,
                    'stream': False, 'keep_alive': '60s', 'options': dict(self.options),
                    'prompt': prompt})
                if (response.get('model') != self.model or response.get('done') is not True
                        or response.get('done_reason') not in ('stop', 'length')
                        or type(response.get('response')) is not str
                        or len(response['response'].encode()) > self.max_response_bytes):
                    raise OllamaCueError('invalid_generation_receipt')
                for field in _MEASUREMENTS:
                    if type(response.get(field)) is not int or response[field] < 0:
                        raise self._failure('missing_generation_measurement_' + field)
                if (response['eval_count'] > self.options['num_predict']
                        or response['prompt_eval_count'] + self.options['num_predict'] > self.options['num_ctx']):
                    raise OllamaCueError('observed_token_budget_violation')
                self._stage = 'postflight'
                self._verify_snapshot(loaded=True)
                truncated = response['done_reason'] == 'length'
                self._truncations += int(truncated)
                self._measured_receipts += 1
                self._input_tokens += response['prompt_eval_count']
                self._output_tokens += response['eval_count']
                self._server_duration_ns += response['total_duration']
                self._stage = None
                return ProviderReceipt(response['response'], None, self.model_config, 0., uuid.uuid4().hex,
                    synthetic=False, error=truncated, cue_digest=request.cue_digest, arm=request.arm,
                    input_tokens=response['prompt_eval_count'], output_tokens=response['eval_count'])
            except OllamaCueError as error:
                self._errors += 1
                raise self._failure(error.args[0] if error.args else None) from None
            except Exception:
                self._errors += 1
                raise self._failure('local_operation_failed') from None

    def summary(self):
        """Aggregate provenance only; no instructions, generated text or secrets."""
        return {'schema': 'nerve-cce-ollama-usage-v1', 'model': self.model,
            'renderer': RENDERER,
            'manifest_digest': self.expected_digest, 'attempted_calls': self._calls,
            'measured_receipts': self._measured_receipts,
            'unmeasured_calls': self._calls - self._measured_receipts,
            'errors': self._errors, 'truncations': self._truncations,
            'last_error': self._last_error, 'last_error_stage': self._last_error_stage,
            'input_tokens': self._input_tokens, 'output_tokens': self._output_tokens,
            'server_duration_ns': self._server_duration_ns, 'external_provider_fee_usd': 0.,
            'local_compute_cost_usd': None, 'confidence_available': False,
            'scope': 'local instruction smoke; not paper reproduction or deployed cue',
            'deployment_authorized': False}
