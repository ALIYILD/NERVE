"""Narrow macOS managed-service containment adapter, not a workload sandbox.

No NERVE imports. Native mutating dispatch is deliberately uncommissioned: only
an injected administrator/test transport can exercise the operation protocol.
A missing launchd job is not evidence that escaped descendants, other schedulers,
credentials or remote work are stopped. Consequently ``verified`` ALWAYS remains
false and restart is denied. Existing Guardian recovery authority is not replaced.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import time

_LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
_SHA = re.compile(r'[a-f0-9]{64}\Z')
_GAPS = ['whole-workload identity and descendant containment unverified',
         'alternate scheduling and reboot restart denial unverified',
         'credential revocation and remote effects uncontrolled',
         'independent administration and authenticated recovery not commissioned']


@dataclass(frozen=True)
class ManagedLaunchdService:
    label: str
    plist_path: str
    plist_sha256: str
    workload_user: str
    workload_uid: int
    clinical: bool = False
    shared: bool = False


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate persisted field')
        value[key] = item
    return value


def _regular_bytes(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('bounded singly linked regular file required')
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError('oversized protected input')
    return value


def _native_policy_read(path):
    # Metadata checks are conservative prerequisites, NOT ACL/identity attestation.
    for item in (path, *path.parents):
        info = item.lstat()
        expected = stat.S_ISREG if item == path else stat.S_ISDIR
        if not expected(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise PermissionError('root-owned protected policy ancestors required')
    return _regular_bytes(path, 65536)


class LaunchdController:
    """Existing controller interface with deliberately incomplete coverage.

    ``runner`` and ``policy_reader`` are trusted test/admin dependencies, never
    supplied through workload JSON. Injected observations are labelled simulated.
    Live provisioning, ACL verification and independent UID coverage must be added
    and accepted before native mutation or authenticated restart can be enabled.
    """
    def __init__(self, inventory, state_dir, *, enabled=False, runner=None, policy_reader=None):
        if type(enabled) is not bool:
            raise ValueError('explicit boolean enable required')
        if policy_reader is not None and runner is None:
            raise ValueError('policy injection requires isolated transport')
        self.inventory = {tenant: tuple(services) for tenant, services in inventory.items()}
        seen_labels, seen_uids = set(), {}
        if not self.inventory:
            raise ValueError('nonempty scoped inventory required')
        for tenant, services in self.inventory.items():
            if type(tenant) is not str or not _LABEL.fullmatch(tenant) or not services:
                raise ValueError('literal tenant and nonempty coverage required')
            for service in services:
                if (not isinstance(service, ManagedLaunchdService) or type(service.label) is not str
                        or not _LABEL.fullmatch(service.label) or service.label.startswith('com.apple.')
                        or any(word in service.label.lower() for word in ('guardian', 'watchtower'))
                        or service.label in seen_labels or service.clinical is not False or service.shared is not False
                        or service.plist_path != '/Library/LaunchDaemons/' + service.label + '.plist'
                        or type(service.plist_sha256) is not str or not _SHA.fullmatch(service.plist_sha256)
                        or type(service.workload_user) is not str
                        or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', service.workload_user)
                        or service.workload_user in ('root', 'daemon', 'nobody')
                        or type(service.workload_uid) is not int or service.workload_uid <= 0
                        or service.workload_uid == os.getuid()):
                    raise ValueError('isolated nonclinical literal launchd inventory required')
                if service.workload_uid in seen_uids and seen_uids[service.workload_uid] != tenant:
                    raise ValueError('cross-tenant workload identity prohibited')
                seen_labels.add(service.label)
                seen_uids[service.workload_uid] = tenant
        if enabled and runner is None:
            raise PermissionError('native mutating dispatch is not commissioned')
        self.enabled = enabled
        self.simulated = runner is not None
        self.runner = runner or subprocess.run
        self.policy_reader = policy_reader or _native_policy_read
        self.state_dir = Path(state_dir).absolute()
        if any(path.is_symlink() for path in (self.state_dir, *self.state_dir.parents)):
            raise ValueError('linked state paths prohibited')
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.state_dir.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError('private controller-owned state required')

    def _path(self, tenant):
        if tenant not in self.inventory:
            raise ValueError('unknown tenant')
        return self.state_dir / (sha256(tenant.encode()).hexdigest() + '.json')

    @contextmanager
    def _lock(self):
        fd = os.open(self.state_dir / 'launchd-enforcement.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('regular private lock required')
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _sync_directory(self):
        fd = os.open(self.state_dir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _save(self, tenant, incident):
        target = self._path(tenant)
        temporary = target.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(_encode({'incident_id': incident, 'latched': True}))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, target)
        self._sync_directory()

    def latch(self, tenant):
        try:
            raw = _regular_bytes(self._path(tenant), 4096)
        except FileNotFoundError:
            return None
        value = json.loads(raw, object_pairs_hook=_object)
        if (type(value) is not dict or set(value) != {'incident_id', 'latched'}
                or type(value['incident_id']) is not str or not _LABEL.fullmatch(value['incident_id'])
                or value['latched'] is not True):
            raise ValueError('invalid containment latch')
        return value

    def _policy(self, service):
        raw = self.policy_reader(Path(service.plist_path))
        if type(raw) is not bytes or len(raw) > 65536 or sha256(raw).hexdigest() != service.plist_sha256:
            raise ValueError('reviewed launchd policy digest mismatch')
        value = plistlib.loads(raw)
        if (type(value) is not dict or not {'Label', 'UserName', 'ProgramArguments'} <= set(value)
                or set(value) - {'Label', 'UserName', 'ProgramArguments', 'RunAtLoad', 'KeepAlive'}
                or value['Label'] != service.label or value['UserName'] != service.workload_user
                or type(value['ProgramArguments']) is not list or not 1 <= len(value['ProgramArguments']) <= 32
                or any(type(arg) is not str or not arg or len(arg) > 4096 or '\x00' in arg for arg in value['ProgramArguments'])
                or not value['ProgramArguments'][0].startswith('/')
                or any(type(value[key]) is not bool for key in ('RunAtLoad', 'KeepAlive') if key in value)):
            raise ValueError('unsupported or mismatched reviewed service policy')

    def _command(self, verb, target):
        if verb not in ('disable', 'bootout', 'print', 'print-disabled'):
            raise ValueError('unsupported launchd operation')
        try:
            result = self.runner(['/bin/launchctl', verb, target], capture_output=True, text=True,
                                 timeout=20, check=False, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
            if (type(result.returncode) is not int or type(result.stdout) is not str
                    or type(result.stderr) is not str or len(result.stdout) > 65536 or len(result.stderr) > 4096):
                return None, '', ''
            return result.returncode, result.stdout, result.stderr
        except (OSError, subprocess.TimeoutExpired):
            return None, '', ''

    def _journal(self, tenant, incident, label, verb, phase, **fields):
        payload = _encode(dict(incident_id=incident, service=label, action=verb, phase=phase,
                              observed_at=time.time(), **fields)).encode() + b'\n'
        path = self._path(tenant).with_suffix('.actions.jsonl')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'ab') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('regular private journal required')
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        self._sync_directory()

    def measure(self, service):
        result = dict(service=service.label, status='UNKNOWN', disabled=False, absent=False)
        try:
            self._policy(service)
        except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
            return result
        code, output, error = self._command('print-disabled', 'system')
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        entries = {}
        if code != 0 or error or len(lines) < 2 or lines[0] != 'disabled services = {' or lines[-1] != '}':
            return result
        for line in lines[1:-1]:
            match = re.fullmatch(r'"([A-Za-z0-9][A-Za-z0-9_.-]{0,127})" => (enabled|disabled)', line)
            if not match or match[1] in entries:
                return result
            entries[match[1]] = match[2]
        if service.label not in entries:
            return result
        code, output, error = self._command('print', 'system/' + service.label)
        expected = 'Bad request.\nCould not find service "' + service.label + '" in domain for system'
        if code != 113 or output.strip() or error.strip() != expected:
            return result
        # A second policy check catches changes during the two observations.
        try:
            self._policy(service)
        except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
            return result
        result.update(status='OBSERVED', disabled=entries[service.label] == 'disabled', absent=True)
        return result

    def verify(self, tenant):
        self._path(tenant)
        coverage = [self.measure(service) for service in self.inventory[tenant]]
        managed = bool(coverage) and all(row['status'] == 'OBSERVED' and row['disabled'] and row['absent'] for row in coverage)
        return dict(actions=[], verified=False, managed_service_verified=managed,
                    whole_workload_verified=False, simulated=self.simulated, coverage=coverage, gaps=list(_GAPS))

    def contain(self, tenant, incident_id):
        if not self.enabled:
            raise PermissionError('launchd enforcement disabled')
        if type(incident_id) is not str or not _LABEL.fullmatch(incident_id):
            raise ValueError('literal incident identifier required')
        self._path(tenant)
        with self._lock():
            current = self.latch(tenant)
            if current is not None and current['incident_id'] != incident_id:
                raise ValueError('already latched to a different incident')
            for service in self.inventory[tenant]:
                self._policy(service)
            if current is None:
                self._save(tenant, incident_id)
            actions = []
            for service in self.inventory[tenant]:
                for verb in ('disable', 'bootout'):
                    self._journal(tenant, incident_id, service.label, verb, 'intent')
                    code, _, _ = self._command(verb, 'system/' + service.label)
                    ok = code == 0
                    self._journal(tenant, incident_id, service.label, verb, 'result', ok=ok)
                    actions.append(dict(service=service.label, action=verb, ok=ok))
            result = self.verify(tenant)
            result['actions'] = actions
            return result

    def restart(self, tenant, incident_id):
        self._path(tenant)
        # Never enable/bootstrap from a mere service-state observation or a
        # matching incident string. Core authentication remains necessary but
        # cannot manufacture missing independent workload coverage.
        raise PermissionError('whole-workload containment and independent recovery are not commissioned')
