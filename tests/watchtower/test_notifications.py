import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from nerve_guardian.notifications import Notifier, HTTPSDelivery, protected_secret


class NotificationTests(unittest.TestCase):
    def test_shutdown_bounds_stalled_dispatch_and_rejects_new_alerts(self):
        release = threading.Event()
        class StalledNotifier(Notifier):
            def _dispatch(self):
                release.wait(5)
        with tempfile.TemporaryDirectory() as root:
            notifier = StalledNotifier(Path(root)/'outbox.db', {'email': lambda alert: None})
            try:
                alert = dict(tenant='a', incident_id='i', event='critical')
                self.assertTrue(notifier.enqueue(alert))
                start = time.monotonic()
                self.assertFalse(notifier.close(timeout=.1))
                self.assertLess(time.monotonic()-start, .5)
                self.assertFalse(notifier.enqueue(alert))
                self.assertEqual(notifier.health()['status'], 'UNKNOWN')
                self.assertTrue(notifier.health()['closing'])
            finally:
                release.set()
                for thread in notifier.threads: thread.join(2)

    def test_stalled_provider_does_not_block_close_and_pending_recovers(self):
        entered, release = threading.Event(), threading.Event()
        def blocked(alert):
            entered.set()
            release.wait(5)
            raise RuntimeError('synthetic provider outage')
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'outbox.db'
            notifier = Notifier(path, {'email': blocked}, rate_seconds=0)
            try:
                notifier.enqueue(dict(tenant='a', incident_id='i', event='critical'))
                self.assertTrue(entered.wait(2))
                start = time.monotonic()
                self.assertFalse(notifier.close(timeout=.1))
                self.assertLess(time.monotonic()-start, .5)
                self.assertEqual(notifier.status('a')[0]['status'], 'pending')
            finally:
                release.set()
                self.assertTrue(notifier.close(timeout=2))
            received = []
            restored = Notifier(path, {'email': received.append}, rate_seconds=0)
            try:
                self.wait_for(lambda: bool(received))
                self.wait_for(lambda: restored.status('a')[0]['status']=='accepted')
                self.assertEqual(len(received), 1)
            finally:
                self.assertTrue(restored.close())

    def test_shutdown_rejects_invalid_budgets_without_closing(self):
        with tempfile.TemporaryDirectory() as root:
            notifier = Notifier(Path(root)/'outbox.db', {'email': lambda alert: None})
            try:
                for timeout in (-1, float('inf'), float('nan'), 61, '1'):
                    with self.assertRaises(ValueError): notifier.close(timeout)
                self.assertFalse(notifier.closing.is_set())
            finally: self.assertTrue(notifier.close())

    def wait_for(self, test, seconds=4):
        end = time.monotonic()+seconds
        while time.monotonic()<end:
            if test(): return
            time.sleep(.02)
        self.fail('notification did not settle')

    def test_parallel_channels_dedup_retry_and_tenant_isolation(self):
        with tempfile.TemporaryDirectory() as root:
            received = []
            def fail(alert): raise RuntimeError('SECRET provider failure')
            notifier = Notifier(Path(root)/'outbox.db', {'telegram':fail,'email':received.append},max_attempts=2,rate_seconds=0)
            alert = dict(tenant='a',incident_id='incident',event='critical',raw_patient_data='never include')
            try:
                start=time.monotonic(); notifier.enqueue(alert)
                self.assertLess(time.monotonic()-start,.1)
                notifier.enqueue(alert)
                self.wait_for(lambda: len(notifier.status('a'))==2 and all(row['status']!='pending' for row in notifier.status('a')))
                self.assertEqual(len(received),1)
                self.assertNotIn('raw_patient_data',received[0])
                self.assertEqual(notifier.status('b'),[])
                rows = {row['channel']:row for row in notifier.status('a')}
                self.assertEqual(rows['telegram']['status'],'failed')
                self.assertEqual(rows['telegram']['attempts'],2)
                self.assertEqual(rows['email']['status'],'accepted')
            finally: notifier.close()
            restored=Notifier(Path(root)/'outbox.db',{'email':received.append},rate_seconds=0)
            try:
                restored.enqueue(alert); restored.pending.join(); time.sleep(.1)
                self.assertEqual(len(received),1)
            finally: restored.close()

    def test_credential_permissions_and_https(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'secret'; path.write_text('test-only'); path.chmod(0o600)
            self.assertEqual(protected_secret(path,{os.getuid()}),'test-only')
            path.chmod(0o644)
            with self.assertRaises(ValueError): protected_secret(path,{os.getuid()})
            link=Path(root)/'link'; link.symlink_to(path)
            with self.assertRaises(OSError): protected_secret(link,{os.getuid()})
            for endpoint in ('http://api.telegram.org','https://evil.example','https://api.telegram.org?token=x'):
                with self.assertRaises(ValueError):
                    HTTPSDelivery(channel='telegram',endpoint=endpoint,secret_path=path,allowed_uids={os.getuid()},recipient='test')

    def test_https_provider_contract_and_sanitized_failure(self):
        import json
        import urllib.error
        from unittest.mock import patch
        class Response:
            status = 200
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return self.payload[:limit]
        class Opener:
            def __init__(self, result): self.result=result; self.requests=[]
            def open(self, request, timeout):
                self.requests.append((request,timeout))
                if isinstance(self.result, Exception): raise self.result
                return Response(self.result)
        with tempfile.TemporaryDirectory() as root:
            secret=Path(root)/'secret'; secret.write_text('123:TEST_ONLY_SECRET'); secret.chmod(0o600)
            telegram=HTTPSDelivery(channel='telegram',endpoint='https://api.telegram.org',secret_path=secret,allowed_uids={os.getuid()},recipient='test-chat')
            email=HTTPSDelivery(channel='email',endpoint='https://mail.example/send',secret_path=secret,allowed_uids={os.getuid()},recipient='owner@example.test',sender='guardian@example.test')
            for adapter, result in ((telegram,b'{"ok":true}'),(email,b'{"id":"test-message"}')):
                opener=Opener(result)
                with patch('urllib.request.build_opener',return_value=opener): adapter({'incident_id':'synthetic'})
                self.assertEqual(opener.requests[0][1],5)
                self.assertEqual(opener.requests[0][0].method,'POST')
            failures = [b'{"ok":false}', b'not-json', b'[]', b'x'*16385,
                urllib.error.HTTPError('https://api.telegram.org/bot123:TEST_ONLY_SECRET/sendMessage',429,'TEST_ONLY_SECRET',{},None)]
            for result in failures:
                with patch('urllib.request.build_opener',return_value=Opener(result)):
                    with self.assertRaises(ValueError) as error: telegram({'incident_id':'synthetic'})
                    self.assertNotIn('TEST_ONLY_SECRET',str(error.exception))
            for result in (b'{"error":"rejected"}',b'{}',urllib.error.HTTPError('https://mail.example/send',500,'TEST_ONLY_SECRET',{},None)):
                with patch('urllib.request.build_opener',return_value=Opener(result)):
                    with self.assertRaises(ValueError): email({'incident_id':'synthetic'})
            opener=Opener(failures[-1])
            with patch('urllib.request.build_opener',return_value=opener):
                notifier=Notifier(Path(root)/'outbox.db',{'telegram':telegram},max_attempts=2,rate_seconds=0)
                try:
                    notifier.enqueue(dict(tenant='a',incident_id='synthetic',event='critical'))
                    self.wait_for(lambda: bool(notifier.status('a')) and notifier.status('a')[0]['status']=='failed')
                    self.assertEqual(len(opener.requests),2)
                    self.assertEqual(notifier.health()['status'],'UNKNOWN')
                    self.assertNotIn(b'TEST_ONLY_SECRET',(Path(root)/'outbox.db').read_bytes())
                    self.assertTrue(all(thread.is_alive() for thread in notifier.threads))
                finally: notifier.close()

    def test_database_connections_closed_on_success_and_error(self):
        from unittest.mock import Mock, patch
        notifier=object.__new__(Notifier); notifier.database='unused'
        connection=Mock(); connection.__enter__=Mock(return_value=connection); connection.__exit__=Mock(return_value=False)
        with patch('nerve_guardian.notifications.sqlite3.connect',return_value=connection):
            with notifier._db(): pass
            connection.close.assert_called_once()
            connection.close.reset_mock()
            with self.assertRaises(RuntimeError):
                with notifier._db(): raise RuntimeError('synthetic')
            connection.close.assert_called_once()
