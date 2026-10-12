"""External, explicitly enabled systemd containment. No NERVE imports or shell."""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from contextlib import contextmanager


@dataclass(frozen=True)
class ManagedUnit:
    name: str
    clinical: bool = False
    shared: bool = False


class SystemdController:
    """Caller must be the independently authenticated Guardian control plane.

    State directory and inventory must be administrator-owned, inaccessible to
    agents. There is deliberately no network endpoint or agent-facing credential.
    Restart authorisation belongs to the owner's authenticated incident service.
    """
    def __init__(self, inventory, state_dir, *, enabled=False, runner=None,
                 cgroup_root=Path('/sys/fs/cgroup')):
        self.inventory = {t: tuple(units) for t, units in inventory.items()}
        seen = set()
        for tenant, units in self.inventory.items():
            if not isinstance(tenant, str) or not tenant or not units:
                raise ValueError('nonempty tenant and coverage required')
            for unit in units:
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*\.service', unit.name):
                    raise ValueError('literal service name required')
                if unit.clinical or unit.shared or unit.name in seen:
                    raise ValueError('clinical/shared/cross-tenant units prohibited')
                if any(x in unit.name.lower() for x in ('guardian', 'watchtower')):
                    raise ValueError('observer containment prohibited')
                seen.add(unit.name)
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.state_dir.is_symlink() or self.state_dir.stat().st_mode & 0o077:
            raise ValueError('private administrator state directory required')
        self.enabled = enabled
        self.runner = runner or subprocess.run
        self.cgroup_root = Path(cgroup_root).resolve()
        self.blocks = self.state_dir / 'blocks'
        self.blocks.mkdir(mode=0o700, exist_ok=True)
        if self.blocks.is_symlink() or self.blocks.stat().st_mode & 0o077:
            raise ValueError('private block directory required')
        if enabled and runner is None and (os.geteuid() != 0 or self.state_dir.stat().st_uid != 0):
            raise PermissionError('live controller requires administrator-owned state and root identity')

    def _block(self, unit, blocked):
        path = self.blocks / unit
        if blocked:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        else:
            path.unlink(missing_ok=True)
        fd = os.open(self.blocks, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _path(self, tenant):
        if tenant not in self.inventory:
            raise ValueError('unknown tenant')
        return self.state_dir / (hashlib.sha256(tenant.encode()).hexdigest() + '.json')

    @contextmanager
    def _lock(self):
        with open(self.state_dir / 'controller.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def _save(self, tenant, record):
        path = self._path(tenant)
        temporary = path.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(record, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        fd = os.open(self.state_dir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def latch(self, tenant):
        path = self._path(tenant)
        return json.loads(path.read_text()) if path.exists() else None

    def _command(self, verb, name):
        argv = ['/usr/bin/systemctl', '--no-pager', '--no-ask-password', verb, name]
        if verb == 'show':
            argv += ['--property=LoadState,ActiveState,SubState,UnitFileState,MainPID,ControlGroup,KillMode']
        try:
            result = self.runner(argv, capture_output=True, text=True, timeout=20,
                                 check=False, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
            # Never expose stderr: provider/system errors can contain private paths.
            return result.returncode == 0, result.stdout[:16384]
        except (OSError, subprocess.TimeoutExpired):
            return False, ''

    def measure(self, name):
        ok, output = self._command('show', name)
        values = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        if (not ok or not {'LoadState', 'ActiveState', 'MainPID', 'ControlGroup', 'UnitFileState'} <= values.keys()
                or values.get('LoadState') not in ('loaded', 'masked')):
            return {'unit': name, 'status': 'UNKNOWN', 'stopped': False, 'masked': False}
        group = values['ControlGroup']
        empty = False
        if not group:
            empty = values['MainPID'] == '0' and values['ActiveState'] in ('inactive', 'failed')
        else:
            path = (self.cgroup_root / group.lstrip('/')).resolve()
            if self.cgroup_root not in path.parents:
                return {'unit': name, 'status': 'UNKNOWN', 'stopped': False, 'masked': False}
            try:
                # cgroup.events populated covers descendant cgroups as well.
                events = dict(line.split() for line in (path / 'cgroup.events').read_text().splitlines())
                empty = events.get('populated') == '0'
            except (OSError, ValueError):
                return {'unit': name, 'status': 'UNKNOWN', 'stopped': False, 'masked': False}
        stopped = empty and values['MainPID'] == '0' and values['ActiveState'] in ('inactive', 'failed')
        return {'unit': name, 'status': 'OBSERVED', 'stopped': stopped,
                'masked': values['UnitFileState'] == 'masked', 'active': values['ActiveState'],
                'kill_mode': values.get('KillMode', 'unknown')}

    def verify(self, tenant):
        self._path(tenant)
        coverage = [self.measure(unit.name) for unit in self.inventory[tenant]]
        return {'actions': [], 'verified': bool(coverage) and all(x['stopped'] and x['masked'] for x in coverage),
                'coverage': coverage, 'gaps': ['unmanaged processes, other hosts, containers, external tools, network and IAM are not controlled']}

    def _contain(self, tenant, incident_id):
        current = self.latch(tenant)
        if current and current.get('latched') and current['incident_id'] != incident_id:
            raise ValueError('tenant already latched to another incident')
        for unit in self.inventory[tenant]:
            self._block(unit.name, True)
        self._save(tenant, {'incident_id': incident_id, 'latched': True})
        actions = []
        for unit in self.inventory[tenant]:
            for verb in ('mask', 'stop'):
                ok, _ = self._command(verb, unit.name)
                actions.append({'unit': unit.name, 'action': verb, 'ok': ok})
        result = self.verify(tenant)
        result['actions'] = actions
        return result

    def contain(self, tenant, incident_id):
        if not self.enabled:
            raise PermissionError('live enforcement disabled')
        if not isinstance(incident_id, str) or not 1 <= len(incident_id) <= 128:
            raise ValueError('incident identifier required')
        with self._lock():
            return self._contain(tenant, incident_id)

    def restart(self, tenant, incident_id):
        if not self.enabled:
            raise PermissionError('live enforcement disabled')
        with self._lock():
            state = self.latch(tenant)
            if not state or not state.get('latched') or state['incident_id'] != incident_id:
                raise PermissionError('matching incident latch required')
            actions = []
            for unit in self.inventory[tenant]:
                for verb in ('unmask', 'start'):
                    if verb == 'start':
                        self._block(unit.name, False)
                    ok, _ = self._command(verb, unit.name)
                    actions.append({'unit': unit.name, 'action': verb, 'ok': ok})
                    if not ok:
                        result = self._contain(tenant, incident_id)
                        result.update(verified=False, actions=actions + result['actions'])
                        return result
            coverage = [self.measure(unit.name) for unit in self.inventory[tenant]]
            verified = all(x.get('active') == 'active' and not x['masked'] for x in coverage)
            if not verified:
                result = self._contain(tenant, incident_id)
                result.update(verified=False, actions=actions + result['actions'])
                return result
            self._save(tenant, {'incident_id': incident_id, 'latched': False})
            return {'actions': actions, 'verified': True, 'coverage': coverage,
                    'gaps': ['restart health is process state only; application health must be separately checked']}
