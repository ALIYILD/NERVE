import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from nerve_guardian.health import check, main


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'health.json'
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, **changes):
        report = {'timestamp': time.time(), 'status': 'OBSERVED_SCOPE_ONLY', 'tenants': ['private-tenant']}
        report.update(changes)
        self.path.write_text(json.dumps(report))
        self.path.chmod(0o600)

    def runner(self, argv, **kwargs):
        self.assertEqual('/usr/bin/systemctl', argv[0])
        self.assertEqual('show', argv[3])
        self.assertEqual(5, kwargs['timeout'])
        self.assertNotIn('shell', kwargs)
        return subprocess.CompletedProcess(argv, 0,
            'LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=42\nControlGroup=/system.slice/guardian.service\n', '')

    def test_healthy_is_scoped_no_sensitive_output(self):
        result = check('guardian.service', self.path, runner=self.runner)
        self.assertEqual('OBSERVED_SCOPE_ONLY', result['status'])
        self.assertNotIn('private-tenant', json.dumps(result))
        self.assertNotIn(str(self.path), json.dumps(result))

    def test_stale_future_missing_invalid_and_unknown_reports(self):
        for changes in ({'timestamp': time.time() - 120}, {'timestamp': time.time() + 120},
                        {'timestamp': float('nan')}, {'timestamp': True}, {'status': 'UNKNOWN'}, {'tenants': []}):
            self.write(**changes)
            self.assertEqual('UNKNOWN', check('guardian.service', self.path, runner=self.runner)['status'])
        self.path.write_text('not-json secret')
        self.assertEqual('UNKNOWN', check('guardian.service', self.path, runner=self.runner)['status'])
        self.path.unlink()
        self.assertEqual('UNKNOWN', check('guardian.service', self.path, runner=self.runner)['status'])

    def test_inactive_missing_pid_or_cgroup_and_timeout(self):
        for before, after in [('ActiveState=active', 'ActiveState=inactive'), ('MainPID=42', 'MainPID=0'),
                              ('ControlGroup=/system.slice/guardian.service', 'ControlGroup='),
                              ('LoadState=loaded', 'LoadState=not-found')]:
            def runner(argv, **kwargs):
                result = self.runner(argv, **kwargs)
                result.stdout = result.stdout.replace(before, after)
                return result
            self.assertEqual('UNKNOWN', check('guardian.service', self.path, runner=runner)['status'])
        def unavailable(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 5)
        self.assertEqual('UNKNOWN', check('guardian.service', self.path, runner=unavailable)['status'])

    def test_no_arbitrary_unit_or_writable_symlink_report(self):
        for unit in ('--all', 'guardian.service;id', '*.service', '../guardian.service'):
            self.assertEqual('UNKNOWN', check(unit, self.path, runner=lambda *a, **kw: self.fail('executed'))['status'])
        self.path.chmod(0o666)
        self.assertEqual('UNKNOWN', check('guardian.service', self.path, runner=self.runner)['status'])
        self.path.chmod(0o600)
        link = self.path.with_suffix('.link')
        link.symlink_to(self.path)
        self.assertEqual('UNKNOWN', check('guardian.service', link, runner=self.runner)['status'])
        os.utime(self.path, (0, 0))
        self.assertEqual('UNKNOWN', check('guardian.service', self.path, runner=self.runner)['status'])

    def test_cli_exit_codes(self):
        with patch('sys.argv', ['health', '--unit', 'guardian.service', '--health-file', str(self.path)]), \
             patch('nerve_guardian.health.check', return_value={'status': 'UNKNOWN'}), patch('builtins.print'):
            self.assertEqual(2, main())
        with patch('sys.argv', ['health', '--unit', 'guardian.service', '--health-file', str(self.path)]), \
             patch('nerve_guardian.health.check', return_value={'status': 'OBSERVED_SCOPE_ONLY'}), patch('builtins.print'):
            self.assertEqual(0, main())


if __name__ == '__main__':
    unittest.main()
