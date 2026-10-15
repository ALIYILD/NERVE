"""Independent orchestration attacks; fake supervisor, never live shutdown.

These tests prove software decisions and durable ledger behavior only. Real
systemd/IAM/network enforcement requires separately authorized staging evidence.
"""
from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3
import tempfile
import unittest

from nerve_guardian.core import Guardian
from nerve_guardian.store import Store, IntegrityError


class FakeInfrastructure:
    def __init__(self):
        self.contain_calls = []
        self.restart_calls = []
        self.stopped = True

    def contain(self, tenant, incident):
        self.contain_calls.append((tenant, incident))
        return {'verified': self.stopped, 'coverage': [], 'actions': []}

    def verify(self, tenant):
        return {'verified': self.stopped, 'coverage': [], 'gaps': []}

    def restart(self, tenant, incident):
        self.restart_calls.append((tenant, incident))
        return {'verified': True, 'coverage': []}


class FakeProbe:
    def __init__(self, status='CRITICAL', independent=True, stamp=100):
        self.status, self.independent, self.stamp = status, independent, stamp

    def sample(self, tenant):
        return [{'source': 'pinned-infrastructure', 'kind': 'protected_file_changed',
                 'status': self.status, 'independent': self.independent, 'observed_at': self.stamp}]


class IndependentReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'state', Path(self.tmp.name) / 'anchor', clock=lambda: 100)
        self.controller = FakeInfrastructure()
        self.probe = FakeProbe()

    def guardian(self, armed=True):
        return Guardian(self.store, self.controller, self.probe, tenants=['a', 'b'],
                        owners={'alice': 'a', 'bob': 'b'}, clock=lambda: 100,
                        armed=armed, synthetic=True)

    def owner(self, tenant='a', jti='fresh-token-001', mfa=True):
        return SimpleNamespace(subject='alice' if tenant == 'a' else 'bob', tenant=tenant,
                               auth_time=99, expires_at=200, jti=jti, verified_mfa=mfa)

    def test_observe_only_critical_is_never_normal(self):
        snapshot = self.guardian(armed=False).tick('a')
        self.assertEqual(snapshot['risk'], 'CRITICAL')
        self.assertEqual(self.controller.contain_calls, [])

    def test_warning_is_not_normal(self):
        self.probe.status = 'WARNING'
        self.assertEqual(self.guardian(armed=False).tick('a')['risk'], 'WARNING')

    def test_application_claim_cannot_trigger_containment(self):
        self.probe.independent = False
        snapshot = self.guardian().tick('a')
        self.assertEqual(snapshot['risk'], 'UNKNOWN')
        self.assertEqual(self.controller.contain_calls, [])

    def test_stale_critical_cannot_trigger_containment(self):
        self.probe.stamp = 1
        self.assertEqual(self.guardian().tick('a')['risk'], 'UNKNOWN')
        self.assertEqual(self.controller.contain_calls, [])

    def test_visibility_alerts_do_not_overwrite_other_tenants(self):
        self.probe.status = 'UNKNOWN'
        guardian = self.guardian()
        guardian.tick('a')
        guardian.tick('b')
        alerts = [v for v in self.store.read()['notifications'].values() if v['event'] == 'visibility_loss']
        self.assertEqual({a['tenant'] for a in alerts}, {'a', 'b'})

    def test_partial_containment_never_enables_restart_request(self):
        self.controller.stopped = False
        guardian = self.guardian()
        snapshot = guardian.tick('a')
        self.assertEqual(snapshot['emergency_state'], 'PARTIAL_CONTAINMENT')
        incident = snapshot['incidents'][0]['id']
        with self.assertRaises(PermissionError):
            guardian.request_restart(self.owner(), incident, 'repair-ticket')
        self.assertEqual(self.controller.restart_calls, [])

    def test_cross_tenant_restart_and_missing_mfa_denied(self):
        guardian = self.guardian()
        incident = guardian.tick('a')['incidents'][0]['id']
        for principal in (self.owner('b'), self.owner(mfa=False)):
            with self.assertRaises(PermissionError):
                guardian.request_restart(principal, incident, 'repair-ticket')
        self.assertEqual(self.controller.restart_calls, [])

    def test_restart_token_replay_denied_across_reopened_guardian(self):
        guardian = self.guardian()
        incident = guardian.tick('a')['incidents'][0]['id']
        guardian.request_restart(self.owner(), incident, 'repair-ticket')
        with self.assertRaises(PermissionError):
            self.guardian().request_restart(self.owner(), incident, 'repair-ticket')
        self.assertEqual(self.controller.restart_calls, [])

    def test_unknown_probe_denies_approved_restart(self):
        guardian = self.guardian()
        incident = guardian.tick('a')['incidents'][0]['id']
        request = guardian.request_restart(self.owner(), incident, 'repair-ticket')
        self.probe.status = 'UNKNOWN'
        with self.assertRaises(PermissionError):
            guardian.approve_restart(self.owner(jti='fresh-token-002'), incident, request['id'])
        self.assertEqual(self.controller.restart_calls, [])

    def test_state_tampering_denies_recovery_and_normality(self):
        guardian = self.guardian()
        incident = guardian.tick('a')['incidents'][0]['id']
        with sqlite3.connect(self.store.path) as con:
            con.execute("UPDATE state SET document=? WHERE id=1", (json.dumps({'incidents': {}, 'tokens': {}, 'requests': {}, 'notifications': {}}),))
        with self.assertRaises(IntegrityError):
            guardian.request_restart(self.owner(), incident, 'repair-ticket')
        self.assertEqual(guardian.tick('a')['risk'], 'UNKNOWN')
        self.assertEqual(self.controller.restart_calls, [])

    def test_commit_anchor_crash_is_detected_not_silently_healed(self):
        original_anchor = self.store.anchor.read_bytes()
        self.store.change('a', 'test', lambda state: state['tokens'].update({'x': 200}))
        # Simulate the persisted DB commit with the pre-commit external anchor.
        self.store.anchor.write_bytes(original_anchor)
        with self.assertRaises(IntegrityError):
            self.store.read()
        with self.assertRaises(IntegrityError):
            Store(self.store.directory, self.store.anchor_directory)

    def test_arming_existing_observed_incident_contains_persistent_critical(self):
        self.guardian(armed=False).tick('a')
        self.assertEqual(self.controller.contain_calls, [])
        snapshot = self.guardian(armed=True).tick('a')
        self.assertEqual(len(self.controller.contain_calls), 1)
        self.assertEqual(snapshot['emergency_state'], 'AWAITING_OWNER_REVIEW')

    def test_ingested_report_counter_keys_cannot_leak_raw_data(self):
        import time
        from nerve_guardian.__main__ import telemetry_report
        path = Path(self.tmp.name) / 'report.json'
        path.write_text(json.dumps({'observations': [{'tenant': 'a', 'source': 'app',
            'observed_at': time.time(), 'status': 'OK',
            'counters': {'PATIENT_secret_api_key': 1}}]}))
        self.assertNotIn('PATIENT_secret_api_key', json.dumps(telemetry_report(path, 'a')))
