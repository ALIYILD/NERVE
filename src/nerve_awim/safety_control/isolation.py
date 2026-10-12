"""Trusted-host process group supervision, not an OS sandbox.

Only processes spawned by this host object can be stopped. Deployment must
separately prevent workers from escaping their process group or changing the
controller's files/credentials. No agent-supplied PID or shell is accepted.
"""
import os
import signal
import subprocess
import threading


class WorkerSupervisor:
    def __init__(self, *, grace_seconds=1.0):
        if type(grace_seconds) not in (int, float) or not 0 < grace_seconds <= 5:
            raise ValueError('bounded shutdown grace required')
        self.grace_seconds = grace_seconds
        self._workers = {}
        self._lock = threading.RLock()
        self._closed = False

    def start(self, scope, argv, *, cwd=None, env=None):
        """Host-only launcher; never expose argv or this object to a model."""
        if type(scope) is not str or not scope or len(scope) > 192:
            raise ValueError('bounded scope required')
        if (type(argv) is not list or not argv or len(argv) > 32 or
                any(type(v) is not str or not v or len(v) > 8192 for v in argv)):
            raise ValueError('trusted bounded argv required')
        with self._lock:
            if self._closed:
                raise PermissionError('supervisor isolated; new reviewed supervisor required')
            if scope in self._workers and self._workers[scope].poll() is None:
                raise ValueError('scope already has an active worker')
            process = subprocess.Popen(argv, cwd=cwd, env=env, shell=False,
                start_new_session=True, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True)
            self._workers[scope] = process
            return process.pid

    def stop(self, scope, reason=None):
        """Callback for controller-owned scope isolation; idempotent."""
        with self._lock:
            process = self._workers.get(scope)
            if process is None:
                return {'status': 'no_registered_worker', 'isolated': False}
            if process.poll() is not None:
                return {'status': 'worker_already_exited', 'isolated': False,
                        'returncode': process.returncode}
            if os.getpgid(process.pid) != process.pid:
                raise RuntimeError('registered process lost its expected group')
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            escalated = False
            try:
                process.wait(timeout=self.grace_seconds)
            except subprocess.TimeoutExpired:
                escalated = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
            return {'status': 'terminated', 'isolated': True,
                    'forced': escalated, 'returncode': process.returncode}

    def close(self):
        with self._lock:
            self._closed = True
            for scope in tuple(self._workers):
                self.stop(scope)
