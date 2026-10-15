"""Durable, bounded local goal supervision for trusted host-owned subloops.

The host supplies bounded handlers and independent receipt validators. This is
not a process sandbox or a production authorization service. An interrupted
handler is never silently replayed: its external effects may be indeterminate.
"""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import math
import os
from pathlib import Path
import time


class GoalOrchestrator:
    def __init__(self, directory, *, handlers, validators, clock=time.time):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'goal.json'
        self.handlers, self.validators, self.clock = handlers, validators, clock

    @contextmanager
    def _lock(self):
        with (self.directory / 'goal.lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def _save(self, state):
        encoded = json.dumps(state, allow_nan=False, sort_keys=True, indent=2)
        if len(encoded.encode()) > 2_000_000:
            raise ValueError('goal checkpoint budget exceeded')
        temporary = self.directory / 'goal.json.tmp'
        with temporary.open('w') as stream:
            stream.write(encoded + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def inspect(self):
        with self._lock():
            return json.loads(self.path.read_text())

    def create(self, *, goal_id, target, tasks, deadline_seconds=300):
        """Parents are monitoring groups; leaves have handlers and validators.

        Dependencies refer to earlier tasks, making cycles impossible. All
        leaves are required. A host must include an independent final target
        verifier; a successful command exit alone is not sufficient evidence.
        """
        tasks = deepcopy(tasks)
        if not all(type(x) is str and 0 < len(x) <= 512 for x in (goal_id, target)):
            raise ValueError('bounded goal ID and measurable target required')
        if type(deadline_seconds) not in (int, float) or not math.isfinite(deadline_seconds) or not 1 <= deadline_seconds <= 3600:
            raise ValueError('bounded deadline required')
        if not 1 <= len(tasks) <= 100:
            raise ValueError('one to 100 subloops required')
        seen, parents = set(), set()
        for task in tasks:
            if set(task) - {'id', 'parent', 'depends_on', 'handler', 'max_attempts'}:
                raise ValueError('unknown task fields')
            name = task.get('id')
            if type(name) is not str or not 0 < len(name) <= 128 or name in seen:
                raise ValueError('unique bounded task ID required')
            dependencies = task.setdefault('depends_on', [])
            if type(dependencies) is not list or any(d not in seen for d in dependencies):
                raise ValueError('dependencies must refer to earlier tasks')
            parent = task.get('parent')
            if parent is not None:
                if parent not in seen or parent in dependencies:
                    raise ValueError('parent must precede child and cannot be its dependency')
                parents.add(parent)
            handler = task.get('handler')
            if handler is not None and (handler not in self.handlers or handler not in self.validators):
                raise ValueError('registered handler and independent validator required')
            attempts = task.setdefault('max_attempts', 1)
            if type(attempts) is not int or not 1 <= attempts <= 3:
                raise ValueError('one to three attempts required')
            task.update(status='pending', attempts=0, receipt=None, error=None)
            seen.add(name)
        for task in tasks:
            if (task['id'] in parents) == (task.get('handler') is not None):
                raise ValueError('groups need children; only leaves have handlers')
            if task['id'] in parents and task['depends_on']:
                raise ValueError('put dependencies on leaves, not monitoring groups')
        # A child may not depend on a group containing itself, even indirectly.
        edges = {t['id']: list(t['depends_on']) + [c['id'] for c in tasks if c.get('parent') == t['id']] for t in tasks}
        visited = set()
        def visit(name, ancestors):
            if name in ancestors:
                raise ValueError('dependency/group cycle')
            if name in visited:
                return
            for child in edges[name]:
                visit(child, ancestors | {name})
            visited.add(name)
        for name in edges:
            visit(name, set())
        with self._lock():
            if self.path.exists():
                raise FileExistsError('goal already exists; inspect or resume it')
            state = dict(schema='nerve-goal-v1', goal_id=goal_id, target=target,
                         deadline=self.clock()+deadline_seconds, status='active',
                         tasks=tasks, ticks=0, production_authorized=False)
            self._save(state)
        return state

    def cancel(self):
        with self._lock():
            state = json.loads(self.path.read_text())
            if state['status'] == 'active':
                state['status'] = 'cancelled'
                self._save(state)
            return state

    def tick(self):
        """Run at most one bounded leaf; checkpoint before and after execution.

        Callbacks must enforce their own I/O timeouts. The lock prevents two
        supervisors executing the same leaf. Expired results cannot succeed.
        """
        with self._lock():
            state = json.loads(self.path.read_text())
            if state['status'] != 'active':
                return state
            state['ticks'] += 1
            tasks = state['tasks']
            by_id = {t['id']: t for t in tasks}
            interrupted = [t for t in tasks if t['status'] == 'running']
            if interrupted:
                for task in interrupted:
                    task.update(status='blocked', error='interrupted_execution_requires_reconciliation')
                state['status'] = 'blocked'
            elif self.clock() >= state['deadline']:
                state['status'] = 'budget_exhausted'
            else:
                for task in reversed(tasks):
                    children = [t for t in tasks if t.get('parent') == task['id']]
                    if children:
                        task['status'] = 'succeeded' if all(c['status'] == 'succeeded' for c in children) else 'pending'
                ready = next((t for t in tasks if t.get('handler') and t['status'] == 'pending'
                              and all(by_id[d]['status'] == 'succeeded' for d in t['depends_on'])), None)
                if ready is not None:
                    ready.update(status='running', attempts=ready['attempts']+1)
                    self._save(state)
                    try:
                        # Only dependency receipts are supplied; no implicit shared task state.
                        context = {d: deepcopy(by_id[d]['receipt']) for d in ready['depends_on']}
                        receipt = self.handlers[ready['handler']](context)
                        encoded = json.dumps(receipt, allow_nan=False)
                        if len(encoded.encode()) > 100_000:
                            raise ValueError('receipt too large')
                        accepted = self.validators[ready['handler']](deepcopy(receipt))
                        if type(accepted) is not bool:
                            raise ValueError('validator must return boolean')
                        ready['receipt'] = receipt
                        if self.clock() >= state['deadline']:
                            ready.update(status='blocked', error='deadline_exhausted')
                            state['status'] = 'budget_exhausted'
                        elif accepted:
                            ready.update(status='succeeded', error=None)
                        else:
                            ready.update(status='pending' if ready['attempts'] < ready['max_attempts'] else 'blocked', error='target_not_verified')
                    except Exception as error:
                        # Do not persist exception bodies: they may contain host secrets.
                        ready.update(status='blocked', error=type(error).__name__)
                for task in reversed(tasks):
                    children = [t for t in tasks if t.get('parent') == task['id']]
                    if children:
                        task['status'] = ('succeeded' if all(c['status'] == 'succeeded' for c in children)
                                          else 'blocked' if any(c['status'] == 'blocked' for c in children) else 'pending')
                if state['status'] == 'active':
                    if all(t['status'] == 'succeeded' for t in tasks):
                        state['status'] = 'complete'
                    elif any(t['status'] == 'blocked' for t in tasks) or ready is None:
                        state['status'] = 'blocked'
            self._save(state)
            return state

    def run(self, *, max_ticks=100):
        if type(max_ticks) is not int or not 1 <= max_ticks <= 300:
            raise ValueError('bounded tick budget required')
        for _ in range(max_ticks):
            state = self.tick()
            if state['status'] != 'active':
                break
        return state
