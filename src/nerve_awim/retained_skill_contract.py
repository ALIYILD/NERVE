"""Opt-in, pure Loop 41 contract consumer; no live registry or activation wiring."""
from copy import deepcopy
from hashlib import sha256
import json
import re


def signing_payload(record):
    return json.dumps({k: v for k, v in record.items() if k != 'signed_by'},
                      sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def select_retained_skill(record, *, incumbent, config_bytes, artifact_bytes,
                          manifest_hash, model_digest, verify_gate, verify_signature):
    """Callbacks are trusted host code, never values loaded from a skill record.

    verify_gate(record, verified_artifacts) must verify canonical study receipts
    and all candidate/config/model/manifest bindings, returning literal True only
    for a promotion proposal. verify_signature(key, payload, signature) must also
    check current signer authorization for the record's skill and host scope.
    No exceptions or partially verified records authorize a selection.
    """
    fallback = deepcopy(incumbent)
    try:
        item = deepcopy(record)
        def require(condition):
            if not condition:
                raise ValueError('invalid retention contract')

        def digest(value):
            return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None

        require(set(item) == {'skill_id', 'version', 'config_hash', 'evidence_bundle',
                              'supersedes', 'signed_by'})
        require(all(isinstance(item[k], str) and 0 < len(item[k]) <= 256
                    for k in ('skill_id', 'version')))
        require(item['skill_id'] == incumbent['skill_id'])
        require(item['version'] != incumbent['version'])
        require(item['supersedes'] == incumbent)
        require(digest(item['config_hash']) and type(config_bytes) is bytes)
        require(sha256(config_bytes).hexdigest() == item['config_hash'])
        bundle = item['evidence_bundle']
        names = ('dev_study', 'holdout_study', 'task_bank_manifest')
        require(set(bundle) == set(names) | {'model_digest'})
        require(digest(model_digest) and bundle['model_digest'] == model_digest)
        require(digest(manifest_hash) and bundle['task_bank_manifest']['sha256'] == manifest_hash)
        verified = {}
        for name in names:
            ref = bundle[name]
            require(set(ref) == {'uri', 'sha256'})
            require(isinstance(ref['uri'], str) and 0 < len(ref['uri']) <= 2048)
            require(digest(ref['sha256']))
            data = artifact_bytes[ref['uri']]
            require(type(data) is bytes and sha256(data).hexdigest() == ref['sha256'])
            verified[name] = data
        require(verify_gate(deepcopy(item), verified) is True)
        signer = item['signed_by']
        require(set(signer) == {'key_id', 'signature'})
        require(all(isinstance(signer[k], str) and signer[k] for k in signer))
        require(verify_signature(signer['key_id'], signing_payload(item), signer['signature']) is True)
        return {'selected': {k: item[k] for k in ('skill_id', 'version', 'config_hash')},
                'retained_skill_selected': True, 'production_authorized': False}
    except Exception:
        return {'selected': fallback, 'retained_skill_selected': False,
                'production_authorized': False, 'reason': 'retention_verification_failed'}
