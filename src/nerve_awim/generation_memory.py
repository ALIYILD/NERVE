"""Bounded generation handoffs over the existing trusted memory authority.

Host-only public/synthetic notes; not workspace backup or patient-data storage.
Approval permits advisory inheritance only, never tool/deployment authority.
SQLite integrity is not protection against a writer controlling the host DB.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import sqlite3
import time

from .memory_v18 import TrustedMemoryLedger, _id, _PLACEHOLDER


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return sha256(_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class GenerationScope:
    profile: str
    context: str
    task_family: str
    task_contract: str
    runtime_revision: str
    model_revision: str
    template_revision: str
    evaluator_revision: str

    def __post_init__(self):
        for key, value in asdict(self).items():
            _id(value, key)

    @property
    def ledger_context(self):
        return 'generation-' + _digest(asdict(self))


def _note(value):
    if (type(value) is not dict or set(value) != {'category', 'text', 'data_class'}
            or value['category'] not in ('observation', 'failed_attempt', 'hypothesis')
            or value['data_class'] not in ('public', 'synthetic')
            or type(value['text']) is not str or not 1 <= len(value['text']) <= 1024
            or _PLACEHOLDER.search(value['text'])):
        raise ValueError('bounded public or synthetic non-secret note required')
    return value


class GenerationMemory:
    """An adjunct to TrustedMemoryLedger, with no capability issuer of its own."""
    def __init__(self, ledger):
        if not isinstance(ledger, TrustedMemoryLedger):
            raise TypeError('existing trusted ledger required')
        self.ledger = ledger
        with sqlite3.connect(ledger.path) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS generation_snapshots (
                    id TEXT PRIMARY KEY, tenant TEXT NOT NULL, agent TEXT NOT NULL,
                    payload TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS generation_no_update BEFORE UPDATE ON generation_snapshots
                    BEGIN SELECT RAISE(ABORT,'immutable generation'); END;
                CREATE TRIGGER IF NOT EXISTS generation_no_delete BEFORE DELETE ON generation_snapshots
                    BEGIN SELECT RAISE(ABORT,'immutable generation'); END;
            ''')

    def _scope(self, actor, scope, permission):
        self.ledger.authority.require(actor, permission)
        if type(scope) is not GenerationScope or scope.profile != actor.agent_id:
            raise PermissionError('exact actor profile and generation scope required')
        # Revalidate even a forged frozen dataclass.
        GenerationScope(**asdict(scope))

    def propose_note(self, actor, scope, *, text, category, data_class, source_id, valid_until):
        self._scope(actor, scope, 'propose')
        content = _json(_note(dict(text=text, category=category, data_class=data_class)))
        return self.ledger.propose(actor, context=scope.ledger_context, content=content,
                                   source_id=source_id, kind='episodic', valid_until=valid_until)

    def _record(self, db, actor, scope, memory_id, now):
        _id(memory_id, 'memory ID')
        record = self.ledger._get(db, actor, memory_id)
        if (record.status != 'approved' or record.evaluator_id != scope.evaluator_revision
                or record.context != scope.ledger_context or record.valid_until is None
                or record.valid_until <= now or len(record.content.encode()) > 4096
                or sha256(record.content.encode()).hexdigest() != record.source_sha256):
            raise ValueError('memory approval, expiry, integrity or scope invalid')
        _id(record.evaluator_id, 'evaluator')
        note = _note(json.loads(record.content))
        if _json(note) != record.content:
            raise ValueError('noncanonical note')
        return dict(memory_id=memory_id, source_id=record.source_id,
                    content_digest=record.source_sha256, evaluator_id=record.evaluator_id,
                    valid_until=record.valid_until, note=note)

    def _load(self, db, actor, snapshot_id, scope, now, visited):
        if type(snapshot_id) is not str or len(snapshot_id) != 64 or any(c not in '0123456789abcdef' for c in snapshot_id):
            raise ValueError('invalid snapshot id')
        if snapshot_id in visited or len(visited) >= 32:
            raise ValueError('cyclic or excessive generation lineage')
        visited.add(snapshot_id)
        row = db.execute('SELECT payload FROM generation_snapshots WHERE id=? AND tenant=? AND agent=?',
                         (snapshot_id, actor.tenant_id, actor.agent_id)).fetchone()
        if not row:
            raise LookupError('snapshot not found in actor scope')
        raw = row[0]
        if len(raw.encode()) > 16384:
            raise ValueError('oversized snapshot')
        value = json.loads(raw)
        if (set(value) != {'version', 'tenant', 'agent', 'scope', 'parent', 'notes', 'valid_until', 'authorization_granted'}
                or _json(value) != raw or _digest(value) != snapshot_id
                or type(value['version']) is not int or value['version'] != 1
                or value['tenant'] != actor.tenant_id or value['agent'] != actor.agent_id
                or value['scope'] != asdict(scope) or value['authorization_granted'] is not False
                or type(value['valid_until']) is not int or value['valid_until'] <= now
                or type(value['notes']) is not list or not 1 <= len(value['notes']) <= 8):
            raise ValueError('invalid snapshot binding')
        if value['parent'] is not None:
            self._load(db, actor, value['parent'], scope, now, visited)
        seen_ids, seen_content, seen_sources = set(), set(), set()
        for note in value['notes']:
            record = self._record(db, actor, scope, note['memory_id'], now)
            if (record != note or record['memory_id'] in seen_ids or record['content_digest'] in seen_content
                    or record['source_id'] in seen_sources):
                raise ValueError('changed or duplicate inherited evidence')
            seen_ids.add(record['memory_id']); seen_content.add(record['content_digest']); seen_sources.add(record['source_id'])
        return value

    def freeze(self, actor, scope, *, memory_ids, valid_until, parent_id=None):
        self._scope(actor, scope, 'read')
        now = int(time.time())
        if (type(valid_until) is not int or not now < valid_until <= now + 30*86400
                or type(memory_ids) not in (list, tuple) or not 1 <= len(memory_ids) <= 8):
            raise ValueError('bounded notes and future expiry within 30 days required')
        with sqlite3.connect(self.ledger.path) as db:
            db.execute('BEGIN IMMEDIATE')
            if parent_id is not None:
                parent = self._load(db, actor, parent_id, scope, now, set())
                valid_until = min(valid_until, parent['valid_until'])
            notes = [self._record(db, actor, scope, mid, now) for mid in memory_ids]
            for field in ('memory_id', 'source_id', 'content_digest'):
                if len({note[field] for note in notes}) != len(notes):
                    raise ValueError('duplicate inherited evidence')
            valid_until = min(valid_until, *(note['valid_until'] for note in notes))
            value = dict(version=1, tenant=actor.tenant_id, agent=actor.agent_id, scope=asdict(scope),
                         parent=parent_id, notes=notes, valid_until=valid_until, authorization_granted=False)
            raw = _json(value)
            if len(raw.encode()) > 16384:
                raise ValueError('snapshot byte budget exceeded')
            snapshot_id = _digest(value)
            db.execute('INSERT OR IGNORE INTO generation_snapshots VALUES(?,?,?,?)',
                       (snapshot_id, actor.tenant_id, actor.agent_id, raw))
            self._load(db, actor, snapshot_id, scope, now, set())
        return snapshot_id

    def handoff(self, actor, snapshot_id, scope):
        """Revalidate at each fresh session; returned data is never authorization."""
        self._scope(actor, scope, 'read')
        with sqlite3.connect(self.ledger.path) as db:
            db.execute('BEGIN')
            return self._load(db, actor, snapshot_id, scope, int(time.time()), set())

    def metadata(self, actor, snapshot_id, scope):
        """Provider-free inspection without disclosing note text or source IDs."""
        value = self.handoff(actor, snapshot_id, scope)
        return dict(snapshot_id=snapshot_id, parent_id=value['parent'], scope=value['scope'],
                    note_count=len(value['notes']), valid_until=value['valid_until'],
                    authorization_granted=False)
