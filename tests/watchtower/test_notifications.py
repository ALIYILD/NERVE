import os
import tempfile
import time
import unittest
from pathlib import Path
from nerve_guardian.notifications import Notifier, HTTPSDelivery, protected_secret


class NotificationTests(unittest.TestCase):
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
