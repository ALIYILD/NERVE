"""Explicit additive migration and scoped, ordered prediction/outcome receipts.

The database and this host are trusted. Capabilities reuse NERVE LearningAuthority;
this is not a remote authentication service or storage for clinical observations.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import threading
from .contracts import canonical, digest, identifier, observation, REVISION, IntegrityError
from ..governed_learning_v20 import LearningAuthority

SCHEMA = (
 'CREATE TABLE wm_schema(version INTEGER PRIMARY KEY)',
 'INSERT INTO wm_schema VALUES(1)',
 '''CREATE TABLE wm_episodes(scope TEXT, episode TEXT, source TEXT, family TEXT,
 split TEXT, revision TEXT, initial TEXT, PRIMARY KEY(scope,episode), UNIQUE(scope,source))''',
 '''CREATE TABLE wm_transitions(scope TEXT, id TEXT, episode TEXT, sequence INTEGER,
 action TEXT, previous TEXT, prediction TEXT, model TEXT, predicted_at REAL,
 outcome TEXT, completion INTEGER, status TEXT, observed_at REAL, cost REAL,
 PRIMARY KEY(scope,id), UNIQUE(scope,episode,sequence))''',
 '''CREATE TABLE wm_artifacts(scope TEXT, id TEXT, body TEXT, state TEXT,
 PRIMARY KEY(scope,id))''',
 '''CREATE TABLE wm_runs(scope TEXT, id TEXT, phase TEXT, budget INTEGER,
 owner TEXT, fence INTEGER, lease_until REAL, body TEXT, PRIMARY KEY(scope,id))''',
 '''CREATE TABLE wm_final(scope TEXT, source TEXT, run TEXT, model TEXT, consumed INTEGER,
 PRIMARY KEY(scope,source))''',
 '''CREATE TABLE wm_events(id INTEGER PRIMARY KEY, scope TEXT, run TEXT, kind TEXT, body TEXT)''',
 '''CREATE TABLE wm_releases(scope TEXT PRIMARY KEY, generation INTEGER, active TEXT,
 previous TEXT, body TEXT)''',
)


RECEIPTS = """CREATE TABLE wm_final_reports(scope TEXT, run TEXT, model TEXT,
 evidence_hash TEXT, report TEXT, report_hash TEXT, PRIMARY KEY(scope,run))"""


def migrate(path):
    """Explicit transaction; does not change legacy tables or their schema version."""
    with sqlite3.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='wm_schema'").fetchone()
        if exists:
            if db.execute('SELECT version FROM wm_schema').fetchall() not in ([(1,)], [(2,)]):
                raise IntegrityError('unsupported world-model migration version')
        else:
            for statement in SCHEMA:
                db.execute(statement)
        if db.execute("SELECT version FROM wm_schema").fetchall() == [(1,)]:
            db.execute(RECEIPTS)
            db.execute("UPDATE wm_schema SET version=2")


class Ledger:
    def __init__(self, path, authority):
        if type(authority) is not LearningAuthority:
            raise TypeError('existing NERVE authority required')
        self.path, self.authority = str(Path(path)), authority
        self._local = threading.local()
        with self.db() as db:
            if [tuple(r) for r in db.execute('SELECT version FROM wm_schema')] != [(2,)]:
                raise IntegrityError('explicit migration required')

    @contextmanager
    def db(self):
        existing = getattr(self._local, 'db', None)
        if existing is not None:
            yield existing
            return
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            self._local.db = db
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            self._local.db = None
            db.close()

    def scope(self, actor, *roles):
        self.authority.require(actor, *roles)
        return canonical([actor.tenant, actor.agent])

    def episode(self, actor, *, episode, source, family, split, initial, revision=REVISION):
        scope = self.scope(actor, 'trainer', 'evaluator')
        for value in (episode, source, family):
            identifier(value)
        observation(initial)
        if initial is None or revision != REVISION or split not in ('train','selection','regression','final'):
            raise ValueError('compatible observed episode required')
        if split != 'train':
            self.authority.require(actor, 'evaluator')
        row = (scope, episode, source, family, split, revision, canonical(initial))
        with self.db() as db:
            existing = db.execute('SELECT * FROM wm_episodes WHERE scope=? AND episode=?', (scope,episode)).fetchone()
            if existing:
                if tuple(existing) != row:
                    raise IntegrityError('episode identity conflict')
                return episode
            db.execute('INSERT INTO wm_episodes VALUES(?,?,?,?,?,?,?)', row)
        return episode

    def reserve(self, actor, *, transition_id, episode, sequence, action, previous, prediction, model=None):
        scope = self.scope(actor, 'trainer', 'evaluator', 'runtime')
        for value in (transition_id, episode, action):
            identifier(value)
        if model is not None:
            identifier(model)
        if type(sequence) is not int or sequence < 0:
            raise ValueError('nonnegative sequence required')
        observation(previous)
        observation(prediction)
        with self.db() as db:
            ep = db.execute('SELECT * FROM wm_episodes WHERE scope=? AND episode=?', (scope,episode)).fetchone()
            if ep is None:
                raise LookupError('episode outside scope')
            if ep['split'] != 'train':
                self.authority.require(actor, 'evaluator')
            old = db.execute('SELECT * FROM wm_transitions WHERE scope=? AND id=?', (scope,transition_id)).fetchone()
            intended = (episode,sequence,action,canonical(previous),canonical(prediction),model)
            if old:
                if tuple(old[k] for k in ('episode','sequence','action','previous','prediction','model')) != intended:
                    raise IntegrityError('idempotency conflict')
                return transition_id
            rows = db.execute('SELECT * FROM wm_transitions WHERE scope=? AND episode=? ORDER BY sequence', (scope,episode)).fetchall()
            if len(rows) != sequence or (rows and rows[-1]['status'] == 'reserved'):
                raise ValueError('ordered completed prefix required')
            expected = rows[-1]['outcome'] if rows else ep['initial']
            if canonical(previous) != expected or previous is None:
                raise ValueError('previous observation must match observed prefix')
            db.execute('INSERT INTO wm_transitions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (scope,transition_id,episode,sequence,action,canonical(previous),canonical(prediction),model,
                 time.time(),None,None,'reserved',None,0))
        return transition_id

    def complete(self, actor, transition_id, *, outcome, completion, status='observed', cost=0):
        scope = self.scope(actor, 'trainer', 'evaluator', 'runtime')
        identifier(transition_id)
        observation(outcome)
        if completion is not None and type(completion) is not bool:
            raise ValueError('explicit completion boolean or unknown required')
        canonical(cost)
        if type(cost) not in (int,float) or cost < 0 or status not in ('observed','error','missing'):
            raise ValueError('invalid outcome accounting')
        if (status == 'observed') != (outcome is not None) or (outcome is None and completion is not None):
            raise ValueError('missing/error outcomes cannot invent observations or completion')
        values = (canonical(outcome),completion,status,cost)
        with self.db() as db:
            row = db.execute('SELECT t.*,e.split FROM wm_transitions t JOIN wm_episodes e '
                'ON t.scope=e.scope AND t.episode=e.episode WHERE t.scope=? AND t.id=?', (scope,transition_id)).fetchone()
            if row is None:
                raise LookupError('prediction must be reserved before outcome')
            if row['split'] != 'train':
                self.authority.require(actor, 'evaluator')
            if row['status'] != 'reserved':
                if tuple(row[k] for k in ('outcome','completion','status','cost')) != values:
                    raise IntegrityError('immutable outcome conflict')
                return
            db.execute('UPDATE wm_transitions SET outcome=?,completion=?,status=?,cost=?,observed_at=? WHERE scope=? AND id=?',
                       (*values,time.time(),scope,transition_id))

    def episodes(self, actor, split='train'):
        scope = self.scope(actor, 'trainer','evaluator','auditor','runtime')
        if split != 'train':
            self.authority.require(actor, 'evaluator')
        with self.db() as db:
            result = []
            for ep in db.execute('SELECT * FROM wm_episodes WHERE scope=? AND split=? ORDER BY episode',(scope,split)):
                item = dict(ep)
                item['initial'] = json.loads(item['initial'])
                item['transitions'] = []
                for row in db.execute('SELECT * FROM wm_transitions WHERE scope=? AND episode=? ORDER BY sequence',(scope,ep['episode'])):
                    row = dict(row)
                    for key in ('previous','prediction','outcome'):
                        row[key] = json.loads(row[key]) if row[key] is not None else None
                    row['completion'] = None if row['completion'] is None else bool(row['completion'])
                    item['transitions'].append(row)
                result.append(item)
            return result
