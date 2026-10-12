"""Real SQLite process/concurrency checks; synthetic records and no network."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway.lifecycle import QUOTA_ERROR, install_quota
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger


_WRITER = r'''
import json, sqlite3, sys
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway.lifecycle import QUOTA_ERROR
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
authority = MemoryAuthority()
actor = authority.issue('tenant-a', 'agent-a', permissions=('read','propose'))
ledger = TrustedMemoryLedger(sys.argv[1], authority)
gateway = MemoryGateway(ledger, max_records_per_scope=5)
scope = MemoryScope('tenant-a','agent-a','synthetic-patient')
print('ready', flush=True)
sys.stdin.readline()
admitted = rejected = 0
for index in range(8):
    try:
        if sys.argv[2] == 'legacy':
            ledger.propose(actor, context=scope.context, content='synthetic evidence', source_id='fixture')
        else:
            gateway.propose(actor, scope=scope, content='synthetic evidence', source_id='fixture')
        admitted += 1
    except sqlite3.IntegrityError as error:
        if str(error) != QUOTA_ERROR: raise
        rejected += 1
    except ValueError as error:
        if str(error) != 'scope record quota reached': raise
        rejected += 1
print(json.dumps({'admitted':admitted,'rejected':rejected}))
'''


class MemoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic.sqlite'
        self.authority = MemoryAuthority()
        self.actor = self.authority.issue('tenant-a', 'agent-a',
            permissions=('read', 'propose', 'approve', 'delete'))
        self.ledger = TrustedMemoryLedger(self.path, self.authority)
        self.scope = MemoryScope('tenant-a', 'agent-a', 'synthetic-patient')

    def write(self, context='synthetic-patient'):
        return self.ledger.propose(self.actor, context=context,
            content='synthetic evidence', source_id='fixture')

    def count(self, context='synthetic-patient'):
        with sqlite3.connect(self.path) as con:
            return con.execute('SELECT COUNT(*) FROM trusted_memory_v18 WHERE context=?',
                               (context,)).fetchone()[0]

    def test_multiple_processes_and_legacy_writers_share_atomic_cap(self):
        root = Path(__file__).resolve().parents[1]
        processes = [subprocess.Popen(
            [sys.executable, '-c', _WRITER, str(self.path), mode], cwd=root,
            env={**os.environ, 'PYTHONPATH': str(root / 'src')},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True) for mode in ('legacy', 'gateway', 'legacy', 'gateway')]
        try:
            # Every process has installed/read the policy before any may write.
            # Each waits on its own stdin, then all are released concurrently.
            for process in processes:
                readable, _, _ = select.select([process.stdout], [], [], 10)
                self.assertTrue(readable, 'writer startup exceeded 10s')
                self.assertEqual(process.stdout.readline().strip(), 'ready')
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda p: p.communicate('go\n', timeout=20), processes))
            totals = []
            for process, (stdout, stderr) in zip(processes, results):
                self.assertEqual(process.returncode, 0, stderr)
                totals.append(json.loads(stdout))
            self.assertEqual(sum(row['admitted'] for row in totals), 5)
            self.assertEqual(sum(row['rejected'] for row in totals), 27)
            self.assertEqual(self.count(), 5)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)

    def test_legacy_writes_limited_after_gateway_installation(self):
        self.write()
        MemoryGateway(self.ledger, max_records_per_scope=2)
        self.write()
        with self.assertRaisesRegex(sqlite3.IntegrityError, QUOTA_ERROR):
            self.write()
        self.assertEqual(self.count(), 2)
        self.write('synthetic-other')
        self.assertEqual(self.count('synthetic-other'), 1)

    def test_destination_scope_update_cannot_bypass_cap(self):
        MemoryGateway(self.ledger, max_records_per_scope=1)
        full = self.write()
        movable = self.write('synthetic-other')
        with self.assertRaisesRegex(sqlite3.IntegrityError, QUOTA_ERROR):
            with sqlite3.connect(self.path) as con:
                con.execute('UPDATE trusted_memory_v18 SET context=? WHERE memory_id=?',
                            (self.scope.context, movable))
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.count('synthetic-other'), 1)
        # A no-op scope update of an existing row must not consume new capacity.
        with sqlite3.connect(self.path) as con:
            con.execute('UPDATE trusted_memory_v18 SET context=? WHERE memory_id=?',
                        (self.scope.context, full))
        self.ledger.forget(self.actor, full)
        with sqlite3.connect(self.path) as con:
            con.execute('UPDATE trusted_memory_v18 SET context=? WHERE memory_id=?',
                        (self.scope.context, movable))
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.count('synthetic-other'), 0)

    def test_conflicting_config_cannot_relax_persisted_limit(self):
        MemoryGateway(self.ledger, max_records_per_scope=1)
        for limit in (2, 1000):
            with self.assertRaisesRegex(ValueError, 'persisted host policy'):
                MemoryGateway(self.ledger, max_records_per_scope=limit)
        self.write()
        with self.assertRaisesRegex(sqlite3.IntegrityError, QUOTA_ERROR):
            self.write()

    def test_restart_retains_limit_and_deletion_releases_capacity(self):
        MemoryGateway(self.ledger, max_records_per_scope=1)
        first = self.write()
        authority = MemoryAuthority()
        actor = authority.issue('tenant-a', 'agent-a', permissions=('read', 'propose', 'delete'))
        reopened = TrustedMemoryLedger(self.path, authority)
        gateway = MemoryGateway(reopened, max_records_per_scope=1)
        with self.assertRaisesRegex(ValueError, 'scope record quota reached'):
            gateway.propose(actor, scope=self.scope, content='new synthetic', source_id='fixture')
        gateway.delete(actor, first, scope=self.scope)
        gateway.propose(actor, scope=self.scope, content='new synthetic', source_id='fixture')
        self.assertEqual(self.count(), 1)

    def test_preexisting_over_quota_rows_survive_but_growth_stops(self):
        first, second = self.write(), self.write()
        MemoryGateway(self.ledger, max_records_per_scope=1)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.ledger.status(self.actor, first).memory_id, first)
        with self.assertRaisesRegex(sqlite3.IntegrityError, QUOTA_ERROR):
            self.write()
        self.ledger.forget(self.actor, first)
        with self.assertRaisesRegex(sqlite3.IntegrityError, QUOTA_ERROR):
            self.write()
        self.ledger.forget(self.actor, second)
        self.write()

    def test_missing_policy_row_fails_closed(self):
        install_quota(self.path, 2)
        with sqlite3.connect(self.path) as con:
            con.execute('DELETE FROM memory_gateway_limits_v1')
        with self.assertRaisesRegex(sqlite3.IntegrityError, QUOTA_ERROR):
            self.write()

    def test_killed_uncommitted_ledger_writer_recovers_without_consuming_quota(self):
        """SQLite transaction recovery only; no KV runtime or restore involved."""
        install_quota(self.path, 1)
        writer = r'''
import hashlib, sqlite3, sys, time
con = sqlite3.connect(sys.argv[1])
con.execute('BEGIN IMMEDIATE')
content = 'synthetic interrupted evidence'
con.execute('INSERT INTO trusted_memory_v18 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
    ('interrupted-record', 'tenant-a', 'agent-a', 'synthetic-patient', 'episodic',
     content, 'fixture', hashlib.sha256(content.encode()).hexdigest(), 'pending',
     None, None, int(time.time()), None, None))
print('uncommitted', flush=True)
sys.stdin.read(1)
'''
        process = subprocess.Popen([sys.executable, '-c', writer, str(self.path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        try:
            readable, _, _ = select.select([process.stdout], [], [], 10)
            self.assertTrue(readable, 'writer did not reach uncommitted transaction in 10s')
            self.assertEqual(process.stdout.readline().strip(), 'uncommitted')
            process.kill()
            process.communicate(timeout=5)
            self.assertLess(process.returncode, 0)
            # A fresh connection must recover rollback state, not a phantom row.
            self.assertEqual(self.count(), 0)
            reopened = TrustedMemoryLedger(self.path, self.authority)
            gateway = MemoryGateway(reopened, max_records_per_scope=1)
            gateway.propose(self.actor, scope=self.scope,
                            content='synthetic committed evidence', source_id='fixture')
            self.assertEqual(self.count(), 1)
            with sqlite3.connect(self.path) as con:
                self.assertIsNone(con.execute('SELECT memory_id FROM trusted_memory_v18 '
                    'WHERE memory_id=?', ('interrupted-record',)).fetchone())
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
