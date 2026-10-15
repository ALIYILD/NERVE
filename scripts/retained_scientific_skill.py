#!/usr/bin/env python3
"""Host-trusted, opt-in Loop 41 adapter; no network or production activation.

The independent trust anchor is in code, not supplied by the candidate registry.
Consumption replays the original private journals with the frozen canonical gate.
Missing local evidence fails closed. The public record alone is not sufficient.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

TRUST_SHA256 = '6d902228024e9909b901a203cea5917c1e7655131c6c444ae7fe9d94de3ed8d4'
TRUST_PATH = Path(__file__).resolve().parents[1] / 'trust/scientific-v3-7b-operator.json'


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _require(value):
    if not value:
        raise ValueError('retention trust verification failed')


def _trust():
    raw = TRUST_PATH.read_bytes()
    _require(_sha(raw) == TRUST_SHA256)
    value = json.loads(raw)
    _require(value['registry_only'] is True and value['production_authorized'] is False)
    return value


def load_selection_inputs(registry_directory):
    """Return the existing pure consumer's arguments using independent host trust.

    Invalid trust/registry metadata raises before selection; callers must retain
    their incumbent on loader errors. Callback errors also fail closed in the
    pure consumer. Registry state represents retention, never deployed runtime.
    """
    trust = _trust()
    root = Path(registry_directory)
    record = json.loads((root / 'skill-v1.json').read_bytes())
    config = (root / 'candidate-config.json').read_bytes()
    baseline = (root / 'baseline-config.json').read_bytes()
    _require(_sha(baseline) == trust['incumbent']['config_hash'])
    state = json.loads((root / 'registry.json').read_bytes())
    expected_current = {k: trust[k] for k in ('skill_id', 'version', 'config_hash')}
    _require(state['current'] == expected_current)
    _require(state['runtime_activation'] is False and state['production_authorized'] is False)
    _require(state['records']['v1'] == {'status': 'retained', 'record': 'skill-v1.json'})
    _require(state['records'][trust['incumbent']['version']] == {
        'status': 'superseded', 'descriptor': trust['incumbent'],
        'superseded_by': 'v1', 'bootstrap': True})
    artifacts = {ref['uri']: (root / ref['uri']).read_bytes()
                 for name, ref in trust['evidence_bundle'].items() if name != 'model_digest'}

    def verify_signature(key_id, payload, signature):
        try:
            current = _trust()
            _require(current == trust and key_id == trust['key_id'])
            _require(_sha(payload) == trust['authorized_payload_sha256'])
            decoded = json.loads(payload)
            _require(all(decoded[k] == trust[k] for k in ('skill_id', 'version', 'config_hash')))
            _require(decoded['supersedes'] == trust['incumbent'])
            _require(decoded['evidence_bundle'] == trust['evidence_bundle'])
            Ed25519PublicKey.from_public_bytes(base64.b64decode(trust['public_key_base64'], validate=True)).verify(
                base64.b64decode(signature, validate=True), payload)
            return True
        except Exception:
            return False

    def verify_gate(item, verified_artifacts):
        try:
            _require(_trust() == trust)
            _require(all(item[k] == trust[k] for k in ('skill_id', 'version', 'config_hash')))
            _require(item['supersedes'] == trust['incumbent'])
            _require(item['evidence_bundle'] == trust['evidence_bundle'])
            _require(_sha(config) == trust['config_hash'])
            studies = {}
            for name in ('dev_study', 'holdout_study', 'task_bank_manifest'):
                ref = trust['evidence_bundle'][name]
                raw = verified_artifacts[name]
                _require(_sha(raw) == ref['sha256'])
                studies[name] = json.loads(raw)
            dry, holdout = studies['dev_study'], studies['holdout_study']
            regs = []
            for study in (dry, holdout):
                _require(study['candidate_config_sha256'] == trust['config_hash'])
                _require(study['incumbent_config_sha256'] == trust['incumbent']['config_hash'])
                regraw = base64.b64decode(study['registration_bytes_base64'], validate=True)
                aggraw = base64.b64decode(study['aggregate_bytes_base64'], validate=True)
                reg, agg = json.loads(regraw), json.loads(aggraw)
                _require(reg == study['registration'] and agg == study['aggregate'])
                _require(_sha(regraw) == agg['registration_sha256'])
                _require(reg['identity']['model_digest'] == trust['model_digest'])
                _require(agg['complete'] is True and agg['error_type'] is None)
                _require(agg['attempts'] == agg['logical_model_calls'] == 160 and agg['timeouts'] == 0)
                regs.append(reg)
            dr, hr = regs
            _require(dr['kind'] == 'dry' and hr['kind'] == 'slice2')
            _require(dry['aggregate']['dry_admission_passed'] is True)
            _require(hr['dry_registration_sha256'] == dry['aggregate']['registration_sha256'])
            _require(hr['dry_aggregate_sha256'] == _sha(base64.b64decode(dry['aggregate_bytes_base64'])))
            _require(hr['sources'] == dr['sources'] and hr['identity'] == dr['identity'])
            _require(hr['manifest']['parent_manifest_sha256'] == trust['manifest_hash'])
            _require(hr['input_sha256'] == hr['manifest']['content_sha256'])
            for cfgbytes, arm in ((config, 'candidate'), (baseline, 'baseline')):
                cfg = json.loads(cfgbytes)
                _require(cfg['arm'] == arm and cfg['sources'] == dr['sources'])
                _require(cfg['identity'] == dr['identity'] and cfg['seed'] == dr['seed'])
                _require(cfg['reference_registration_sha256'] == dr['reference_registration_sha256'])
            frozen = Path(trust['frozen_checkout'])
            sources = [frozen / 'scripts/run_scientific_runpod_gate.py', *sorted((frozen / 'src').rglob('*.py'))]
            _require({str(p.relative_to(frozen)): _sha(p.read_bytes()) for p in sources} == dr['sources'])
            # CPU-only canonical replay validates private input, all requests,
            # responses, scores and aggregate; never the run/register entrypoint.
            for kind, study in (('dry', dry), ('slice2', holdout)):
                private = Path(trust['private_receipt_root']) / kind
                _require(_sha((private / 'registration.json').read_bytes()) == study['aggregate']['registration_sha256'])
                command = [sys.executable, '-I', '-c',
                    'import runpy,sys;sys.path.insert(0,sys.argv[1]);p=sys.argv[2];sys.argv=sys.argv[2:];runpy.run_path(p,run_name="__main__")',
                    str(frozen / 'src'), str(frozen / 'scripts/run_scientific_runpod_gate.py'),
                    'verify', '--directory', str(private)]
                result = subprocess.run(command, cwd=frozen, check=True, capture_output=True, text=True, timeout=120)
                _require(json.loads(result.stdout) == study['aggregate'])
            _require(holdout['aggregate']['verdict'] == 'promote_proposal')
            return True
        except Exception:
            return False

    return {'record': record, 'incumbent': trust['incumbent'], 'config_bytes': config,
            'artifact_bytes': artifacts, 'manifest_hash': trust['manifest_hash'],
            'model_digest': trust['model_digest'], 'verify_gate': verify_gate,
            'verify_signature': verify_signature}
