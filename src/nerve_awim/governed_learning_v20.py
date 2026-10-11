"""Opt-in local outcome learning and governed routing releases.

Trusted host supplies pure/read-only registered handlers and an independent
judge. Local object capabilities are NOT remote authentication, a sandbox or
clinical deployment authority. Never expose authority issuance to agents.
Only aggregate outcomes, identifiers and input hashes are stored, not payloads.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import uuid

from .agent_learning_v12 import AgentTask, RegisteredStrategy

ROLES = frozenset(('trainer', 'evaluator', 'operator', 'runtime', 'auditor'))
MIN_TRAIN = 3
MIN_HOLDOUT = 5
MIN_ACCURACY = .8


def _id(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,96}', value):
        raise ValueError('bounded identifier required')
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class LearningActor:
    tenant: str
    agent: str
    role: str
    _nonce: str = field(repr=False)


class LearningAuthority:
    """Host-only capability issuer; real applications must authenticate first."""
    def __init__(self):
        self._issued = {}

    def issue(self, tenant, agent, role):
        if role not in ROLES:
            raise ValueError('unknown learning role')
        actor = LearningActor(_id(tenant), _id(agent), role, uuid.uuid4().hex)
        self._issued[actor._nonce] = actor
        return actor

    def require(self, actor, *roles):
        if (type(actor) is not LearningActor or
                self._issued.get(actor._nonce) is not actor or actor.role not in roles):
            raise PermissionError('host-issued scoped capability required')

    def revoke(self, actor):
        self.require(actor, *ROLES)
        del self._issued[actor._nonce]


class GovernedLearning:
    """Learn routes from executed tasks, freeze, evaluate once, approve, rollback.

    The host must bump contract_revision whenever handler/evaluator semantics
    change. A scope cannot silently resume under a different contract. SQL and
    host code are trusted; local audit rows are not tamper-proof signatures.
    """
    def __init__(self, path, *, authority, strategies, judge, contract_revision,
                 baseline_routes):
        if type(authority) is not LearningAuthority or not callable(judge):
            raise TypeError('trusted authority and independent judge required')
        self.authority, self.judge = authority, judge
        self.contract = _id(contract_revision)
        self.path = str(Path(path))
        registry = {}
        for strategy in strategies:
            if type(strategy) is not RegisteredStrategy:
                raise TypeError('registered strategies required')
            key = (_id(strategy.context), _id(strategy.strategy_id))
            if key in registry:
                raise ValueError('duplicate strategy')
            registry[key] = strategy.handler
        contexts = {key[0] for key in registry}
        if (not 1 <= len(contexts) <= 16 or
                any(sum(c == context for c, _ in registry) > 8 for context in contexts)):
            raise ValueError('registry exceeds research budget')
        self._registry = registry
        self._baseline = self._routes(baseline_routes)
        with self._db() as con:
            con.executescript('''
              CREATE TABLE IF NOT EXISTS gl_state (
                tenant TEXT, agent TEXT, contract TEXT, active TEXT, generation INTEGER,
                PRIMARY KEY (tenant, agent));
              CREATE TABLE IF NOT EXISTS gl_tasks (
                tenant TEXT, agent TEXT, task_id TEXT, payload_hash TEXT,
                context TEXT, split TEXT, claim TEXT,
                PRIMARY KEY (tenant, agent, task_id),
                UNIQUE (tenant, agent, payload_hash));
              CREATE TABLE IF NOT EXISTS gl_holdout_reservations (
                tenant TEXT, agent TEXT, task_id TEXT, payload_hash TEXT,
                PRIMARY KEY (tenant, agent, task_id),
                UNIQUE (tenant, agent, payload_hash));
              CREATE TABLE IF NOT EXISTS gl_outcomes (
                tenant TEXT, agent TEXT, task_id TEXT, strategy TEXT,
                success INTEGER, handler_error INTEGER,
                PRIMARY KEY (tenant, agent, task_id, strategy));
              CREATE TABLE IF NOT EXISTS gl_candidates (
                id TEXT PRIMARY KEY, tenant TEXT, agent TEXT, contract TEXT,
                base_release TEXT, base_generation INTEGER, routes TEXT,
                training TEXT, status TEXT, evaluation TEXT);
              CREATE TABLE IF NOT EXISTS gl_releases (
                id TEXT PRIMARY KEY, tenant TEXT, agent TEXT, contract TEXT,
                routes TEXT, candidate TEXT);
              CREATE TABLE IF NOT EXISTS gl_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT,
                agent TEXT, event TEXT, details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')

    @contextmanager
    def _db(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    def _routes(self, routes):
        contexts = {c for c, _ in self._registry}
        if (type(routes) is not dict or set(routes) != contexts or
                any((c, s) not in self._registry for c, s in routes.items())):
            raise ValueError('one registered strategy per context required')
        return dict(routes)

    def _scope(self, actor, *roles):
        self.authority.require(actor, *roles)
        return (actor.tenant, actor.agent)

    def _state(self, con, scope):
        row = con.execute('SELECT * FROM gl_state WHERE tenant=? AND agent=?', scope).fetchone()
        if row is None:
            raise LookupError('operator must bootstrap this scope')
        if row['contract'] != self.contract:
            raise ValueError('contract revision changed; use a new reviewed deployment namespace')
        return row

    def _release(self, con, scope, release_id):
        row = con.execute('SELECT * FROM gl_releases WHERE id=? AND tenant=? AND agent=?',
                          (release_id, *scope)).fetchone()
        if row is None or row['contract'] != self.contract:
            raise LookupError('release not found in current scope/contract')
        return self._routes(json.loads(row['routes']))

    def _candidate(self, con, scope, candidate_id):
        row = con.execute('SELECT * FROM gl_candidates WHERE id=? AND tenant=? AND agent=?',
                          (candidate_id, *scope)).fetchone()
        if row is None or row['contract'] != self.contract:
            raise LookupError('candidate not found in current scope/contract')
        return row

    @staticmethod
    def _event(con, scope, event, details):
        con.execute('INSERT INTO gl_events(tenant,agent,event,details) VALUES(?,?,?,?)',
                    (*scope, event, _json(details)))

    def bootstrap(self, actor):
        scope = self._scope(actor, 'operator')
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute('SELECT 1 FROM gl_state WHERE tenant=? AND agent=?', scope).fetchone():
                raise ValueError('scope already initialised')
            release = uuid.uuid4().hex
            con.execute('INSERT INTO gl_releases VALUES(?,?,?,?,?,?)',
                        (release, *scope, self.contract, _json(self._baseline), None))
            con.execute('INSERT INTO gl_state VALUES(?,?,?,?,?)',
                        (*scope, self.contract, release, 0))
            self._event(con, scope, 'bootstrap', {'release': release, 'generation': 0})
        return self.status(actor)

    def _task(self, task):
        if type(task) is not AgentTask or task.context not in self._baseline:
            raise ValueError('typed task in a registered context required')
        _id(task.task_id)
        # Canonical JSON also rules out arbitrary executable Python objects.
        encoded = _json(task.payload)
        if len(encoded.encode()) > 16384:
            raise ValueError('task payload exceeds research limit')
        clean = json.loads(encoded)
        return AgentTask(task.task_id, task.context, clean), sha256(encoded.encode()).hexdigest()

    @staticmethod
    def _claim(con, scope, task, digest, split, claim):
        if split != 'holdout' and con.execute('''SELECT 1 FROM gl_holdout_reservations
                WHERE tenant=? AND agent=? AND (task_id=? OR payload_hash=?)''',
                (*scope, task.task_id, digest)).fetchone():
            raise ValueError('task reserved for independently held-out evaluation')
        try:
            con.execute('INSERT INTO gl_tasks VALUES(?,?,?,?,?,?,?)',
                        (*scope, task.task_id, digest, task.context, split, claim))
        except sqlite3.IntegrityError:
            raise ValueError('task ID or exact payload already reserved/consumed in this scope') from None

    def _attempt(self, task, strategy):
        # Isolate mutable input objects between handlers and the evaluator.
        original = deepcopy(task)
        try:
            value = self._registry[(task.context, strategy)](deepcopy(task.payload))
        except Exception:
            return False, True
        accepted = self.judge(original, value)
        if type(accepted) is not bool:
            raise ValueError('independent judge must return a boolean')
        return accepted, False

    def learn_from_task(self, actor, task):
        """Execute registered read-only alternatives; persist judged training only.

        No caller-supplied rewards are accepted. An evaluator failure records no
        training outcomes. A failed task stays consumed to prevent replay bias.
        """
        scope = self._scope(actor, 'trainer')
        task, digest = self._task(task)
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            self._state(con, scope)
            self._claim(con, scope, task, digest, 'train', 'training')
        return self._learn_claimed_task(scope, task)

    def _learn_claimed_task(self, scope, task):
        """Host-internal execution after an atomic, one-use training claim."""
        try:
            outcomes = [(strategy, *self._attempt(task, strategy))
                        for context, strategy in sorted(self._registry)
                        if context == task.context]
        except Exception:
            with self._db() as con:
                self._event(con, scope, 'training_evaluator_failed', {'task_id': task.task_id})
            raise RuntimeError('independent training evaluation failed; no rewards stored') from None
        with self._db() as con:
            con.executemany('INSERT INTO gl_outcomes VALUES(?,?,?,?,?,?)',
                            [(*scope, task.task_id, strategy, int(ok), int(error))
                             for strategy, ok, error in outcomes])
            self._event(con, scope, 'training_recorded', {'task_id': task.task_id,
                                                        'strategies': len(outcomes)})
        return {'task_id': task.task_id, 'evaluated_strategies': len(outcomes)}

    def freeze_candidate(self, actor):
        scope = self._scope(actor, 'trainer')
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            state = self._state(con, scope)
            current = self._release(con, scope, state['active'])
            rows = con.execute('''SELECT t.context, o.strategy, COUNT(*) AS n,
                SUM(o.success) AS hits FROM gl_outcomes o JOIN gl_tasks t
                ON o.tenant=t.tenant AND o.agent=t.agent AND o.task_id=t.task_id
                WHERE o.tenant=? AND o.agent=? AND t.split='train'
                GROUP BY t.context,o.strategy''', scope).fetchall()
            scores = {(r['context'], r['strategy']): (r['hits'], r['n']) for r in rows}
            if any(scores.get(key, (0, 0))[1] < MIN_TRAIN for key in self._registry):
                raise ValueError('at least three judged training tasks per registered strategy required')
            routes, evidence = {}, {}
            for context in sorted(current):
                choices = [s for c, s in self._registry if c == context]
                # Alternatives must have been evaluated on the same complete task batches.
                if len({scores[(context, s)][1] for s in choices}) != 1:
                    raise ValueError('unmatched training denominators')
                routes[context] = min(choices, key=lambda s: (
                    -scores[(context, s)][0] / scores[(context, s)][1],
                    s != current[context], s))
                evidence[context] = {s: {'hits': scores[(context, s)][0],
                                         'tasks': scores[(context, s)][1]} for s in choices}
            candidate = uuid.uuid4().hex
            con.execute('INSERT INTO gl_candidates VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (candidate, *scope, self.contract, state['active'], state['generation'],
                         _json(routes), _json(evidence), 'frozen', None))
            self._event(con, scope, 'candidate_frozen', {'candidate': candidate,
                                                       'base_generation': state['generation']})
        return candidate

    def evaluate_candidate(self, actor, candidate_id, tasks):
        """One-use, paired holdout. All contexts need five fresh independent cases.

        Exact-ID/content overlap is prevented; semantic independence and source
        selection remain the trusted evaluator's responsibility. Results cannot
        train the candidate or be retried after inspecting a failed evaluation.
        """
        scope = self._scope(actor, 'evaluator')
        tasks = tuple(tasks)
        if not 1 <= len(tasks) <= 128:
            raise ValueError('between one and 128 held-out tasks required')
        prepared = [self._task(t) for t in tasks]
        if any(sum(t.context == c for t, _ in prepared) < MIN_HOLDOUT for c in self._baseline):
            raise ValueError('five held-out cases per context required')
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            state = self._state(con, scope)
            candidate = self._candidate(con, scope, candidate_id)
            if candidate['status'] != 'frozen' or candidate['base_generation'] != state['generation']:
                raise ValueError('fresh frozen candidate against current release required')
            routes = self._routes(json.loads(candidate['routes']))
            baseline = self._release(con, scope, candidate['base_release'])
            for task, digest in prepared:
                self._claim(con, scope, task, digest, 'holdout', candidate_id)
            con.execute("UPDATE gl_candidates SET status='evaluating' WHERE id=?", (candidate_id,))
        # Both arms receive the same cases and exactly one strategy invocation.
        metrics = {c: {'tasks': 0, 'baseline_hits': 0, 'candidate_hits': 0,
                       'baseline_errors': 0, 'candidate_errors': 0} for c in routes}
        try:
            for task, _ in prepared:
                row = metrics[task.context]
                old_ok, old_error = self._attempt(task, baseline[task.context])
                new_ok, new_error = self._attempt(task, routes[task.context])
                row['tasks'] += 1
                row['baseline_hits'] += old_ok
                row['candidate_hits'] += new_ok
                row['baseline_errors'] += old_error
                row['candidate_errors'] += new_error
            eligible = all(r['candidate_hits'] >= r['baseline_hits'] and
                           r['candidate_hits'] / r['tasks'] >= MIN_ACCURACY and
                           r['candidate_errors'] <= r['baseline_errors'] for r in metrics.values())
            improved = sum(r['candidate_hits'] - r['baseline_hits'] for r in metrics.values()) > 0
            status = 'passed' if eligible and improved and routes != baseline else 'rejected'
            evidence = {'status': status, 'contexts': metrics,
                        'gate': 'paired-v20-min5-accuracy0.8-no-context-regression-strict-total-gain'}
        except Exception:
            with self._db() as con:
                con.execute("UPDATE gl_candidates SET status='failed' WHERE id=?", (candidate_id,))
                self._event(con, scope, 'holdout_evaluator_failed', {'candidate': candidate_id})
            raise RuntimeError('independent holdout evaluation failed; candidate cannot be promoted') from None
        with self._db() as con:
            con.execute('UPDATE gl_candidates SET status=?,evaluation=? WHERE id=?',
                        (status, _json(evidence), candidate_id))
            self._event(con, scope, 'holdout_evaluated', {'candidate': candidate_id, 'status': status})
        return evidence

    @staticmethod
    def _approval_input(expected_generation, reason):
        if type(expected_generation) is not int or expected_generation < 0:
            raise ValueError('explicit generation required')
        # Store a bounded review reference, not free text that may contain secrets.
        return _id(reason)

    def activate(self, actor, candidate_id, *, expected_generation, reason):
        scope = self._scope(actor, 'operator')
        self._approval_input(expected_generation, reason)
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            state = self._state(con, scope)
            candidate = self._candidate(con, scope, candidate_id)
            if (state['generation'] != expected_generation or
                    candidate['base_generation'] != expected_generation or
                    candidate['base_release'] != state['active']):
                raise ValueError('stale approval; re-evaluate against the current release')
            if candidate['status'] != 'passed':
                raise ValueError('independent holdout gate has not passed')
            routes = self._routes(json.loads(candidate['routes']))
            release = uuid.uuid4().hex
            con.execute('INSERT INTO gl_releases VALUES(?,?,?,?,?,?)',
                        (release, *scope, self.contract, _json(routes), candidate_id))
            con.execute('UPDATE gl_state SET active=?,generation=generation+1 WHERE tenant=? AND agent=?',
                        (release, *scope))
            self._event(con, scope, 'activated', {'release': release, 'previous': state['active'],
                                                'candidate': candidate_id, 'review': reason,
                                                'generation': expected_generation + 1})
        return self.status(actor)

    def rollback(self, actor, release_id, *, expected_generation, reason):
        scope = self._scope(actor, 'operator')
        self._approval_input(expected_generation, reason)
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            state = self._state(con, scope)
            self._release(con, scope, release_id)
            if state['generation'] != expected_generation or state['active'] == release_id:
                raise ValueError('stale generation or already-active rollback target')
            con.execute('UPDATE gl_state SET active=?,generation=generation+1 WHERE tenant=? AND agent=?',
                        (release_id, *scope))
            self._event(con, scope, 'rolled_back', {'release': release_id, 'previous': state['active'],
                                                  'review': reason, 'generation': expected_generation + 1})
        return self.status(actor)

    def execute(self, actor, task):
        """Use one immutable approved route snapshot; never writes training rewards."""
        scope = self._scope(actor, 'runtime')
        task, _ = self._task(task)
        with self._db() as con:
            state = self._state(con, scope)
            routes = self._release(con, scope, state['active'])
        strategy = routes[task.context]
        value = self._registry[(task.context, strategy)](deepcopy(task.payload))
        return {'value': value, 'strategy': strategy, 'release': state['active'],
                'generation': state['generation'], 'feedback_written': False}

    def status(self, actor):
        scope = self._scope(actor, *ROLES)
        with self._db() as con:
            state = self._state(con, scope)
            routes = self._release(con, scope, state['active'])
            counts = con.execute('SELECT split,COUNT(*) n FROM gl_tasks WHERE tenant=? AND agent=? GROUP BY split',
                                 scope).fetchall()
            return {'active_release': state['active'], 'generation': state['generation'],
                    'routes': routes, 'task_counts': {r['split']: r['n'] for r in counts},
                    'contract_revision': self.contract}

    def candidate_report(self, actor, candidate_id):
        scope = self._scope(actor, 'auditor', 'evaluator', 'operator')
        with self._db() as con:
            self._state(con, scope)
            row = self._candidate(con, scope, candidate_id)
            return {'candidate': candidate_id, 'status': row['status'],
                    'routes': json.loads(row['routes']), 'training': json.loads(row['training']),
                    'evaluation': json.loads(row['evaluation']) if row['evaluation'] else None}

    def audit(self, actor):
        scope = self._scope(actor, 'auditor', 'operator')
        with self._db() as con:
            self._state(con, scope)
            rows = con.execute('SELECT sequence,event,details FROM gl_events WHERE tenant=? AND agent=? ORDER BY sequence',
                               scope).fetchall()
            return [{'sequence': r['sequence'], 'event': r['event'], 'details': json.loads(r['details'])}
                    for r in rows]
