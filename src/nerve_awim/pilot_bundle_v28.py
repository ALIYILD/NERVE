"""Deterministic pilot archives with strict checksum/path verification.

Checksums detect corruption, not a malicious publisher. Trust the repository
revision and delivery channel separately. Never install directly over a host.
"""
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile

MANIFEST = 'PILOT-MANIFEST.json'
MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 512
EXTRAS = (
    'LICENSE', 'README.md',
    'deploy/nerve-repository-pilot.service',
    'deploy/requirements-pilot-linux-x86_64.lock', 'deploy/requirements-pilot.txt',
    'docs/repository-host-v25.md', 'docs/bound-repository-host-v26.md',
    'docs/host-operations-v27.md', 'docs/pilot-installation-v28.md',
    'scripts/serve_repository_host_v25.py', 'scripts/bind_repository_trial_v26.py',
    'scripts/manage_repository_store_v27.py', 'scripts/verify_pilot_install_v28.py',
)


def _path(name):
    if (type(name) is not str or not name or '\\' in name or '\x00' in name
            or PurePosixPath(name).is_absolute() or ':' in name
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError('unsafe bundle path')
    return name


def build_bundle(root, destination, *, revision, dirty):
    root, destination = Path(root).resolve(), Path(destination)
    if not re.fullmatch('[0-9a-f]{40}', revision) or type(dirty) is not bool:
        raise ValueError('explicit source revision and dirty status required')
    names = sorted(set(EXTRAS) | {p.relative_to(root).as_posix()
                   for p in (root/'src'/'nerve_awim').rglob('*.py')})
    payload, total = {}, 0
    if not (root/'src'/'nerve_awim'/'__init__.py').is_file() or len(names) >= MAX_FILES:
        raise ValueError('missing package or too many files')
    for name in names:
        _path(name)
        path = root/name
        if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
            raise ValueError('bundle source cannot contain symlinks')
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError('missing or unsafe source file')
        total += path.stat().st_size
        if total > MAX_BYTES:
            raise ValueError('bundle exceeds size budget')
        payload[name] = path.read_bytes()
    manifest = {'format': 1, 'source_revision': revision, 'worktree_dirty': dirty,
                'target': 'cpython312-linux-x86_64-glibc234',
                'files': {n: {'sha256': sha256(b).hexdigest(), 'size': len(b)} for n,b in payload.items()}}
    payload[MANIFEST] = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
    if sum(len(content) for content in payload.values()) > MAX_BYTES:
        raise ValueError('bundle including manifest exceeds size budget')
    # Exclusive creation prevents overwriting an existing artifact.
    with destination.open('xb') as output:
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in sorted(payload.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
    return manifest


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate manifest key')
        result[key] = value
    return result


def read_bundle(path):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [item.filename for item in entries]
        if (not 1 < len(entries) <= MAX_FILES or len(set(names)) != len(names)
                or MANIFEST not in names or sum(i.file_size for i in entries) > MAX_BYTES):
            raise ValueError('invalid bundle size or member set')
        for item in entries:
            _path(item.filename)
            if (item.is_dir() or stat.S_IFMT(item.external_attr >> 16) not in (0, stat.S_IFREG)
                    or item.flag_bits & 1):
                raise ValueError('only unencrypted regular files allowed')
        manifest = json.loads(archive.read(MANIFEST), object_pairs_hook=_unique)
        if (type(manifest) is not dict or set(manifest) != {'format','source_revision','worktree_dirty','target','files'}
                or type(manifest['format']) is not int or manifest['format'] != 1
                or type(manifest['source_revision']) is not str
                or not re.fullmatch('[0-9a-f]{40}', manifest['source_revision'])
                or type(manifest['worktree_dirty']) is not bool
                or manifest['target'] != 'cpython312-linux-x86_64-glibc234'
                or type(manifest['files']) is not dict
                or set(manifest['files']) != set(names)-{MANIFEST}):
            raise ValueError('invalid bundle manifest')
        contents = {}
        for name, expected in manifest['files'].items():
            if (type(expected) is not dict or set(expected) != {'sha256','size'}
                    or type(expected['size']) is not int or expected['size'] < 0):
                raise ValueError('invalid file record')
            content = archive.read(name)
            if len(content) != expected['size'] or sha256(content).hexdigest() != expected['sha256']:
                raise ValueError('bundle checksum mismatch')
            contents[name] = content
        # Avoid prefix conflicts, e.g. both "src" and "src/module.py".
        for name in names:
            if any(str(p) in names for p in PurePosixPath(name).parents if str(p) != '.'):
                raise ValueError('file/directory conflict')
    return manifest, contents


def unpack_bundle(archive, destination):
    manifest, contents = read_bundle(archive)
    destination = Path(destination)
    destination.mkdir()  # Existing paths (even empty directories/symlinks) fail.
    try:
        for name, content in contents.items():
            path = destination/name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(content)
            path.chmod(0o644)
        (destination/MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n')
    except BaseException:
        shutil.rmtree(destination)
        raise
    return manifest
