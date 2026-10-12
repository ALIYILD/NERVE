"""Persistent, opt-in post-promotion checks for trusted read-only handlers."""
from copy import deepcopy
import math
from time import perf_counter


class PromotionMonitor:
    def __init__(self, engine):
        self.engine = engine
        with engine._db() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS gl_promotion_monitors (
                    canary TEXT PRIMARY KEY, tenant TEXT, agent TEXT, release TEXT,
                    generation INTEGER, fallback TEXT, latency_ms REAL, phase TEXT, reason TEXT);
                CREATE TABLE IF NOT EXISTS gl_promotion_outcomes (
                    canary TEXT, task_id TEXT, status TEXT, latency_ms REAL,
                    PRIMARY KEY(canary,task_id));
            ''')

    @staticmethod
    def validate_budget(budget):
        if (type(budget) not in (int, float) or not math.isfinite(budget)
                or not 0 < budget <= 60000):
            raise ValueError('finite monitoring budget between zero and 60000 ms required')

    def arm(self, con, scope, row, generation, budget, reason):
        # Called only inside the operator's promotion transaction.
        self.validate_budget(budget)
        self.engine._release(con, scope, row['base_release'])
        con.execute('INSERT INTO gl_promotion_monitors VALUES(?,?,?,?,?,?,?,?,?)',
                    (row['id'], *scope, row['release'], generation,
                     row['base_release'], budget, 'active', reason))
        self.engine._event(con, scope, 'promotion_monitor_armed', {
            'canary': row['id'], 'release': row['release'], 'generation': generation,
            'fallback': row['base_release'], 'latency_ms': budget, 'review': reason})

    def _row(self, con, scope, canary):
        self.engine._state(con, scope)
        row = con.execute('SELECT * FROM gl_promotion_monitors WHERE canary=? AND tenant=? AND agent=?',
                          (canary, *scope)).fetchone()
        if row is None:
            raise LookupError('monitor not found in this scope')
        return row

    @staticmethod
    def _current(row, state):
        return state['active'] == row['release'] and state['generation'] == row['generation']

    def _finish(self, con, scope, row, state, reason):
        # Never overwrite a newer operator decision (including rollback/reactivation).
        phase = 'rolled_back' if self._current(row, state) else 'superseded'
        if phase == 'rolled_back':
            self.engine._release(con, scope, row['fallback'])
            con.execute('UPDATE gl_state SET active=?,generation=generation+1 WHERE tenant=? AND agent=?',
                        (row['fallback'], *scope))
        con.execute('UPDATE gl_promotion_monitors SET phase=?,reason=? WHERE canary=?',
                    (phase, reason, row['canary']))
        self.engine._event(con, scope, 'promotion_monitor_' + phase, {
            'canary': row['canary'], 'reason': reason, 'release': row['release'],
            'fallback': row['fallback'], 'observed_generation': state['generation']})

    def stop(self, actor, canary, *, expected_generation, reason):
        scope = self.engine._scope(actor, 'operator')
        self.engine._approval_input(expected_generation, reason)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, canary)
            state = self.engine._state(con, scope)
            if row['phase'] != 'active' or state['generation'] != expected_generation:
                raise ValueError('active monitor and current explicit generation required')
            self._finish(con, scope, row, state, reason)

    def execute(self, actor, canary, task, *, guard=None):
        self.engine.reject_arc_bypass(actor, task)
        scope = self.engine._scope(actor, 'runtime')
        task, digest = self.engine._task(task)
        attempt = False
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = self._row(con, scope, canary)
            state = self.engine._state(con, scope)
            if guard is not None:
                guard(con, scope, state)
            reason = row['phase']
            fallback = None
            uncertainty_denied = False
            if row['phase'] == 'active' and self._current(row, state):
                release = con.execute('SELECT candidate FROM gl_releases WHERE id=? AND tenant=? AND agent=?', (row['release'], *scope)).fetchone()
                if release and release['candidate']:
                    from .uncertainty.release import require_eligibility
                    try: require_eligibility(con, self.engine, actor, release['candidate'])
                    except (PermissionError, ValueError, LookupError):
                        self._finish(con, scope, row, state, 'uncertainty_ineligible')
                        uncertainty_denied = True
                        reason = 'uncertainty_ineligible'
            if row['phase'] == 'active' and not uncertainty_denied:
                if not self._current(row, state):
                    self._finish(con, scope, row, state, 'active_release_changed')
                    reason = 'active_release_changed'
                else:
                    # Busy/interrupted and non-fresh requests use the pinned previous
                    # release, never an unchecked promoted result.
                    fallback = self.engine._release(con, scope, row['fallback'])
                    if con.execute("SELECT 1 FROM gl_promotion_outcomes WHERE canary=? AND status='pending'",
                                   (canary,)).fetchone():
                        reason = 'pending_attempt'
                    else:
                        try:
                            self.engine._claim(con, scope, task, digest, 'monitor', canary)
                        except ValueError:
                            reason = 'not_fresh_or_reserved'
                        else:
                            routes = self.engine._release(con, scope, row['release'])
                            con.execute('INSERT INTO gl_promotion_outcomes VALUES(?,?,?,NULL)',
                                        (canary, task.task_id, 'pending'))
                            attempt = True
        if attempt:
            status, value = 'handler_error', None
            started = perf_counter()
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
                if guard is not None:
                    guard(con, scope, state)
                con.execute('UPDATE gl_promotion_outcomes SET status=?,latency_ms=? WHERE canary=? AND task_id=?',
                            (status, elapsed, canary, task.task_id))
                if latest['phase'] != 'active':
                    reason = latest['phase']
                elif not self._current(row, state):
                    self._finish(con, scope, row, state, 'active_release_changed')
                    reason = 'active_release_changed'
                elif status != 'passed':
                    self._finish(con, scope, row, state, status)
                    reason = status
                else:
                    return {'value': value, 'strategy': routes[task.context], 'release': row['release'],
                            'generation': row['generation'], 'feedback_written': False,
                            'monitor': {'id': canary, 'used': True, 'reason': 'judged_pass'}}
            fallback = None  # Automatic rollback or a newer operator decision is now authoritative.
        if fallback is not None:
            strategy = fallback[task.context]
            value = self.engine._registry[(task.context, strategy)](deepcopy(task.payload))
            result = {'value': value, 'strategy': strategy, 'release': row['fallback'],
                      'generation': row['generation'], 'feedback_written': False}
        else:
            result = self.engine.execute(actor, task, guard=guard)
        result['monitor'] = {'id': canary, 'used': False, 'reason': reason}
        return result

    def report(self, actor, canary):
        scope = self.engine._scope(actor, 'operator', 'auditor', 'evaluator')
        with self.engine._db() as con:
            row = self._row(con, scope, canary)
            state = self.engine._state(con, scope)
            outcomes = con.execute('SELECT status,COUNT(*) n FROM gl_promotion_outcomes WHERE canary=? GROUP BY status',
                                   (canary,)).fetchall()
            latency = con.execute('SELECT AVG(latency_ms) mean_ms,MAX(latency_ms) max_ms FROM gl_promotion_outcomes WHERE canary=?',
                                  (canary,)).fetchone()
        return {**dict(row), 'outcomes': {r['status']: r['n'] for r in outcomes},
                'latency': dict(latency), 'active_release': state['active'],
                'active_generation': state['generation'], 'cost_usd': None}
