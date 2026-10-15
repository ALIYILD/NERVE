"""Review manifest, not a substitute for a human signature or OS isolation."""
from hashlib import sha256
import json
from pathlib import Path


def verify_manifest(repository):
    root = Path(repository).resolve()
    manifest = json.loads((root/'configs/external-methods-protected.json').read_text())
    if manifest.get('live_holdout_enabled') is not False or manifest.get('promotion_enabled') is not False:
        raise PermissionError('staged_manifest_required')
    expected_paths = {str(p.relative_to(root)) for p in (root/'src/nerve_awim/external_methods').glob('*.py')}
    expected_paths |= {'scripts/run_external_methods.py', 'tests/test_external_methods.py'}
    if set(manifest['source_sha256']) != expected_paths:
        raise ValueError('complete_protected_source_manifest_required')
    for name, expected in manifest['source_sha256'].items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('protected_source_changed')
    return manifest
