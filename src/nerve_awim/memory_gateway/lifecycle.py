"""Opt-in persistent SQLite admission limits for a gateway-owned ledger.

Triggers execute in the existing ledger writer's transaction. Installing this
policy also constrains legacy writers sharing this database. Policy changes are
offline host operations, never agent or API actions.
"""
import sqlite3


QUOTA_ERROR = 'gateway_scope_quota_exceeded'


def install_quota(path, limit):
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('scope quota must be 1..10000 records')
    with sqlite3.connect(path) as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('''CREATE TABLE IF NOT EXISTS memory_gateway_limits_v1 (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            max_records INTEGER NOT NULL CHECK(max_records BETWEEN 1 AND 10000))''')
        current = con.execute('SELECT max_records FROM memory_gateway_limits_v1 WHERE singleton=1').fetchone()
        if current is not None and current[0] != limit:
            raise ValueError('configured quota differs from persisted host policy')
        con.execute('INSERT OR IGNORE INTO memory_gateway_limits_v1 VALUES (1,?)', (limit,))
        con.execute('''CREATE TRIGGER IF NOT EXISTS memory_gateway_quota_insert_v1
            BEFORE INSERT ON trusted_memory_v18
            BEGIN
              SELECT CASE WHEN (SELECT COUNT(*) FROM trusted_memory_v18
                WHERE tenant_id=NEW.tenant_id AND agent_id=NEW.agent_id AND context=NEW.context)
                >= COALESCE((SELECT max_records FROM memory_gateway_limits_v1 WHERE singleton=1),0)
              THEN RAISE(ABORT,'gateway_scope_quota_exceeded') END;
            END''')
        con.execute('''CREATE TRIGGER IF NOT EXISTS memory_gateway_quota_move_v1
            BEFORE UPDATE OF tenant_id,agent_id,context ON trusted_memory_v18
            WHEN OLD.tenant_id != NEW.tenant_id OR OLD.agent_id != NEW.agent_id OR OLD.context != NEW.context
            BEGIN
              SELECT CASE WHEN (SELECT COUNT(*) FROM trusted_memory_v18
                WHERE tenant_id=NEW.tenant_id AND agent_id=NEW.agent_id AND context=NEW.context
                AND memory_id != OLD.memory_id)
                >= COALESCE((SELECT max_records FROM memory_gateway_limits_v1 WHERE singleton=1),0)
              THEN RAISE(ABORT,'gateway_scope_quota_exceeded') END;
            END''')
