"""Passive metadata only. Application-owned databases are untrusted evidence.

This module has no NERVE imports, write connection or containment authority.
Deploy under a distinct read-only identity. A successful read proves collection,
not completeness or freshness of the underlying application activity.
"""
from collections import deque
from pathlib import Path
from queue import Queue, Empty, Full
from threading import Event, Lock, Thread
import re
import sqlite3
import time

_TABLES = {
    name: f'SELECT count(*) FROM {name} WHERE tenant=?'
    for name in ('gl_tasks', 'gl_outcomes', 'gl_candidates', 'gl_releases', 'gl_events',
                 'adaptation_tasks')
}
_TABLES.update({name: f'SELECT count(*) FROM {name} e JOIN adaptation_tasks t ON e.task=t.id WHERE t.tenant=?'
                for name in ('adaptation_events', 'adaptation_corrections', 'adaptation_checkpoints')})


def _label(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', value):
        raise ValueError('bounded administrative identifier required')
    return value


class SQLiteMetadataSource:
    def __init__(self, path, *, tenant, source, tables=('gl_events',), max_seconds=0.1):
        self.path = Path(path)
        self.tenant, self.source = _label(tenant), _label(source)
        if not tables or len(tables) > len(_TABLES) or any(t not in _TABLES for t in tables):
            raise ValueError('allowlisted tables required')
        if not 0 < max_seconds <= 2:
            raise ValueError('bounded read deadline required')
        self.tables, self.max_seconds = tuple(dict.fromkeys(tables)), max_seconds

    def sample(self):
        result = {'tenant': self.tenant, 'source': self.source,
                  'source_type': 'application_untrusted', 'observed_at': time.time(),
                  'status': 'UNKNOWN', 'counters': {}, 'coverage': [],
                  'gaps': ['application_activity_freshness_unverified', 'independent_infrastructure_required']}
        con = None
        try:
            # mode=ro prevents creation/writes. query_only is defense in depth.
            con = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True,
                                  timeout=self.max_seconds)
            con.execute('PRAGMA query_only=ON')
            con.execute('PRAGMA trusted_schema=OFF')
            deadline = time.monotonic() + self.max_seconds
            con.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
            con.execute('BEGIN')
            for table in self.tables:
                try:
                    # Reject attacker-supplied views, even if their names match.
                    kind = con.execute('SELECT type FROM sqlite_master WHERE name=?', (table,)).fetchone()
                    if kind != ('table',):
                        result['gaps'].append('missing_table:' + table)
                        continue
                    if table.startswith('adaptation_') and table != 'adaptation_tasks':
                        if con.execute("SELECT type FROM sqlite_master WHERE name='adaptation_tasks'").fetchone() != ('table',):
                            raise sqlite3.DatabaseError('invalid tenant binding')
                    result['counters'][table] = con.execute(_TABLES[table], (self.tenant,)).fetchone()[0]
                    result['coverage'].append(table)
                except sqlite3.Error:
                    result['gaps'].append('read_failed:' + table)
            # Collection OK is not a behavioural safety status.
            result['status'] = 'OK' if len(result['coverage']) == len(self.tables) else 'UNKNOWN'
        except (OSError, sqlite3.Error, ValueError):
            result['gaps'].append('source_unavailable')
        finally:
            if con is not None:
                con.close()
        return result


class BoundedCollector:
    """One daemon worker; bounded input/output; no NERVE caller ever waits.

    Memory retention is capped by capacity and retention_seconds. Production
    persistence must reside in the separately administered control-plane store.
    """
    def __init__(self, sources, *, max_queue=32, retention_seconds=300):
        if type(max_queue) is not int or not 1 <= max_queue <= 4096 or not 0 < retention_seconds <= 86400:
            raise ValueError('bounded collection configuration required')
        if len(sources) > 128 or any(not isinstance(s, SQLiteMetadataSource) for s in sources):
            raise ValueError('bounded explicit sources required')
        self.sources = {s.source: s for s in sources}
        if len(self.sources) != len(sources):
            raise ValueError('unique source identifiers required')
        self.queue = Queue(max_queue)
        self.results = deque(maxlen=max_queue)
        self.retention_seconds = retention_seconds
        self.dropped = 0
        self._lock, self._stop, self._thread = Lock(), Event(), None

    def submit(self, source):
        if source not in self.sources:
            raise ValueError('unknown configured source')
        try:
            self.queue.put_nowait(source)
            return True
        except Full:
            with self._lock:
                self.dropped += 1
            return False

    def start(self):
        if self._thread is not None:
            raise RuntimeError('collector is single-use')
        self._thread = Thread(target=self._run, daemon=True, name='watchtower-metadata')
        self._thread.start()
        return self

    def _run(self):
        while not self._stop.is_set():
            try:
                source = self.queue.get(timeout=0.05)
            except Empty:
                continue
            try:
                result = self.sources[source].sample()
                with self._lock:
                    if len(self.results) == self.results.maxlen:
                        self.dropped += 1
                    self.results.append(result)
            finally:
                self.queue.task_done()

    def drain(self, limit=32):
        if type(limit) is not int or not 1 <= limit <= 4096:
            raise ValueError('bounded drain required')
        with self._lock:
            cutoff = time.time() - self.retention_seconds
            while self.results and self.results[0]['observed_at'] < cutoff:
                self.results.popleft()
            return [self.results.popleft() for _ in range(min(limit, len(self.results)))]

    def health(self):
        with self._lock:
            return {'status': 'UNKNOWN' if self.dropped or self._thread is None or not self._thread.is_alive() else 'OK',
                    'dropped': self.dropped, 'pending': self.queue.qsize(), 'retained': len(self.results)}

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.2)
