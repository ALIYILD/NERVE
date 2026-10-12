import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('maintenance_collector', Path(__file__).resolve().parents[1] / 'scripts/agentos_maintenance.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class MaintenanceCollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.now = 10000
        self.runtime = self.home / '.agentic-os/runtime-utilization.json'
        self.cron = self.home / '.hermes/profiles/coordinator/cron/jobs.json'
        self.db = self.home / '.hermes/kanban/boards/agentos-maintenance/kanban.db'
        for path in (self.runtime, self.cron, self.db):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.write_text(json.dumps({'ts': 9999, 'services': {'hermes': {'ok': True}, 'dashboard': {'ok': True}}, 'boards': [{'counts': {'blocked': 1}, 'private': 'SECRET'}]}))
        self.cron.write_text(json.dumps({'updated_at': 9999, 'jobs': [{'id': 'j1', 'enabled': True, 'schedule': {'kind': 'cron'}, 'next_run_at': 9940, 'last_status': 'ok', 'last_run_at': 9800, 'deliver': 'local', 'prompt': 'SECRET'}]}))
        conn = sqlite3.connect(self.db)
        conn.executescript('''CREATE TABLE tasks (id TEXT,status TEXT,current_run_id INTEGER,max_retries INTEGER,consecutive_failures INTEGER,max_runtime_seconds INTEGER,body TEXT);
CREATE TABLE task_runs (id INTEGER,task_id TEXT,status TEXT,started_at INTEGER,ended_at INTEGER,last_heartbeat_at INTEGER,max_runtime_seconds INTEGER,error TEXT);
CREATE TABLE task_links (parent_id TEXT,child_id TEXT);
INSERT INTO tasks VALUES ('a','blocked',NULL,1,1,240,'SECRET');
INSERT INTO tasks VALUES ('b','todo',NULL,1,0,240,'SECRET');
INSERT INTO task_runs VALUES (1,'a','timed_out',9000,9243,9200,240,'SECRET');
INSERT INTO task_links VALUES ('a','b');''')
        conn.close()

    def test_blocked_workflow_separate_from_healthy_sources(self):
        before = {p: p.read_bytes() for p in (self.runtime, self.cron, self.db)}
        report = collector.collect(self.home, self.now)
        self.assertEqual(report['status'], 'blocked')
        self.assertEqual(report['source_service_status'], 'ok')
        tasks = report['workflow']['unresolved_tasks']
        self.assertEqual(tasks[0]['retry_disposition'], 'exhausted')
        self.assertEqual(tasks[0]['timeout_diagnosis'], 'watchdog_window')
        self.assertEqual(tasks[1]['dependency_readiness'], 'waiting')
        self.assertEqual(report['schedule']['jobs'][0]['freshness'], 'within_tick')
        self.assertEqual(report['schedule']['inventory']['cron'], 1)
        self.assertNotIn('SECRET', json.dumps(report))
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_recovery_preserves_history_but_resets_breaker(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE tasks SET status='ready', consecutive_failures=0 WHERE id='a'")
        conn.commit()
        conn.close()
        report = collector.collect(self.home, self.now)
        task = report['workflow']['unresolved_tasks'][0]
        self.assertEqual(task['retry_chain']['attempts'], 1)
        self.assertEqual(task['consecutive_failures'], 0)
        self.assertEqual(task['retry_disposition'], 'eligible')

    def test_schedule_health_rejects_unsupported_success(self):
        original = json.loads(self.cron.read_text())
        for updates, expected in (({'last_status': 'error'}, 'failed'),
                                  ({'deliver': 'remote'}, 'failed'),
                                  ({'last_run_at': None}, 'unknown')):
            data = json.loads(json.dumps(original))
            data['jobs'][0].update(updates)
            self.cron.write_text(json.dumps(data))
            self.assertEqual(collector.collect(self.home, self.now)['schedule']['status'], expected)
        original['jobs'].append(dict(original['jobs'][0]))
        self.cron.write_text(json.dumps(original))
        report = collector.collect(self.home, self.now)
        self.assertEqual(report['schedule']['inventory']['invalid'], 1)
        self.assertEqual(report['schedule']['status'], 'unknown')

    def test_board_queries_share_read_transaction(self):
        from unittest.mock import patch
        original = sqlite3.connect
        writer = original(self.db)
        self.addCleanup(writer.close)
        writer.execute('PRAGMA journal_mode=WAL')
        changes = []
        def on_query(statement):
            if statement.startswith('SELECT id,task_id'):
                writer.execute("UPDATE tasks SET status='done'")
                writer.execute("UPDATE task_runs SET status='done'")
                writer.commit()
                changes.append(True)
        def traced(*args, **kwargs):
            conn = original(*args, **kwargs)
            conn.set_trace_callback(on_query)
            return conn
        with patch.object(collector.sqlite3, 'connect', traced):
            report = collector.collect(self.home, self.now)
        self.assertTrue(changes)
        self.assertEqual(report['workflow']['unresolved_tasks'][0]['status'], 'blocked')
        self.assertEqual(report['workflow']['unresolved_tasks'][0]['latest_run']['status'], 'timed_out')
        self.assertEqual(writer.execute('SELECT status FROM task_runs').fetchone()[0], 'done')

    def test_missing_sources_unknown_not_healthy(self):
        with tempfile.TemporaryDirectory() as empty:
            report = collector.collect(empty, self.now)
        self.assertEqual(report['status'], 'unknown')
        self.assertIsNone(report['schedule']['enabled_count'])
        self.assertEqual(report['source_service_status'], 'unknown')

    def test_stale_services_unknown_and_overdue_boundary(self):
        data = json.loads(self.runtime.read_text())
        data['ts'] = 1
        self.runtime.write_text(json.dumps(data))
        report = collector.collect(self.home, self.now + 1)
        self.assertEqual(report['services']['hermes'], 'unknown')
        self.assertEqual(report['schedule']['jobs'][0]['freshness'], 'overdue')
        self.assertEqual(report['schedule']['status'], 'overdue')

    def test_unknown_future_or_naive_timestamp(self):
        self.assertIsNone(collector.epoch('2026-10-12T00:00:00'))
        self.assertIsNone(collector.epoch(True))
        self.assertEqual(collector._freshness(20000, self.now), 'unknown')

    def test_size_bound_marks_truncation(self):
        data = json.loads(self.cron.read_text())
        template = data['jobs'][0]
        data['jobs'] = [dict(template, id=str(i)) for i in range(1000)]
        self.cron.write_text(json.dumps(data))
        report = collector.collect(self.home, self.now)
        self.assertTrue(report['truncated'])
        self.assertEqual(report['status'], 'unknown')
        self.assertLess(len(json.dumps(report).encode()), collector.MAX_BYTES)
        self.assertEqual(report['schedule']['enabled_count'], 1000)

    def test_malformed_jobs_is_unknown(self):
        self.cron.write_text(json.dumps({'updated_at': 9999, 'jobs': ['SECRET']}))
        report = collector.collect(self.home, self.now)
        self.assertEqual(report['source_health']['cron']['read'], 'invalid')
        self.assertIsNone(report['schedule']['enabled_count'])


if __name__ == '__main__':
    unittest.main()
