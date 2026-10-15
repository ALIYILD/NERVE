"""Observed local research inventory; no inference, scanning or runtime selection.

Only the operator's configured Ollama adapter is inspected. Hardware observations
are descriptive resource metadata, not device attestation or allocation promises.
No hostname, user identity, serial number, credential or network address is read.
"""
from hashlib import sha256
import json
import os
import platform
import time

import agentos_cue_local as local
from nerve_awim.cue_engine import ModelProfile
from nerve_awim.cue_evaluation import ModelParity


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode()).hexdigest()


def _positive(value):
    return value if type(value) is int and 0 < value <= 2**63 - 1 else None


def _sysconf(name, *, allow_zero=False):
    try:
        value = os.sysconf(name)
        return 0 if allow_zero and type(value) is int and value == 0 else _positive(value)
    except (AttributeError, OSError, ValueError, OverflowError):
        return None


def _label(value):
    return value if type(value) is str and 0 < len(value) <= 128 and value.isascii() and all(ord(c) >= 32 for c in value) else None


def observe_hardware():
    """Low-cost process-local OS queries only; deliberately do not probe GPUs."""
    try:
        cpus = _positive(os.cpu_count())
    except (OSError, ValueError):
        cpus = None
    page_bytes = _sysconf('SC_PAGE_SIZE')
    pages = _sysconf('SC_PHYS_PAGES')
    free_pages = _sysconf('SC_AVPHYS_PAGES', allow_zero=True)
    total = _positive(page_bytes * pages) if page_bytes and pages else None
    free = page_bytes * free_pages if page_bytes and free_pages is not None else None
    if free is not None and free > 2**63 - 1:
        free = None
    if total is not None and free is not None and free > total:
        free = None
    identity = {'os': _label(platform.system()), 'os_release': _label(platform.release()),
                'architecture': _label(platform.machine()), 'logical_cpus': cpus,
                'physical_memory_bytes': total}
    return {'identity': identity, 'hardware_observation_digest': _digest(identity),
            'free_physical_memory_bytes': free,
            'allocatable_memory_bytes': None, 'accelerator': None,
            'gpu_memory_bytes': None, 'measured_throughput_tokens_per_second': None,
            'identity_attested': False,
            'limitations': ['Logical CPU count is not a throughput measurement.',
                'Physical/free memory is an OS snapshot, not allocatable model capacity.',
                'Unsupported memory queries remain unknown; no GPU capability is inferred.',
                'Resource characteristics do not uniquely identify or attest a host.']}


def inspect_runtime(host):
    """Return redacted configured-local inventory; metadata HTTP only, zero inference.

    Missing/malformed configuration does not contact a provider. Disabled but
    valid configuration may be explicitly inspected, without enabling research.
    Errors expose a fixed category, never exception text or provider response.
    """
    config = local._config(host)
    result = {'schema_version': 1, 'kind': 'nerve-local-runtime-inventory',
              'observed_at': time.time(), 'runtimes': [], 'model_calls': 0,
              'selection_performed': False, 'activation_authorized': False}
    if config is None:
        return dict(result, status='unconfigured_or_invalid')
    try:
        binding = local.inspect_binding(host)
        profile = ModelProfile(**binding['profile'])
        model = ModelParity(**binding['model'])
        if (model.profile_key != profile.key or any(getattr(model, field) != getattr(profile, field)
                for field in ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision'))):
            raise ValueError('runtime profile mismatch')
        hardware = observe_hardware()
        # Allowlist identity fields rather than exporting future adapter payloads.
        runtime = {'runtime_id': 'configured-local-ollama',
            'adapter_id': binding['adapter_id'], 'adapter_revision': binding['adapter_revision'],
            'research_enabled': config['enabled'], 'profile_key': profile.key,
            'model_config_digest': _digest(binding['model']),
            'model': profile.model, 'provider': profile.provider,
            'model_revision': profile.revision, 'tokenizer_revision': profile.tokenizer_revision,
            'template_revision': profile.template_revision,
            'hardware': hardware,
            'daily_call_limit': binding['daily_call_limit'], 'max_job_calls': binding['max_job_calls'],
            'quality_evidence': None, 'measured_latency_ms': None,
            'measured_cost_usd': None, 'eligible_for_automatic_selection': False,
            'blocking_reasons': ['matched_quality_latency_cost_evidence_required',
                                 'resource_compatibility_not_measured'],
            'attestation': 'observational local research; no worker deployment attestation'}
        runtime['runtime_identity_digest'] = _digest({key: runtime[key] for key in
            ('adapter_id', 'adapter_revision', 'profile_key', 'model_config_digest')} |
            {'hardware_observation_digest': hardware['hardware_observation_digest']})
        return dict(result, status='observed', runtimes=[runtime])
    except (ValueError, TypeError, KeyError, RuntimeError, OSError):
        return dict(result, status='inspection_unavailable', error_category='local_runtime_inspection_failed')
