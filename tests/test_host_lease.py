import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from nerve_awim.host_lease import exclusive_host


class HostLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'pilot.db'
        self.path.touch()

    def test_duplicate_and_path_aliases_share_ownership(self):
        symbolic = self.path.parent/'symbolic.db'
        symbolic.symlink_to(self.path)
        hard = self.path.parent/'hard.db'
        os.link(self.path, hard)
        with exclusive_host(self.path):
            for path in (self.path, symbolic, hard):
                with self.assertRaises(BlockingIOError):
                    with exclusive_host(path):
                        self.fail('duplicate acquired ownership')

    def test_exception_releases_ownership(self):
        with self.assertRaises(ValueError):
            with exclusive_host(self.path):
                raise ValueError('interrupted')
        with exclusive_host(self.path):
            pass

    def test_killed_process_releases_ownership(self):
        code = ('from nerve_awim.host_lease import exclusive_host; import sys; '
                'lease=exclusive_host(sys.argv[1]); lease.__enter__(); '
                'print("owned", flush=True); sys.stdin.read()')
        process = subprocess.Popen([sys.executable, '-c', code, str(self.path)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            import select
            self.assertTrue(select.select([process.stdout], [], [], 5)[0])
            self.assertEqual(process.stdout.readline().strip(), 'owned')
            with self.assertRaises(BlockingIOError):
                with exclusive_host(self.path):
                    pass
            process.kill()
            process.communicate(timeout=5)
            with exclusive_host(self.path):
                pass
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def test_missing_database_requires_explicit_creation(self):
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):
            with exclusive_host(self.path):
                pass
        self.assertFalse(self.path.exists())
        with exclusive_host(self.path, create=True):
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_fifo_rejected_without_blocking(self):
        self.path.unlink()
        os.mkfifo(self.path)
        with self.assertRaises(ValueError):
            with exclusive_host(self.path):
                pass

    def test_sqlite_reads_writes_and_backup_work_while_owned(self):
        with exclusive_host(self.path):
            with sqlite3.connect(self.path) as connection:
                connection.execute('CREATE TABLE example(value INTEGER)')
                connection.execute('INSERT INTO example VALUES (7)')
            with sqlite3.connect(self.path) as connection, sqlite3.connect(':memory:') as backup:
                connection.backup(backup)
                self.assertEqual(backup.execute('SELECT value FROM example').fetchone(), (7,))

    def test_darwin_private_lock_persists_and_uses_database_inode(self):
        root = self.path.parent/'leases'
        with patch('nerve_awim.host_lease.sys.platform', 'darwin'), patch('nerve_awim.host_lease._LOCK_ROOT', root):
            with exclusive_host(self.path):
                locks = list(root.iterdir())
                self.assertEqual(len(locks), 1)
                lock = locks[0]
                info = self.path.stat()
                self.assertEqual(lock.name, f'{info.st_dev}-{info.st_ino}.lock')
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
                self.assertEqual(lock.stat().st_mode & 0o777, 0o600)
                inode = lock.stat().st_ino
            self.assertTrue(lock.exists())
            with exclusive_host(self.path):
                self.assertEqual(lock.stat().st_ino, inode)

    def test_darwin_refuses_shared_directory_and_symlink_lock(self):
        root = self.path.parent/'leases'
        root.mkdir(mode=0o755)
        with patch('nerve_awim.host_lease.sys.platform', 'darwin'), patch('nerve_awim.host_lease._LOCK_ROOT', root):
            with self.assertRaises(PermissionError):
                with exclusive_host(self.path):
                    pass
            root.chmod(0o700)
            info = self.path.stat()
            lock = root/f'{info.st_dev}-{info.st_ino}.lock'
            lock.symlink_to(self.path)
            with self.assertRaises(OSError):
                with exclusive_host(self.path):
                    pass
            self.assertEqual(self.path.read_bytes(), b'')

    def test_darwin_refuses_symlink_directory(self):
        target = self.path.parent/'target'
        target.mkdir(mode=0o700)
        root = self.path.parent/'leases'
        root.symlink_to(target)
        with patch('nerve_awim.host_lease.sys.platform', 'darwin'), patch('nerve_awim.host_lease._LOCK_ROOT', root):
            with self.assertRaises(OSError):
                with exclusive_host(self.path):
                    pass
