"""Injected launchd protocol only; never mutate native services or identities."""
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest

from nerve_guardian.launchd import LaunchdController, ManagedLaunchdService


class Supervisor:
    def __init__(self, label):
        self.label = label
        self.calls = []
        self.disabled = False
        self.present = True
        self.timeout = False
        self.bad_disabled = False
        self.unknown_absence = False
        self.disable_failure = False
    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        assert argv[0] == '/bin/launchctl' and kwargs['timeout'] == 20 and 'shell' not in kwargs
        verb = argv[1]
        if self.timeout: raise subprocess.TimeoutExpired(argv, 20)
        code, out, err = 0, '', ''
        if verb == 'disable':
            if self.disable_failure: code = 1
            else: self.disabled = True
        elif verb == 'bootout': self.present = False
        elif verb == 'print-disabled':
            out = 'disabled services = {\n"'+self.label+'" => '+('disabled' if self.disabled else 'enabled')+'\n}\n'
            if self.bad_disabled: out = out.replace('=>', '=')
        elif verb == 'print':
            if not self.present:
                code = 113
                err = 'Bad request.\nCould not find service "'+self.label+'" in domain for system\n'
                if self.unknown_absence: err = 'Permission denied: private path'
            else: out = 'system/'+self.label+' = { state = running }'
        return subprocess.CompletedProcess(argv, code, out, err)


class LaunchdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.raw = plistlib.dumps(dict(Label='com.nerve.disposable', UserName='_nerve_test',
            ProgramArguments=['/usr/bin/true'], RunAtLoad=True, KeepAlive=False))
        self.unit = ManagedLaunchdService('com.nerve.disposable',
            '/Library/LaunchDaemons/com.nerve.disposable.plist',sha256(self.raw).hexdigest(),
            '_nerve_test',os.getuid()+10000)
        self.supervisor = Supervisor(self.unit.label)
        self.controller = self.make()
    def make(self, **kwargs):
        return LaunchdController({'tenant':[self.unit]},self.root/'state',enabled=True,
            runner=self.supervisor,policy_reader=lambda path:self.raw,**kwargs)
    def test_containment_is_service_only_and_durable_never_whole_workload_success(self):
        result = self.controller.contain('tenant','incident-1')
        self.assertTrue(result['managed_service_verified'])
        self.assertFalse(result['verified']); self.assertFalse(result['whole_workload_verified'])
        self.assertTrue(result['simulated'])
        self.assertEqual(self.supervisor.calls[:2],[['/bin/launchctl','disable','system/'+self.unit.label],
            ['/bin/launchctl','bootout','system/'+self.unit.label]])
        rebuilt = self.make()
        self.assertEqual(rebuilt.latch('tenant'),{'incident_id':'incident-1','latched':True})
        journal = [json.loads(line) for line in rebuilt._path('tenant').with_suffix('.actions.jsonl').read_text().splitlines()]
        self.assertEqual([r['phase'] for r in journal],['intent','result','intent','result'])
        self.assertTrue(rebuilt.contain('tenant','incident-1')['managed_service_verified'])
        with self.assertRaises(ValueError): rebuilt.contain('tenant','other')
    def test_default_disabled_and_native_enable_uncommissioned(self):
        controller = LaunchdController({'tenant':[self.unit]},self.root/'disabled',runner=self.supervisor)
        with self.assertRaises(PermissionError): controller.contain('tenant','incident')
        with self.assertRaises(PermissionError): LaunchdController({'tenant':[self.unit]},self.root/'native',enabled=True)
        self.assertEqual(self.supervisor.calls,[])
    def test_restart_denied_even_matching_latch_without_any_enable_or_bootstrap(self):
        self.controller.contain('tenant','incident')
        before = list(self.supervisor.calls)
        with self.assertRaises(PermissionError): self.controller.restart('tenant','incident')
        self.assertEqual(self.supervisor.calls,before)
        self.assertTrue(self.controller.latch('tenant')['latched'])
    def test_inventory_rejects_shared_clinical_observer_uid_and_path_escape(self):
        for unit in (replace(self.unit,clinical=True),replace(self.unit,shared=True),
            replace(self.unit,label='com.nerve.guardian'),replace(self.unit,label='bad;command'),
            replace(self.unit,plist_path='/tmp/other.plist'),replace(self.unit,workload_uid=os.getuid()),
            replace(self.unit,workload_user='root'),replace(self.unit,plist_sha256='wrong')):
            with self.subTest(unit=unit),self.assertRaises(ValueError):
                LaunchdController({'tenant':[unit]},self.root/'bad',runner=self.supervisor)
        with self.assertRaises(ValueError): self.controller.contain('unknown','i')
        self.assertEqual(self.supervisor.calls,[])
    def test_failed_disable_or_unknown_absence_never_confirmed(self):
        self.supervisor.disable_failure = True
        result = self.controller.contain('tenant','i')
        self.assertFalse(result['managed_service_verified'])
        self.assertTrue(self.controller.latch('tenant')['latched'])
        self.supervisor.disable_failure = False; self.supervisor.unknown_absence = True
        result = self.controller.contain('tenant','i')
        self.assertFalse(result['managed_service_verified'])
        self.assertNotIn('private path',str(result))
    def test_timeout_or_malformed_disabled_listing_unknown(self):
        for field in ('timeout','bad_disabled'):
            setattr(self.supervisor,field,True)
            result = self.controller.contain('tenant','i')
            self.assertFalse(result['managed_service_verified'])
            self.assertEqual(result['coverage'][0]['status'],'UNKNOWN')
            setattr(self.supervisor,field,False)
    def test_duplicate_disabled_entry_and_running_service_are_not_absence(self):
        self.supervisor.disabled = True
        self.assertFalse(self.controller.verify('tenant')['managed_service_verified'])
        original = self.supervisor
        def duplicate(argv, **kwargs):
            result = original(argv, **kwargs)
            if argv[1] == 'print-disabled':
                line = '"'+self.unit.label+'" => disabled\n'
                result.stdout = 'disabled services = {\n'+line+line+'}\n'
            return result
        self.controller.runner = duplicate
        self.supervisor.present = False
        self.assertFalse(self.controller.verify('tenant')['managed_service_verified'])

    def test_policy_digest_and_username_drift_prevent_commands(self):
        self.raw = self.raw.replace(b'_nerve_test',b'_nerve_evil')
        with self.assertRaises(ValueError): self.controller.contain('tenant','i')
        self.assertEqual(self.supervisor.calls,[])
        self.assertFalse(self.controller.verify('tenant')['managed_service_verified'])
    def test_policy_race_after_dispatch_fails_observation_but_preserves_latch(self):
        original = self.supervisor
        def changed(argv,**kwargs):
            result = original(argv,**kwargs)
            if argv[1] == 'print': self.raw += b'changed'
            return result
        self.controller.runner = changed
        result = self.controller.contain('tenant','i')
        self.assertFalse(result['managed_service_verified'])
        self.assertTrue(self.controller.latch('tenant')['latched'])
    def test_no_pid_or_descendant_claim_from_service_absence(self):
        result = self.controller.contain('tenant','i')
        self.assertTrue(result['managed_service_verified'])
        self.assertFalse(result['verified'])
        self.assertIn('whole-workload identity and descendant containment unverified',result['gaps'])
    def test_latch_symlink_and_private_state_enforced(self):
        target = self.root/'target'; target.write_text('{}')
        self.controller._path('tenant').symlink_to(target)
        with self.assertRaises(OSError): self.controller.contain('tenant','i')
        self.assertEqual(self.supervisor.calls,[])
        exposed = self.root/'exposed'; exposed.mkdir(mode=0o755)
        with self.assertRaises(ValueError): LaunchdController({'tenant':[self.unit]},exposed,runner=self.supervisor)
    def test_interrupted_journal_keeps_latch_and_no_false_receipt(self):
        original = self.controller._journal
        def interrupt(*args,**kwargs):
            original(*args,**kwargs)
            if args[4] == 'intent': raise RuntimeError('interrupted')
        self.controller._journal = interrupt
        with self.assertRaises(RuntimeError): self.controller.contain('tenant','i')
        self.assertTrue(self.controller.latch('tenant')['latched'])
        self.assertEqual(self.supervisor.calls,[])

if __name__=='__main__': unittest.main()
