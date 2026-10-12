import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from nerve_guardian.telemetry import SQLiteMetadataSource, BoundedCollector
from nerve_guardian.analysis import BehaviourAnalysis


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'app.sqlite'
        with sqlite3.connect(self.path) as con:
            con.execute('CREATE TABLE gl_events(tenant TEXT, details TEXT)')
            con.executemany('INSERT INTO gl_events VALUES(?,?)', [('a', 'PATIENT secret-key'), ('b', 'private')])
        self.source = SQLiteMetadataSource(self.path, tenant='a', source='app')

    def test_read_only_tenant_scoped_redacted(self):
        before = self.path.read_bytes()
        result = self.source.sample()
        self.assertEqual(result['counters'], {'gl_events': 1})
        self.assertEqual(result['status'], 'OK')
        self.assertNotIn('PATIENT', json.dumps(result))
        self.assertNotIn('secret-key', json.dumps(result))
        self.assertEqual(before, self.path.read_bytes())

    def test_missing_not_created(self):
        missing = self.path.parent / 'missing'
        result = SQLiteMetadataSource(missing, tenant='a', source='missing').sample()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertFalse(missing.exists())
        self.assertNotIn(str(self.tmp.name), json.dumps(result))

    def test_poisoned_view_rejected(self):
        with sqlite3.connect(self.path) as con:
            con.execute('DROP TABLE gl_events')
            con.execute("CREATE VIEW gl_events AS SELECT 'a' AS tenant, 'secret' AS details")
        result = self.source.sample()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['counters'], {})

    def test_tables_allowlisted(self):
        with self.assertRaises(ValueError):
            SQLiteMetadataSource(self.path, tenant='a', source='app', tables=('gl_events; DELETE',))

    def test_adaptation_join_is_tenant_scoped(self):
        with sqlite3.connect(self.path) as con:
            con.execute('CREATE TABLE adaptation_tasks(id TEXT, tenant TEXT)')
            con.execute('CREATE TABLE adaptation_events(task TEXT, record TEXT)')
            con.executemany('INSERT INTO adaptation_tasks VALUES(?,?)', [('1','a'),('2','b')])
            con.executemany('INSERT INTO adaptation_events VALUES(?,?)', [('1','secret'),('2','private')])
        result = SQLiteMetadataSource(self.path, tenant='a', source='app', tables=('adaptation_events',)).sample()
        self.assertEqual(result['counters'], {'adaptation_events': 1})

    def test_agentos_learning_counts_are_tenant_scoped_and_metadata_only(self):
        with sqlite3.connect(self.path) as con:
            con.execute('CREATE TABLE trusted_memory_v18(tenant_id TEXT, agent_id TEXT, content TEXT)')
            con.execute('CREATE TABLE memory_utility(tenant TEXT, agent TEXT, payload_hash TEXT)')
            con.executemany('INSERT INTO trusted_memory_v18 VALUES(?,?,?)',
                            [('agentos-local', 'agent-a', 'PATIENT credential-secret'),
                             ('agentos-local', 'agent-b', 'private-memory'),
                             ('other-tenant', 'agent-c', 'unrelated-secret')])
            con.executemany('INSERT INTO memory_utility VALUES(?,?,?)',
                            [('agentos-local', 'agent-a', 'private-hash'),
                             ('other-tenant', 'agent-c', 'unrelated-hash')])
        before = self.path.read_bytes()
        source = SQLiteMetadataSource(self.path, tenant='agentos-local', source='agentos-learning',
                                      tables=('trusted_memory_v18', 'memory_utility'))
        result = source.sample()
        self.assertEqual('OK', result['status'])
        self.assertEqual({'trusted_memory_v18': 2, 'memory_utility': 1}, result['counters'])
        self.assertEqual(before, self.path.read_bytes())
        for secret in ('PATIENT', 'credential-secret', 'private-memory', 'unrelated-secret',
                       'private-hash', 'agent-a', 'other-tenant'):
            self.assertNotIn(secret, json.dumps(result))
        other = SQLiteMetadataSource(self.path, tenant='other-tenant', source='other',
                                     tables=('trusted_memory_v18', 'memory_utility')).sample()
        self.assertEqual({'trusted_memory_v18': 1, 'memory_utility': 1}, other['counters'])
        absent = SQLiteMetadataSource(self.path, tenant='absent', source='absent',
                                      tables=('trusted_memory_v18', 'memory_utility')).sample()
        self.assertEqual({'trusted_memory_v18': 0, 'memory_utility': 0}, absent['counters'])

    def test_agentos_learning_views_and_unscoped_tables_rejected(self):
        with sqlite3.connect(self.path) as con:
            con.execute("CREATE VIEW trusted_memory_v18 AS SELECT 'agentos-local' AS tenant_id")
            con.execute("CREATE VIEW memory_utility AS SELECT 'agentos-local' AS tenant")
        result = SQLiteMetadataSource(self.path, tenant='agentos-local', source='agentos-learning',
                                      tables=('trusted_memory_v18', 'memory_utility')).sample()
        self.assertEqual('UNKNOWN', result['status'])
        self.assertEqual({}, result['counters'])
        for name in ('nerve_runs', 'nerve_calls', 'nerve_missions'):
            with self.assertRaises(ValueError):
                SQLiteMetadataSource(self.path, tenant='agentos-local', source='unsafe', tables=(name,))

    def test_queue_saturation_observable(self):
        collector = BoundedCollector([self.source], max_queue=1)
        self.assertTrue(collector.submit('app'))
        self.assertFalse(collector.submit('app'))
        self.assertEqual(collector.health()['status'], 'UNKNOWN')
        collector.start()
        self.addCleanup(collector.stop)
        deadline = time.monotonic() + 1
        while not collector.results and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(len(collector.drain()), 1)
        self.assertEqual(collector.health()['dropped'], 1)

    def test_output_retention_bounded(self):
        collector = BoundedCollector([self.source], max_queue=1, retention_seconds=.01)
        collector.results.append(self.source.sample())
        collector.results[0]['observed_at'] -= 1
        self.assertEqual(collector.drain(), [])

    def test_anomaly_never_critical_and_stale_unknown(self):
        engine = BehaviourAnalysis()
        snapshot = self.source.sample()
        for count in range(6):
            snapshot.update(observed_at=100 + count, counters={'gl_events': count})
            result = engine.observe(snapshot, now=100 + count)
        self.assertEqual(result['risk'], 'NORMAL')
        snapshot.update(observed_at=106, counters={'gl_events': 1000})
        result = engine.observe(snapshot, now=106)
        self.assertEqual(result['risk'], 'WARNING')
        self.assertFalse(result['automatic_containment'])
        self.assertEqual(engine.observe(snapshot, now=200)['risk'], 'UNKNOWN')
        self.assertEqual(engine.observe(snapshot, now=106)['risk'], 'UNKNOWN')

    def test_baselines_isolated_bounded_and_decrease_warning(self):
        engine = BehaviourAnalysis(max_sources=1)
        snapshot = self.source.sample()
        snapshot.update(observed_at=100, counters={'gl_events': 5})
        engine.observe(snapshot, now=100)
        snapshot.update(observed_at=101, counters={'gl_events': 1})
        self.assertEqual(engine.observe(snapshot, now=101)['risk'], 'WARNING')
        snapshot['tenant'] = 'other'
        self.assertEqual(engine.observe(snapshot, now=101)['reason'], 'baseline_capacity_exhausted')

    def test_nan_and_boolean_observations_unknown(self):
        engine = BehaviourAnalysis()
        snapshot = self.source.sample()
        snapshot['observed_at'] = float('nan')
        self.assertEqual(engine.observe(snapshot)['risk'], 'UNKNOWN')
        snapshot.update(observed_at=100, counters={'gl_events': True})
        self.assertEqual(engine.observe(snapshot, now=100)['risk'], 'UNKNOWN')
