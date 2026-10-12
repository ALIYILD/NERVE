"""Verify local artifacts against an independently approved host manifest.

Integrity checks do not discover hidden capabilities or attest hosted model
weights. The manifest must come from owner review, never from model output.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat


def verify_local_artifacts(root, manifest, *, max_bytes=32 * 1024 * 1024):
    if (type(manifest) is not dict or set(manifest) != {'model', 'revision', 'files'} or
            any(type(manifest[k]) is not str or not 1 <= len(manifest[k]) <= 128
                for k in ('model', 'revision')) or
            type(manifest['files']) is not dict or not 1 <= len(manifest['files']) <= 64):
        raise ValueError('bounded owner-reviewed model manifest required')
    if type(max_bytes) is not int or not 0 < max_bytes <= 512 * 1024 * 1024:
        raise ValueError('bounded verification budget required')
    root = Path(root).resolve(strict=True)
    total, verified = 0, {}
    for name, expected in sorted(manifest['files'].items()):
        if (type(name) is not str or len(name) > 512 or '\\' in name or
                PurePosixPath(name).is_absolute() or
                any(p in ('', '.', '..') for p in name.split('/')) or
                type(expected) is not str or not re.fullmatch('[a-f0-9]{64}', expected)):
            raise ValueError('relative artifact path and SHA-256 required')
        # Walk using directory descriptors so symlink substitution cannot escape
        # the host-selected root between validation and opening the artifact.
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            parts = name.split('/')
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, 'rb') as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_size + total > max_bytes:
                    raise ValueError('regular artifacts within verification budget required')
                digest = hashlib.sha256()
                while True:
                    block = stream.read(min(65536, max_bytes - total + 1))
                    if not block:
                        break
                    total += len(block)
                    if total > max_bytes:
                        raise ValueError('artifact verification budget exceeded')
                    digest.update(block)
                after = os.fstat(stream.fileno())
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise PermissionError('artifact changed during verification')
                if digest.hexdigest() != expected:
                    raise PermissionError('model artifact digest mismatch')
                verified[name] = expected
        finally:
            os.close(directory)
    encoded = json.dumps(manifest, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return {'status': 'local_artifacts_verified', 'model_digest': hashlib.sha256(encoded.encode()).hexdigest(),
            'files': verified, 'bytes_verified': total, 'hidden_capability_absence_proven': False,
            'hosted_model_attested': False}
