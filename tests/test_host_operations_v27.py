import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_repository_host_v25 as fixtures
import test_bound_repository_host_v26 as bound
from scripts.serve_repository_host_v25 import build_host
from nerve_awim.store_recovery_v27 import copy_store, verify_store


@unittest.skipIf(fixtures.jwt is None, 'PyJWT[crypto] required')
class OperationsTests(unittest.TestCase):
    token = fixtures.HostTests.token
    request = fixtures.HostTests.request
    setUp = fixtures.HostTests.setUp

    @classmethod
    def setUpClass(cls):
        fixtures.HostTests.setUpClass.__func__(cls)

    def command(self, *args):
        return subprocess.run([sys.executable, *args], env={**os.environ, 'PYTHONPATH': 'src'},
                              capture_output=True, text=True, timeout=10)

    def config_file(self):
        path = Path(self.temp.name)/'identity.json'
        path.write_text(json.dumps(self.config))
        return path

    def test_readiness_is_authenticated_scoped_and_read_only(self):
        status, result, _ = self.request(path='/v1/readiness', method='GET')
        self.assertEqual(status, 200)
        self.assertEqual(result, {'ready': True, 'mode': 'shadow', 'degraded': False})
        self.assertEqual(self.request(path='/v1/readiness', method='GET', token=self.token(roles=['nerve-runtime']))[0], 403)
        self.assertEqual(self.request(path='/v1/readiness', method='GET', overrides={'HTTP_AUTHORIZATION': ''})[0], 401)
        with self.host.engine._db() as con:
            con.execute("UPDATE gl_state SET generation=1 WHERE tenant='a'")
        self.assertEqual(self.request(path='/v1/readiness', method='GET')[0], 503)
        self.assertEqual(self.request(path='/v1/readiness', method='GET', token=self.token(sub='bob'))[0], 200)

    def test_preflight_no_listen_and_invalid_configuration_is_sanitised(self):
        config = self.config_file()
        command = ('scripts/serve_repository_host_v25.py', '--config', str(config), '--database', str(self.db), '--check')
        run = self.command(*command)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['scopes_checked'], 2)
        config.write_text('PRIVATE-INVALID-CONFIG')
        failed = self.command(*command)
        self.assertEqual(failed.returncode, 1)
        self.assertNotIn('PRIVATE-INVALID-CONFIG', failed.stderr)
        self.assertNotIn('Traceback', failed.stderr)

    def test_preflight_does_not_bootstrap_missing_database(self):
        path = Path(self.temp.name)/'absent.db'
        run = self.command('scripts/serve_repository_host_v25.py', '--config', str(self.config_file()),
                           '--database', str(path), '--check')
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse(path.exists())

    def test_backup_restore_preserves_learning_and_permissions(self):
        self.request()
        self.host.drain()
        backup = Path(self.temp.name)/'backup.db'
        restored = Path(self.temp.name)/'restored.db'
        self.assertTrue(copy_store(self.db, backup)['published'])
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(verify_store(backup)['scopes'], 2)
        copy_store(backup, restored)
        self.host = build_host(self.config, restored)
        report = self.request(path='/v1/evidence', method='GET')[1]
        self.assertEqual(report['actual_active_outcomes'][0]['hits'], 1)
        self.assertTrue(self.host.readiness(('a', 'repo'))['ready'])

    def test_existing_destination_and_source_are_never_overwritten(self):
        destination = Path(self.temp.name)/'keep.db'
        destination.write_bytes(b'KEEP')
        for path in (destination, self.db):
            with self.assertRaises(FileExistsError):
                copy_store(self.db, path)
        self.assertEqual(destination.read_bytes(), b'KEEP')
        self.assertEqual(verify_store(self.db)['integrity'], 'ok')

    def test_symlink_destination_rejected_including_dangling(self):
        target = Path(self.temp.name)/'missing.db'
        link = Path(self.temp.name)/'link.db'
        link.symlink_to(target)
        with self.assertRaises(FileExistsError):
            copy_store(self.db, link)
        self.assertFalse(target.exists())

    def test_corrupt_and_foreign_database_not_published(self):
        corrupt = Path(self.temp.name)/'corrupt.db'
        corrupt.write_bytes(b'not sqlite')
        foreign = Path(self.temp.name)/'foreign.db'
        with sqlite3.connect(foreign) as con:
            con.execute('CREATE TABLE other(id INTEGER)')
        for source in (corrupt, foreign):
            destination = Path(self.temp.name)/('copy-'+source.name)
            with self.assertRaises((ValueError, sqlite3.DatabaseError)):
                copy_store(source, destination)
            self.assertFalse(destination.exists())
        self.assertEqual(list(Path(self.temp.name).glob('.nerve-backup-*')), [])

    def test_interrupted_backup_leaves_no_published_file(self):
        destination = Path(self.temp.name)/'interrupted.db'
        with patch('nerve_awim.store_recovery_v27.time.monotonic', side_effect=(0, 31)):
            with self.assertRaises(TimeoutError):
                copy_store(self.db, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(list(Path(self.temp.name).glob('.nerve-backup-*')), [])

    def test_atomic_publication_does_not_clobber_racing_writer(self):
        destination = Path(self.temp.name)/'racing.db'
        original = os.link
        def raced(src, dst):
            Path(dst).write_bytes(b'OTHER-WRITER')
            return original(src, dst)
        with patch('nerve_awim.store_recovery_v27.os.link', side_effect=raced):
            with self.assertRaises(FileExistsError):
                copy_store(self.db, destination)
        self.assertEqual(destination.read_bytes(), b'OTHER-WRITER')

    def test_wal_backup_includes_committed_changes(self):
        connection = sqlite3.connect(self.db)
        try:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute("INSERT INTO gl_events(tenant,agent,event,details) VALUES('a','repo','wal-test','{}')")
            connection.commit()
            destination = Path(self.temp.name)/'wal-backup.db'
            copy_store(self.db, destination)
            with sqlite3.connect(destination) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM gl_events WHERE event='wal-test'").fetchone()[0], 1)
        finally:
            connection.close()

    def test_cli_backup_verify_restore(self):
        backup, restored = (Path(self.temp.name)/name for name in ('cli-backup.db', 'cli-restored.db'))
        for action, source, destination in [('backup', self.db, backup), ('verify', backup, None), ('restore', backup, restored)]:
            args = ['scripts/manage_repository_store_v27.py', action, '--source', str(source)]
            if destination:
                args.extend(['--destination', str(destination)])
            run = self.command(*args)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['integrity'], 'ok')
        self.assertEqual(verify_store(restored)['scopes'], 2)


@unittest.skipIf(fixtures.jwt is None, 'PyJWT[crypto] required')
class BoundRecoveryTests(unittest.TestCase):
    token = bound.BoundHostTests.token
    request = bound.BoundHostTests.request
    setUp = bound.BoundHostTests.setUp
    task = bound.BoundHostTests.task
    candidate_at = bound.BoundHostTests.candidate_at
    bind = bound.BoundHostTests.bind
    selected = bound.BoundHostTests.selected
    send = bound.BoundHostTests.send
    ready = bound.BoundHostTests.ready
    promote = bound.BoundHostTests.promote

    @classmethod
    def setUpClass(cls):
        fixtures.HostTests.setUpClass.__func__(cls)

    def test_monitor_restore_retains_binding_and_rollback(self):
        self.promote()
        snapshot = Path(self.temp.name)/'monitor-snapshot.db'
        restored = Path(self.temp.name)/'monitor-restored.db'
        copy_store(self.db, snapshot)
        copy_store(snapshot, restored)
        self.host = build_host(self.config, restored)
        result = self.request(path='/v1/readiness', method='GET')[1]
        self.assertTrue(result['ready'])
        self.assertFalse(result['degraded'])
        # Real registry restored; nested-function regex error triggers rollback.
        result = self.request({'task_id': 'restored-failure', 'source': 'def outer():\n    def nested(): pass'})[1]
        self.assertEqual(result['monitor']['reason'], 'quality_failure')
        self.assertEqual(result['release'], self.base)
        self.assertTrue(self.request(path='/v1/readiness', method='GET')[1]['ready'])

    def test_pending_recovery_reports_degraded_without_unlocking(self):
        self.promote()
        with self.engine._db() as con:
            con.execute('INSERT INTO gl_promotion_outcomes VALUES(?,?,?,NULL)', (self.trial, 'interrupted', 'pending'))
        result = self.request(path='/v1/readiness', method='GET')[1]
        self.assertTrue(result['ready'])
        self.assertTrue(result['degraded'])
        self.assertEqual(result['reason'], 'pending_attempt_baseline_only')
        self.assertEqual(self.send(self.task(999999))[1]['monitor']['reason'], 'pending_attempt')
