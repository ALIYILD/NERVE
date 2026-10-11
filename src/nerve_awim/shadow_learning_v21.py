"""Explicit, bounded, in-process shadow collection for trusted read-only tools.

execute preserves the active runtime result/exception. drain performs expensive
judging and alternative executions separately. This is not a worker sandbox or
a durable payload queue: pending raw tasks live only in host memory.
"""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter


@dataclass
class _Observation:
    task: object
    result: object
    handler_error: bool
    latency_ms: float


class ShadowLearning:
    """Host adapter. Never freezes, evaluates holdouts, activates or rolls back.

    runtime and trainer must belong to the same authenticated host scope.
    Alternatives must be pure/read-only and bounded by the host. Call drain
    outside the request path. One adapter instance has one host owner/thread.
    """
    def __init__(self, engine, *, runtime, trainer, capacity=32):
        engine.authority.require(runtime, 'runtime')
        engine.authority.require(trainer, 'trainer')
        if (runtime.tenant, runtime.agent) != (trainer.tenant, trainer.agent):
            raise PermissionError('runtime and trainer scope must match')
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError('capacity must be between one and 128')
        self.engine, self.runtime, self.trainer = engine, runtime, trainer
        self.capacity, self._pending = capacity, deque()
        self.dropped = 0
        with engine._db() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS gl_shadow (
                tenant TEXT, agent TEXT, task_id TEXT, payload_hash TEXT,
                context TEXT, release TEXT, generation INTEGER, strategy TEXT,
                success INTEGER, handler_error INTEGER, latency_ms REAL,
                cost_usd REAL, training_status TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tenant, agent, task_id))''')

    @property
    def pending(self):
        return len(self._pending)

    def execute(self, task, *, expected_release=None, expected_generation=None):
        # Invalid inputs/credentials fail before dispatch and are not outcomes.
        scope = self.engine._scope(self.runtime, 'runtime')
        clean, _ = self.engine._task(task)
        with self.engine._db() as con:
            con.execute('BEGIN')
            state = self.engine._state(con, scope)
            if ((expected_release is not None and state['active'] != expected_release) or
                    (expected_generation is not None and state['generation'] != expected_generation)):
                raise ValueError('host deployment changed; review binding before serving')
            routes = self.engine._release(con, scope, state['active'])
        strategy = routes[clean.context]
        result = {'strategy': strategy, 'release': state['active'],
                  'generation': state['generation'], 'feedback_written': False}
        started = perf_counter()
        failed = True
        try:
            result['value'] = self.engine._registry[(clean.context, strategy)](deepcopy(clean.payload))
            failed = False
            return result
        finally:
            elapsed = (perf_counter() - started) * 1000
            # Instrumentation cannot replace a successful value or original error.
            try:
                if len(self._pending) >= self.capacity:
                    self.dropped += 1
                else:
                    self._pending.append(_Observation(clean, deepcopy(result), failed, elapsed))
            except Exception:
                self.dropped += 1

    def drain(self, *, limit=32):
        """Judge actual outputs; then independently run matched training arms.

        Primary telemetry and replay training are explicitly distinct. A failed
        judge produces no reward. Duplicate/held-out tasks cannot enter training.
        Tasks are dropped from memory after one attempt, including failures.
        Costs are unknown (NULL), never fabricated as zero. Host/provider cost
        attestation is not connected in this local-tools adapter.
        """
        scope = self.engine._scope(self.trainer, 'trainer')
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError('drain limit must be between one and 128')
        counts = {'recorded': 0, 'rejected': 0, 'failed': 0}
        for _ in range(min(limit, len(self._pending))):
            item = self._pending.popleft()
            try:
                task, digest = self.engine._task(item.task)
                # Reserve before any judge sees the task: holdout/train races and
                # failed-judge retries cannot leak examples or bias selection.
                with self.engine._db() as con:
                    con.execute('BEGIN IMMEDIATE')
                    self.engine._state(con, scope)
                    self.engine._claim(con, scope, task, digest, 'train', 'shadow-training')
                    con.execute('INSERT INTO gl_shadow VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',
                        (*scope, task.task_id, digest, task.context, item.result['release'],
                         item.result['generation'], item.result['strategy'], None,
                         int(item.handler_error), item.latency_ms, None, 'pending'))
                success, training_status = None, 'failed'
                try:
                    success = False if item.handler_error else self.engine.judge(
                        deepcopy(task), deepcopy(item.result['value']))
                    if type(success) is not bool:
                        success = None
                        raise ValueError('independent judge must return a boolean')
                    self.engine._learn_claimed_task(scope, task)
                    training_status = 'recorded'
                except Exception:
                    pass
                with self.engine._db() as con:
                    con.execute('''UPDATE gl_shadow SET success=?, training_status=?
                        WHERE tenant=? AND agent=? AND task_id=?''',
                        (int(success) if success is not None else None,
                         training_status, *scope, task.task_id))
                counts[training_status] += 1
            except ValueError:
                counts['rejected'] += 1
            except Exception:
                counts['failed'] += 1
        return {**counts, 'pending': self.pending, 'dropped': self.dropped}

    def report(self, actor):
        scope = self.engine._scope(actor, 'auditor', 'operator', 'evaluator')
        with self.engine._db() as con:
            self.engine._state(con, scope)
            rows = con.execute('''SELECT context, release, generation, strategy,
                COUNT(*) tasks, SUM(COALESCE(success,0)) hits,
                SUM(success IS NULL) unjudged, SUM(handler_error) errors,
                SUM(training_status='failed') training_failures,
                SUM(training_status='pending') interrupted_or_pending,
                MIN(created_at) first_observed_at, MAX(created_at) last_observed_at,
                AVG(latency_ms) mean_latency_ms, MAX(latency_ms) max_latency_ms
                FROM gl_shadow WHERE tenant=? AND agent=?
                GROUP BY context,release,generation,strategy ORDER BY context,generation''', scope).fetchall()
        return {'mode': 'shadow', 'actual_active_outcomes': [dict(row) for row in rows],
                'cost_usd': None, 'cost_status': 'provider billing not connected',
                'pending_in_this_process': self.pending, 'dropped_in_this_process': self.dropped,
                'training': 'separate matched re-executions; primary output is never replaced',
                'release_changed_by_adapter': False}
