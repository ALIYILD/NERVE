"""Opt-in bounded canaries for trusted, pure/read-only registered handlers.

The host operator approves a passed candidate. A stable hash samples requests;
quality/handler/latency failures stop candidate traffic and serve the active
baseline. Success only enables another operator review, never auto-promotion.
"""
from copy import deepcopy
from hashlib import sha256
import json
import math
from time import perf_counter
import uuid

from .governed_learning_v20 import _json
from .promotion_monitor_v24 import PromotionMonitor


class CanaryLearning:
    def __init__(self, engine):
        if len(engine._baseline) != 1:
            raise ValueError('this bounded pilot supports one task context per scope')
        self.engine = engine
        self.monitor = PromotionMonitor(engine)
        with engine._db() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS gl_canaries (
                    id TEXT PRIMARY KEY, tenant TEXT, agent TEXT, candidate TEXT,
                    base_release TEXT, base_generation INTEGER, release TEXT,
                    percent INTEGER, required_successes INTEGER, latency_ms REAL,
                    phase TEXT, reason TEXT);
                CREATE TABLE IF NOT EXISTS gl_canary_outcomes (
                    canary TEXT, task_id TEXT, status TEXT, latency_ms REAL,
                    PRIMARY KEY(canary,task_id));
            ''')

    def _row(self, con, scope, canary):
        self.engine._state(con, scope)
        row = con.execute('SELECT * FROM gl_canaries WHERE id=? AND tenant=? AND agent=?',
                          (canary, *scope)).fetchone()
        if row is None:
            raise LookupError('canary not found in this scope')
        return row

    def start(self, actor, candidate_id, *, expected_generation, reason,
              percent=5, required_successes=20, latency_ms=1000):
        scope = self.engine._scope(actor, 'operator')
        self.engine._approval_input(expected_generation, reason)
        if type(percent) is not int or not 1 <= percent <= 25:
            raise ValueError('canary sampling must be 1-25 percent')
        if type(required_successes) is not int or not 5 <= required_successes <= 1000:
            raise ValueError('five to 1000 successful fresh tasks required')
        if (type(latency_ms) not in (int, float) or not math.isfinite(latency_ms)
                or not 0 < latency_ms <= 60000):
            raise ValueError('finite latency budget between zero and 60000 ms required')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            state = self.engine._state(con, scope)
            candidate = self.engine._candidate(con, scope, candidate_id)
            if (candidate['status'] != 'passed' or candidate['base_generation'] != expected_generation
                    or state['generation'] != expected_generation or candidate['base_release'] != state['active']):
                raise ValueError('passed candidate against current approved generation required')
            if con.execute('''SELECT 1 FROM gl_canaries WHERE tenant=? AND agent=?
                    AND phase IN ('active','ready')''', scope).fetchone():
                raise ValueError('finish or stop the existing canary first')
            # Failed candidates cannot be repeatedly canaried until luck passes.
            if con.execute('SELECT 1 FROM gl_canaries WHERE tenant=? AND agent=? AND candidate=?',
                           (*scope, candidate_id)).fetchone():
                raise ValueError('candidate already had a canary; require a new reviewed candidate')
            canary, release = uuid.uuid4().hex, uuid.uuid4().hex
            self.engine._routes(json.loads(candidate['routes']))
            con.execute('INSERT INTO gl_canaries VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (canary, *scope, candidate_id, state['active'], expected_generation,
                         release, percent, required_successes, latency_ms, 'active', reason))
            self.engine._event(con, scope, 'canary_started', {'canary': canary,
                'candidate': candidate_id, 'review': reason, 'percent': percent,
                'required_successes': required_successes, 'latency_ms': latency_ms})
        return canary

    def _stop(self, con, scope, canary, reason):
        con.execute("UPDATE gl_canaries SET phase='stopped',reason=? WHERE id=?", (reason, canary))
        self.engine._event(con, scope, 'canary_stopped', {'canary': canary, 'reason': reason})

    def stop(self, actor, canary, *, reason):
        scope = self.engine._scope(actor, 'operator')
        self.engine._approval_input(0, reason)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, canary)
            if row['phase'] not in ('active', 'ready'):
                raise ValueError('canary is not active or awaiting review')
            self._stop(con, scope, canary, reason)

    def execute(self, actor, canary, task):
        scope = self.engine._scope(actor, 'runtime')
        with self.engine._db() as con:
            self._row(con, scope, canary)
            monitored = con.execute('SELECT 1 FROM gl_promotion_monitors WHERE canary=? AND tenant=? AND agent=?',
                                    (canary, *scope)).fetchone()
        if monitored:
            return self.monitor.execute(actor, canary, task)
        task, digest = self.engine._task(task)
        selected, reason = False, 'baseline_sample'
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, canary)
            state = self.engine._state(con, scope)
            if row['phase'] not in ('active', 'ready'):
                reason = row['phase']
            elif state['generation'] != row['base_generation'] or state['active'] != row['base_release']:
                self._stop(con, scope, canary, 'active_release_changed')
                reason = 'active_release_changed'
            elif row['phase'] == 'ready':
                reason = 'awaiting_operator_review'
            elif con.execute("SELECT 1 FROM gl_canary_outcomes WHERE canary=? AND status='pending'",
                             (canary,)).fetchone():
                # One in-flight attempt: bounds exposure and fails closed after a crash.
                reason = 'pending_attempt'
            elif int(sha256((canary + ':' + digest).encode()).hexdigest(), 16) % 100 < row['percent']:
                try:
                    self.engine._claim(con, scope, task, digest, 'canary', canary)
                except ValueError:
                    reason = 'not_fresh_or_reserved'
                else:
                    con.execute('INSERT INTO gl_canary_outcomes VALUES(?,?,?,NULL)',
                                (canary, task.task_id, 'pending'))
                    selected = True
                    candidate = self.engine._candidate(con, scope, row['candidate'])
                    routes = self.engine._routes(json.loads(candidate['routes']))
        if selected:
            started = perf_counter()
            status, value = 'handler_error', None
            try:
                value = self.engine._registry[(task.context, routes[task.context])](deepcopy(task.payload))
                status = 'judge_error'
                accepted = self.engine.judge(deepcopy(task), deepcopy(value))
                if type(accepted) is bool:
                    status = 'passed' if accepted else 'quality_failure'
            except Exception:
                pass
            elapsed = (perf_counter() - started) * 1000
            if status == 'passed' and elapsed > row['latency_ms']:
                status = 'latency_failure'
            with self.engine._db() as con:
                con.execute('BEGIN IMMEDIATE')
                latest = self._row(con, scope, canary)
                state = self.engine._state(con, scope)
                con.execute('UPDATE gl_canary_outcomes SET status=?,latency_ms=? WHERE canary=? AND task_id=?',
                            (status, elapsed, canary, task.task_id))
                if latest['phase'] != 'active':
                    reason = 'operator_stopped'
                elif state['generation'] != row['base_generation'] or state['active'] != row['base_release']:
                    self._stop(con, scope, canary, 'active_release_changed')
                    reason = 'active_release_changed'
                elif status != 'passed':
                    self._stop(con, scope, canary, status)
                    reason = status
                else:
                    hits = con.execute("SELECT COUNT(*) FROM gl_canary_outcomes WHERE canary=? AND status='passed'",
                                       (canary,)).fetchone()[0]
                    if hits >= row['required_successes']:
                        con.execute("UPDATE gl_canaries SET phase='ready' WHERE id=?", (canary,))
                        self.engine._event(con, scope, 'canary_ready_for_review', {'canary': canary})
                    return {'value': value, 'strategy': routes[task.context], 'release': row['release'],
                            'generation': row['base_generation'], 'feedback_written': False,
                            'canary': {'id': canary, 'used': True, 'reason': 'judged_pass'}}
        # Promotion can occur while this request is using the trial path.
        # Decide monitoring versus an immutable active snapshot in one read transaction.
        with self.engine._db() as con:
            con.execute('BEGIN')
            monitored = con.execute('SELECT 1 FROM gl_promotion_monitors WHERE canary=? AND tenant=? AND agent=?',
                                    (canary, *scope)).fetchone()
            state = self.engine._state(con, scope)
            active_routes = self.engine._release(con, scope, state['active'])
        if monitored:
            return self.monitor.execute(actor, canary, task)
        strategy = active_routes[task.context]
        value = self.engine._registry[(task.context, strategy)](deepcopy(task.payload))
        result = {'value': value, 'strategy': strategy, 'release': state['active'],
                  'generation': state['generation'], 'feedback_written': False}
        result['canary'] = {'id': canary, 'used': False, 'reason': reason}
        return result

    def report(self, actor, canary):
        scope = self.engine._scope(actor, 'operator', 'auditor', 'evaluator')
        with self.engine._db() as con:
            row = self._row(con, scope, canary)
            state = self.engine._state(con, scope)
            counts = con.execute('''SELECT status,COUNT(*) n FROM gl_canary_outcomes
                WHERE canary=? GROUP BY status''', (canary,)).fetchall()
            latency = con.execute('''SELECT AVG(latency_ms) mean_ms, MAX(latency_ms) max_ms
                FROM gl_canary_outcomes WHERE canary=?''', (canary,)).fetchone()
        return {'canary': canary, 'phase': row['phase'], 'reason': row['reason'],
                'candidate': row['candidate'], 'percent': row['percent'],
                'required_successes': row['required_successes'], 'latency_budget_ms': row['latency_ms'],
                'outcomes': {r['status']: r['n'] for r in counts},
                'latency': dict(latency),
                'base_generation': row['base_generation'], 'active_generation': state['generation'],
                'base_release': row['base_release'], 'active_release': state['active'],
                'cost_usd': None, 'automatic_promotion': False}

    def promote(self, actor, canary, *, expected_generation, reason, monitor_latency_ms=None):
        scope = self.engine._scope(actor, 'operator')
        self.engine._approval_input(expected_generation, reason)
        if monitor_latency_ms is not None:
            self.monitor.validate_budget(monitor_latency_ms)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, canary)
            state = self.engine._state(con, scope)
            if (row['phase'] != 'ready' or state['generation'] != expected_generation
                    or row['base_generation'] != expected_generation or state['active'] != row['base_release']):
                raise ValueError('completed canary and current explicit generation required')
            candidate = self.engine._candidate(con, scope, row['candidate'])
            if candidate['status'] != 'passed':
                raise ValueError('candidate no longer eligible')
            routes = self.engine._routes(json.loads(candidate['routes']))
            con.execute('INSERT INTO gl_releases VALUES(?,?,?,?,?,?)',
                        (row['release'], *scope, self.engine.contract, _json(routes), row['candidate']))
            con.execute('UPDATE gl_state SET active=?,generation=generation+1 WHERE tenant=? AND agent=?',
                        (row['release'], *scope))
            con.execute("UPDATE gl_canaries SET phase='promoted',reason=? WHERE id=?", (reason, canary))
            if monitor_latency_ms is not None:
                self.monitor.arm(con, scope, row, expected_generation + 1, monitor_latency_ms, reason)
            self.engine._event(con, scope, 'canary_promoted', {'canary': canary,
                'release': row['release'], 'previous': row['base_release'],
                'generation': expected_generation + 1, 'review': reason})
        return self.engine.status(actor)
