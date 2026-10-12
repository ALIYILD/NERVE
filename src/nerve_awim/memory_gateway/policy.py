"""Durable exact-scope revocation and bounded payload-free lifecycle audit.

Opt-in research policy in the same SQLite ledger. No key management or physical
erasure claim. Tombstones are deliberately retained when evidence is deleted.
"""
from pathlib import Path
from hashlib import sha256
import json
import sqlite3
import time

from .observability import build_audit_event

REVOKED_ERROR = 'gateway_scope_revoked'


def install_utility_cleanup(con):
    """Protect future legacy deletes only when both optional tables exist.

    Historical orphan rows cannot safely be attributed to a deleted context;
    they need a separately reviewed retention migration, not cross-scope purge.
    """
    tables = {row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('memory_utility','memory_scope_revocations_v1')")}
    if tables != {'memory_utility', 'memory_scope_revocations_v1'}:
        return
    con.execute('''CREATE TRIGGER IF NOT EXISTS memory_utility_delete_v1
        AFTER DELETE ON trusted_memory_v18
        BEGIN DELETE FROM memory_utility WHERE tenant=OLD.tenant_id
            AND agent=OLD.agent_id AND memory=OLD.memory_id; END''')


def _scope_values(scope):
    return scope.tenant_id, scope.agent_id, scope.context


def _scope_digest(scope):
    return sha256(json.dumps(_scope_values(scope), separators=(',', ':')).encode()).hexdigest()


class DurableMemoryPolicy:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('''CREATE TABLE IF NOT EXISTS memory_scope_revocations_v1 (
                tenant TEXT NOT NULL, agent TEXT NOT NULL, context TEXT NOT NULL,
                revoked_at INTEGER NOT NULL, PRIMARY KEY(tenant,agent,context))''')
            con.execute('''CREATE TABLE IF NOT EXISTS memory_lifecycle_audit_v1 (
                sequence INTEGER PRIMARY KEY, scope_digest TEXT NOT NULL,
                trace_id TEXT NOT NULL, event TEXT NOT NULL, status TEXT NOT NULL,
                created_at INTEGER NOT NULL)''')
            install_utility_cleanup(con)
            con.execute('''CREATE TRIGGER IF NOT EXISTS memory_scope_revoked_insert_v1
                BEFORE INSERT ON trusted_memory_v18
                WHEN EXISTS(SELECT 1 FROM memory_scope_revocations_v1
                    WHERE tenant=NEW.tenant_id AND agent=NEW.agent_id AND context=NEW.context)
                BEGIN SELECT RAISE(ABORT,'gateway_scope_revoked'); END''')
            con.execute('''CREATE TRIGGER IF NOT EXISTS memory_scope_revoked_update_v1
                BEFORE UPDATE OF status,tenant_id,agent_id,context ON trusted_memory_v18
                WHEN NEW.status='approved' AND EXISTS(SELECT 1 FROM memory_scope_revocations_v1
                    WHERE tenant=NEW.tenant_id AND agent=NEW.agent_id AND context=NEW.context)
                BEGIN SELECT RAISE(ABORT,'gateway_scope_revoked'); END''')

    def _read(self):
        return sqlite3.connect(Path(self.path).resolve().as_uri() + '?mode=ro', uri=True, timeout=0.1)

    def is_revoked(self, scope):
        with self._read() as con:
            return con.execute('''SELECT 1 FROM memory_scope_revocations_v1
                WHERE tenant=? AND agent=? AND context=?''', _scope_values(scope)).fetchone() is not None

    @staticmethod
    def _audit(con, scope, event, status):
        record = build_audit_event(event, status)
        con.execute('INSERT INTO memory_lifecycle_audit_v1 VALUES(NULL,?,?,?,?,?)',
                    (_scope_digest(scope), record['trace_id'], record['event'], record['status'], record['created_at']))
        # Bounded local audit window. Tombstones are stored separately and never
        # evicted by audit retention. External audit retention is host-owned.
        con.execute('''DELETE FROM memory_lifecycle_audit_v1 WHERE sequence NOT IN
            (SELECT sequence FROM memory_lifecycle_audit_v1 ORDER BY sequence DESC LIMIT 10000)''')
        return record['trace_id']

    def audit(self, scope, event, status):
        with sqlite3.connect(self.path) as con:
            return self._audit(con, scope, event, status)

    def revoke(self, scope, evaluator_id):
        with sqlite3.connect(self.path) as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('INSERT OR IGNORE INTO memory_scope_revocations_v1 VALUES(?,?,?,?)',
                        (*_scope_values(scope), int(time.time())))
            count = con.execute('''UPDATE trusted_memory_v18 SET status='revoked',evaluator_id=?
                WHERE tenant_id=? AND agent_id=? AND context=? AND status='approved' ''',
                (evaluator_id, *_scope_values(scope))).rowcount
            trace = self._audit(con, scope, 'scope_revoked', 'success')
        return count, trace

    def revoke_source(self, scope, memory_id, evaluator_id):
        """Commit source revocation and its evidence in one write transaction."""
        with sqlite3.connect(self.path) as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('''SELECT status FROM trusted_memory_v18
                WHERE tenant_id=? AND agent_id=? AND context=? AND memory_id=?''',
                (*_scope_values(scope), memory_id)).fetchone()
            if row is None:
                raise LookupError('memory not found in authorised scope')
            if row[0] != 'approved':
                raise ValueError('only approved memories can be revoked')
            con.execute('''UPDATE trusted_memory_v18 SET status='revoked',evaluator_id=?
                WHERE tenant_id=? AND agent_id=? AND context=? AND memory_id=?''',
                (evaluator_id, *_scope_values(scope), memory_id))
            return self._audit(con, scope, 'source_revoked', 'success')

    @staticmethod
    def _delete_utility(con, scope, memory_id=None):
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_utility'").fetchone():
            return
        if memory_id is None:
            con.execute('''DELETE FROM memory_utility WHERE tenant=? AND agent=? AND memory IN
                (SELECT memory_id FROM trusted_memory_v18 WHERE tenant_id=? AND agent_id=? AND context=?)''',
                (scope.tenant_id, scope.agent_id, *_scope_values(scope)))
        else:
            con.execute('DELETE FROM memory_utility WHERE tenant=? AND agent=? AND memory=?',
                        (scope.tenant_id, scope.agent_id, memory_id))

    def delete(self, scope, memory_id=None):
        with sqlite3.connect(self.path) as con:
            con.execute('BEGIN IMMEDIATE')
            if memory_id is None:
                con.execute('INSERT OR IGNORE INTO memory_scope_revocations_v1 VALUES(?,?,?,?)',
                            (*_scope_values(scope), int(time.time())))
            self._delete_utility(con, scope, memory_id)
            query = 'DELETE FROM trusted_memory_v18 WHERE tenant_id=? AND agent_id=? AND context=?'
            params = _scope_values(scope)
            if memory_id is not None:
                query += ' AND memory_id=?'
                params += (memory_id,)
            count = con.execute(query, params).rowcount
            trace = self._audit(con, scope, 'scope_deleted' if memory_id is None else 'source_deleted', 'success')
        return count, trace

    def events(self, scope, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('bounded audit limit required')
        with self._read() as con:
            rows = con.execute('''SELECT trace_id,event,status,created_at FROM memory_lifecycle_audit_v1
                WHERE scope_digest=? ORDER BY sequence DESC LIMIT ?''', (_scope_digest(scope), limit)).fetchall()
        return [dict(zip(('trace_id', 'event', 'status', 'created_at'), row)) for row in rows]
