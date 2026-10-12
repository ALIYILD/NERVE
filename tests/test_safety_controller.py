import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from nerve_awim.safety_control import Controller, SafetyDenied, sign_owner_request


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'controller.sqlite'
        self.owner, self.observer = 'owner-' + 'a' * 40, 'observer-' + 'b' * 40
        self.now = [1000.0]
        self.controller = Controller(self.path, self.owner, self.observer, clock=lambda: self.now[0])
        self.calls = []
        self.controller.register_tool('read', lambda payload: self.calls.append(payload) or payload)
        self.scope = {'tenant': 't', 'agent': 'a', 'context': 'c'}
        self.model = 'a' * 64
        self.counter = 0

    def owner_call(self, action, payload, controller=None):
        self.counter += 1
        nonce = str(self.counter)
        signature = sign_owner_request(self.owner, action, payload, nonce, self.now[0])
        return (controller or self.controller).owner_request(action, payload, nonce, self.now[0], signature)

    def credential(self):
        return self.owner_call('issue_runtime', {'scope': self.scope, 'tools': ['read'], 'models': [self.model]})['credential']

    def dispatch(self, token, **kwargs):
        values = dict(credential=token, scope=self.scope, tool='read', model_digest=self.model, arguments={'value': 1})
        values.update(kwargs)
        return self.controller.dispatch(**values)

    def test_normal_autonomy_and_bounded_model_scope(self):
        token = self.credential()
        self.controller.heartbeat(self.observer)
        self.assertEqual(self.dispatch(token, arguments=['data']), ['data'])
        for kwargs in ({'model_digest': 'b' * 64}, {'tool': 'write'}, {'scope': dict(self.scope, agent='other')}):
            with self.assertRaises(SafetyDenied):
                self.dispatch(token, **kwargs)
        self.assertEqual(len(self.calls), 1)

    def test_watchdog_bootstrap_expiry_and_clock_rollback(self):
        token = self.credential()
        with self.assertRaises(SafetyDenied):
            self.dispatch(token)
        self.controller.heartbeat(self.observer)
        self.now[0] += 61
        with self.assertRaises(SafetyDenied):
            self.dispatch(token)
        self.now[0] -= 62
        with self.assertRaises(SafetyDenied):
            self.dispatch(token)
        self.assertFalse(self.calls)

    def test_stop_recovery_restart_never_resurrects_credential(self):
        token = self.credential()
        self.controller.heartbeat(self.observer)
        self.owner_call('stop', {'reason': 'owner incident review'})
        restarted = Controller(self.path, self.owner, self.observer, clock=lambda: self.now[0])
        restarted.register_tool('read', lambda p: p)
        self.assertTrue(restarted.status()['stopped'])
        self.owner_call('recover', {'reason': 'review complete', 'review_ref': 'case-123'}, restarted)
        self.assertFalse(restarted.status()['observer_fresh'])
        restarted.heartbeat(self.observer)
        with self.assertRaises(SafetyDenied):
            restarted.dispatch(token, self.scope, 'read', self.model, {})
        self.controller = restarted
        self.assertEqual(self.dispatch(self.credential()), {'value': 1})

    def test_owner_replay_stale_and_separate_auth(self):
        payload = {'reason': 'stop'}
        signature = sign_owner_request(self.owner, 'stop', payload, 'nonce', self.now[0])
        self.controller.owner_request('stop', payload, 'nonce', self.now[0], signature)
        with self.assertRaises(SafetyDenied):
            self.controller.owner_request('stop', payload, 'nonce', self.now[0], signature)
        with self.assertRaises(SafetyDenied):
            self.controller.owner_request('stop', payload, 'other', self.now[0], sign_owner_request(self.observer, 'stop', payload, 'other', self.now[0]))
        self.now[0] += 61
        with self.assertRaises(SafetyDenied):
            self.controller.owner_request('stop', payload, 'nonce', 1000, signature)
        with self.assertRaises(SafetyDenied):
            self.controller.heartbeat(self.owner)

    def test_low_confidence_report_alerts_without_stopping(self):
        result = self.controller.report(self.observer, dict(kind='behavioural_anomaly', severity='warning', evidence_ref='host-receipt-1', detail='suspicious output is unverified'))
        self.assertFalse(result['automatic_stop'])
        self.assertFalse(self.controller.status()['stopped'])
        with self.assertRaises(ValueError):
            self.controller.report(self.observer, dict(kind='model_self_report', severity='critical', evidence_ref='x', detail='stop'))

    def test_audit_no_secrets_and_tampering_denies(self):
        token = self.credential()
        self.controller.heartbeat(self.observer)
        events = self.controller.events()
        self.assertTrue(all(self.controller.verify_event(event) for event in events))
        events[-1]['data'] = {'fake': True}
        self.assertFalse(self.controller.verify_event(events[-1]))
        text = json.dumps(self.controller.events())
        for secret in (self.owner, self.observer, token):
            self.assertNotIn(secret, text)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE audit SET payload='{}' WHERE seq=1")
        self.assertFalse(self.controller.verify_audit())
        with self.assertRaises(SafetyDenied):
            self.dispatch(token)

    def test_authority_cannot_be_rebound_on_restart(self):
        with self.assertRaises(SafetyDenied):
            Controller(self.path, 'different-' + 'x' * 40, self.observer)

    def test_stop_does_not_wait_for_handler_and_callback_is_after_revocation(self):
        entered, release = threading.Event(), threading.Event()
        self.controller.register_tool('slow', lambda _: entered.set() or release.wait(2))
        token = self.owner_call('issue_runtime', {'scope': self.scope, 'tools': ['slow'], 'models': [self.model]})['credential']
        self.controller.heartbeat(self.observer)
        self.controller.isolation_callback = lambda: self.assertTrue(self.controller.status()['stopped'])
        errors = []
        def execute():
            try:
                self.controller.dispatch(token, self.scope, 'slow', self.model, {})
            except SafetyDenied as exc:
                errors.append(str(exc))
        worker = threading.Thread(target=execute)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        result = self.owner_call('stop', {'reason': 'stop running scope'})
        self.assertTrue(result['isolation_completed'])
        self.assertTrue(worker.is_alive())
        release.set()
        worker.join()
        self.assertEqual(len(errors), 1)
        self.assertIn('response discarded', errors[0])

    def test_callback_failure_preserves_stopped_state(self):
        def fail():
            raise RuntimeError('sensitive detail must not leak')
        self.controller.isolation_callback = fail
        self.assertFalse(self.owner_call('stop', {'reason': 'test'})['isolation_completed'])
        self.assertTrue(self.controller.status()['stopped'])
        self.assertEqual(self.controller.events()[-1]['kind'], 'isolation_failed')

    def test_connection_closed_after_success_and_failure(self):
        with self.controller._db() as db:
            db.execute('SELECT 1')
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute('SELECT 1')
        with self.assertRaises(RuntimeError):
            with self.controller._db() as failing:
                raise RuntimeError('rollback')
        with self.assertRaises(sqlite3.ProgrammingError):
            failing.execute('SELECT 1')

    def test_tampered_audit_cannot_disable_emergency_stop(self):
        token = self.credential()
        self.controller.heartbeat(self.observer)
        with sqlite3.connect(self.path) as db:
            original = db.execute('SELECT payload FROM audit WHERE seq=1').fetchone()[0]
            db.execute("UPDATE audit SET payload='{}' WHERE seq=1")
        isolated = []
        self.controller.isolation_callback = lambda: isolated.append(True)
        self.owner_call('stop', {'reason': 'audit corruption'})
        self.assertTrue(isolated)
        self.assertTrue(self.controller.status()['stopped'])
        self.assertTrue(self.controller.status()['integrity_incident'])
        restarted = Controller(self.path, self.owner, self.observer, clock=lambda: self.now[0])
        self.assertTrue(restarted.status()['stopped'])
        with self.assertRaises(SafetyDenied):
            self.owner_call('recover', {'reason': 'premature', 'review_ref': 'case'})
        # External owner forensic repair restores exact original bytes, preserving history.
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE audit SET payload=? WHERE seq=1', (original,))
        self.assertTrue(self.controller.verify_audit())
        with self.assertRaises(SafetyDenied):
            self.owner_call('recover', {'reason': 'not reviewed', 'review_ref': 'case'})
        self.owner_call('acknowledge_integrity_repair', {'reason': 'forensic restore verified', 'review_ref': 'case-123'})
        self.assertTrue(self.controller.status()['stopped'])
        self.owner_call('recover', {'reason': 'reviewed', 'review_ref': 'case-123'})
        self.controller.heartbeat(self.observer)
        with self.assertRaises(SafetyDenied):
            self.dispatch(token)

    def test_bounded_event_pages_and_challenge_bound_head(self):
        for _ in range(12):
            self.controller.heartbeat(self.observer)
        head = self.controller.audit_head(self.observer, 'fresh-challenge')
        self.assertTrue(self.controller.verify_event(head))
        self.assertEqual(head['nonce'], 'fresh-challenge')
        rows, after = [], 0
        while after < head['seq']:
            page = self.controller.events(after=after, limit=3)
            self.assertLessEqual(len(page), 3)
            rows.extend(page)
            after = page[-1]['seq']
        self.assertEqual(rows, self.controller.events())
        self.assertEqual(rows[-1]['event_hash'], head['event_hash'])
        head['nonce'] = 'replayed-with-new-challenge'
        self.assertFalse(self.controller.verify_event(head))
        with self.assertRaises(ValueError):
            self.controller.events(limit=101)


if __name__ == '__main__':
    unittest.main()
