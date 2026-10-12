import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from nerve_guardian.infrastructure import ManagedUnit, SystemdController
from nerve_guardian.probes import InfrastructureProbe


class IsolatedSupervisor:
    """Test-only real child supervisor. Not evidence for live systemd operation."""
    def __init__(self, root):
        self.root = Path(root)
        self.mask = self.root / 'masked'
        self.child = None
        self.calls = []

    def start(self):
        if self.mask.exists():
            return False
        self.child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        return True

    def close(self):
        if self.child is not None and self.child.poll() is None:
            self.child.kill()
            self.child.wait(timeout=5)

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        assert kwargs['timeout'] == 20 and 'shell' not in kwargs
        verb = argv[3]
        if verb == 'mask':
            self.mask.touch()
        elif verb == 'stop':
            self.close()
        elif verb == 'unmask':
            self.mask.unlink(missing_ok=True)
        elif verb == 'start':
            return subprocess.CompletedProcess(argv, 0 if self.start() else 1, '', '')
        elif verb == 'show':
            running = self.child is not None and self.child.poll() is None
            output = '\n'.join(['LoadState=loaded', 'ActiveState=' + ('active' if running else 'inactive'),
                'SubState=' + ('running' if running else 'dead'),
                'UnitFileState=' + ('masked' if self.mask.exists() else 'enabled'),
                'MainPID=' + (str(self.child.pid) if running else '0'),
                'ControlGroup=', 'KillMode=control-group'])
            return subprocess.CompletedProcess(argv, 0, output, '')
        return subprocess.CompletedProcess(argv, 0, '', '')


class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.supervisor = IsolatedSupervisor(self.root)
        self.inventory = {'tenant': [ManagedUnit('nerve-test.service')]}
        self.controller = SystemdController(self.inventory, self.root / 'state', enabled=True,
                                           runner=self.supervisor)

    def tearDown(self):
        self.supervisor.close()
        self.temp.cleanup()

    def test_real_disposable_child_and_persistent_recreation_refusal(self):
        self.assertTrue(self.supervisor.start())
        child = self.supervisor.child
        result = self.controller.contain('tenant', 'incident-1')
        self.assertTrue(result['verified'])
        self.assertTrue((self.controller.blocks / 'nerve-test.service').exists())
        self.assertIsNotNone(child.poll())
        self.assertFalse(self.supervisor.start())
        rebuilt = SystemdController(self.inventory, self.root / 'state', enabled=True, runner=self.supervisor)
        self.assertTrue(rebuilt.latch('tenant')['latched'])
        with self.assertRaises(PermissionError):
            rebuilt.restart('tenant', 'wrong-incident')
        self.assertTrue(rebuilt.restart('tenant', 'incident-1')['verified'])
        self.assertFalse(rebuilt.latch('tenant')['latched'])
        self.assertFalse((rebuilt.blocks / 'nerve-test.service').exists())

    def test_disabled_unknown_and_excluded_inventory(self):
        disabled = SystemdController(self.inventory, self.root / 'disabled', runner=self.supervisor)
        with self.assertRaises(PermissionError):
            disabled.contain('tenant', 'i')
        with self.assertRaises(ValueError):
            self.controller.contain('other-tenant', 'i')
        for unit in (ManagedUnit('shared.service', shared=True), ManagedUnit('clinical.service', clinical=True),
                     ManagedUnit('nerve-guardian.service'), ManagedUnit('x;touch /tmp/x.service')):
            with self.assertRaises(ValueError):
                SystemdController({'tenant': [unit]}, self.root / 'bad')

    def test_mask_failure_not_confirmed(self):
        def runner(argv, **kwargs):
            if argv[3] == 'mask':
                return subprocess.CompletedProcess(argv, 1, '', 'private-error')
            return self.supervisor(argv, **kwargs)
        self.controller.runner = runner
        result = self.controller.contain('tenant', 'i')
        self.assertFalse(result['verified'])
        self.assertTrue(self.controller.latch('tenant')['latched'])
        self.assertNotIn('private-error', str(result))

    def test_timeout_is_unknown(self):
        def runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 20)
        self.controller.runner = runner
        result = self.controller.contain('tenant', 'i')
        self.assertFalse(result['verified'])
        self.assertEqual('UNKNOWN', result['coverage'][0]['status'])

    def test_cgroup_descendants_prevent_confirmation(self):
        group = self.root / 'cgroups' / 'system.slice' / 'nerve-test.service'
        group.mkdir(parents=True)
        (group / 'cgroup.events').write_text('populated 1\nfrozen 0\n')
        self.controller.cgroup_root = (self.root / 'cgroups').resolve()
        def runner(argv, **kwargs):
            result = self.supervisor(argv, **kwargs)
            if argv[3] == 'show':
                result.stdout = result.stdout.replace('ControlGroup=', 'ControlGroup=/system.slice/nerve-test.service')
            return result
        self.controller.runner = runner
        self.assertFalse(self.controller.contain('tenant', 'i')['verified'])
        (group / 'cgroup.events').write_text('populated 0\n')
        self.assertTrue(self.controller.verify('tenant')['verified'])

    def test_failed_restart_recontains(self):
        self.controller.contain('tenant', 'i')
        def runner(argv, **kwargs):
            if argv[3] == 'start':
                return subprocess.CompletedProcess(argv, 1, '', '')
            return self.supervisor(argv, **kwargs)
        self.controller.runner = runner
        self.assertFalse(self.controller.restart('tenant', 'i')['verified'])
        self.assertTrue(self.controller.verify('tenant')['verified'])
        self.assertTrue(self.controller.latch('tenant')['latched'])

    def test_tampering_missing_stale_and_unauthorized_restart(self):
        protected = self.root / 'policy.json'
        protected.write_text('approved')
        digest = hashlib.sha256(protected.read_bytes()).hexdigest()
        heartbeat = self.root / 'heartbeat'
        heartbeat.touch()
        os.utime(heartbeat, (50, 50))
        probe = InfrastructureProbe(self.controller, protected_files={'tenant': {protected: digest}},
                                    heartbeats={'tenant': heartbeat}, clock=lambda: 1000)
        samples = probe.sample('tenant')
        self.assertIn('UNKNOWN', [x['status'] for x in samples])
        protected.write_text('modified')
        self.assertIn('protected_file_changed', [x['kind'] for x in probe.sample('tenant')])
        self.controller.contain('tenant', 'i')
        self.supervisor.mask.unlink()
        self.assertTrue(self.supervisor.start())
        self.assertIn('unauthorized_restart', [x['kind'] for x in probe.sample('tenant')])
        protected.unlink()
        self.assertIn('visibility_loss', [x['kind'] for x in probe.sample('tenant')])


if __name__ == '__main__':
    unittest.main()
