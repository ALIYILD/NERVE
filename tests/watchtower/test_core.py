import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from nerve_guardian.core import Guardian
from nerve_guardian.store import Store,IntegrityError
from nerve_guardian.auth import Principal
from nerve_guardian.demo import FixtureProbe,run_demo


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.pin=self.root/'pin';self.pin.write_text('approved')
        self.store=Store(self.root/'state',self.root/'anchor')
        self.probe=FixtureProbe(self.pin)
        self.controller=Mock()
        self.controller.contain.return_value={'verified':True,'coverage':[],'actions':[]}
        self.controller.verify.return_value={'verified':True,'coverage':[]}
        self.controller.restart.return_value={'verified':True}
        self.engine=Guardian(self.store,self.controller,self.probe,tenants=['demo'],owners={'owner':'demo'},armed=True,synthetic=True)
    def owner(self,jti):
        import time
        now=int(time.time());return Principal('owner','demo',now,jti,now+100)
    def incident(self):
        self.pin.write_text('tampered');return self.engine.tick('demo')['incidents'][0]['id']
    def test_repaired_fresh_mfa_restart_and_replay(self):
        incident=self.incident();self.pin.write_text('approved')
        request=self.engine.request_restart(self.owner('request-token'),incident,'repair-ticket')
        self.assertEqual(self.engine.approve_restart(self.owner('approve-token'),incident,request['id'])['status'],'RESOLVED')
        with self.assertRaises(PermissionError):self.engine.approve_restart(self.owner('approve-token'),incident,request['id'])
        self.assertEqual(self.controller.restart.call_count,1)
    def test_missing_mandatory_signal_denies_restart(self):
        incident=self.incident();self.pin.write_text('approved')
        request=self.engine.request_restart(self.owner('request-token'),incident,'repair-ticket')
        sample=self.probe.sample;self.probe.sample=lambda tenant:sample(tenant)[:-1]
        with self.assertRaises(PermissionError):self.engine.approve_restart(self.owner('approve-token'),incident,request['id'])
        self.controller.restart.assert_not_called()
    def test_failed_restart_is_contained_again(self):
        incident=self.incident();self.pin.write_text('approved')
        request=self.engine.request_restart(self.owner('request-token'),incident,'repair-ticket')
        self.controller.restart.return_value={'verified':False}
        with self.assertRaises(PermissionError):self.engine.approve_restart(self.owner('approve-token'),incident,request['id'])
        self.assertEqual(self.controller.contain.call_count,2)
    def test_critical_evidence_retains_hashes_not_raw_text(self):
        incident=self.incident();record=self.store.read()['incidents'][incident]
        self.assertIn('sha256',record['observations'][0]['evidence'])
        self.assertNotIn('tampered',json.dumps(record))
    def test_audit_failure_raises_independent_alert(self):
        notifier=Mock();self.engine.notifier=notifier
        self.store.path.write_bytes(b'corrupted')
        result=self.engine.tick('demo')
        self.assertEqual(result['risk'],'UNKNOWN');notifier.enqueue.assert_called_once()
        self.assertEqual(notifier.enqueue.call_args[0][0]['event'],'audit_integrity_failure')
    def test_observe_only_deduplicates_critical(self):
        self.engine.armed=False;self.pin.write_text('tampered')
        for _ in range(3):self.engine.tick('demo')
        self.assertEqual(len(self.store.read()['incidents']),1);self.controller.contain.assert_not_called()
    def test_keep_stopped_invalidates_pending_approval(self):
        incident=self.incident();request=self.engine.request_restart(self.owner('request-token'),incident,'repair-ticket')
        self.engine.keep_stopped(self.owner('hold-token'),incident)
        self.pin.write_text('approved')
        with self.assertRaises(PermissionError):self.engine.approve_restart(self.owner('approve-token'),incident,request['id'])
        self.controller.restart.assert_not_called()
    def test_real_disposable_process_demo(self):
        report=run_demo()
        for key in ('normal_workload_alive','real_disposable_process_stopped','recreation_blocked','replay_denied'):self.assertTrue(report[key])
        self.assertEqual(report['restart_status'],'RESOLVED')
        self.assertEqual(report['notification_channels_exercised'],['email','telegram'])
        self.assertEqual(report['live_provider_calls'],0)
    def test_denied_restart_alert_is_bounded_and_redacted(self):
        self.engine.record_denial()
        self.engine.record_denial()
        records=self.store.audit('demo')
        self.assertEqual(len(records),1)
        alerts=list(self.store.read()['notifications'].values())
        self.assertEqual(len(alerts),1)
        self.assertEqual(alerts[0]['event'],'unauthorized_restart_attempt')
        self.assertNotIn('subject',alerts[0])
