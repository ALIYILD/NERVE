"""Bounded independent notification outbox; no provider errors or secrets logged."""
import json
import math
import fcntl
from contextlib import contextmanager
import os
import queue
import sqlite3
import stat
import threading
import time
import urllib.request
from pathlib import Path


def protected_secret(path, allowed_uids):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in allowed_uids or info.st_mode & 0o077:
            raise ValueError('credential file protection invalid')
        if info.st_size > 8192:
            raise ValueError('credential file too large')
        return os.read(fd, 8192).decode().strip()
    finally:
        os.close(fd)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class HTTPSDelivery:
    """Explicitly provisioned HTTPS destination; redirects disabled."""
    def __init__(self, *, channel, endpoint, secret_path, allowed_uids, recipient, sender=None):
        from urllib.parse import urlsplit
        parsed = urlsplit(endpoint)
        if channel not in ('telegram', 'email') or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('invalid HTTPS provider configuration')
        if channel == 'telegram' and endpoint != 'https://api.telegram.org':
            raise ValueError('Telegram endpoint must be pinned')
        self.channel, self.endpoint, self.recipient, self.sender = channel, endpoint, recipient, sender
        self.secret_path, self.allowed_uids = secret_path, frozenset(allowed_uids)

    def __call__(self, alert):
        try:
            return self._send(alert)
        except Exception:
            # urllib errors can include Telegram's token-bearing request URL.
            raise ValueError('notification provider delivery unconfirmed') from None

    def _send(self, alert):
        token = protected_secret(self.secret_path, self.allowed_uids)
        message = json.dumps(alert, sort_keys=True)
        headers = {'Content-Type': 'application/json'}
        if self.channel == 'telegram':
            import re
            if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
                raise ValueError('invalid credential')
            url = self.endpoint + '/bot' + token + '/sendMessage'
            body = {'chat_id': self.recipient, 'text': message}
        else:
            url = self.endpoint
            headers['Authorization'] = 'Bearer ' + token
            body = {'from': self.sender, 'to': [self.recipient], 'subject': 'NERVE Guardian incident', 'text': message}
        request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method='POST')
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=5) as response:
            if response.status < 200 or response.status >= 300:
                raise ValueError('delivery failed')
            result = response.read(16385)
            if len(result) > 16384:
                raise ValueError('delivery unconfirmed')
            payload = json.loads(result)
            if not isinstance(payload, dict):
                raise ValueError('delivery unconfirmed')
            if self.channel == 'telegram' and payload.get('ok') is not True:
                raise ValueError('delivery unconfirmed')
            if self.channel == 'email' and (not isinstance(payload.get('id'), str) or not payload['id']):
                raise ValueError('delivery unconfirmed')


class Notifier:
    """enqueue never waits on storage/network. Queue overflow is explicit health loss.

    Dispatcher commits durable outbox before network delivery. Abrupt process death
    can lose uncommitted queue entries; incidents remain the authoritative resend source.
    Provider success means accepted, not read by the owner.
    """
    FIELDS = ('tenant', 'incident_id', 'event', 'severity', 'timestamp', 'containment_status', 'verification_status', 'evidence_reference', 'dashboard_url', 'next_action_code', 'timestamp_utc', 'affected_service')

    def __init__(self, database, adapters, *, capacity=256, max_attempts=3, rate_seconds=1):
        if not 1 <= capacity <= 4096 or not 1 <= max_attempts <= 5 or rate_seconds < 0:
            raise ValueError('invalid notification bounds')
        if not adapters or set(adapters) - {'telegram', 'email'}:
            raise ValueError('unknown notification channel')
        self.database, self.adapters = str(database), dict(adapters)
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.pending = queue.Queue(capacity)
        self.max_attempts, self.rate = max_attempts, rate_seconds
        self.dropped = 0
        self.storage_failures = 0
        self.stop = threading.Event()
        self.closing = threading.Event()
        self.lifecycle_lock = threading.Lock()
        # Separate lock file avoids interfering with SQLite locks on macOS.
        # Resolve directory aliases; reject file aliases and shared permissions.
        # The Guardian-only directory must prohibit replacement of either inode.
        self.database = str(Path(self.database).parent.resolve() / Path(self.database).name)
        self.owner_fd = self._private_file(self.database + '.owner.lock')
        self.threads = []
        ready = threading.Event()
        def start_worker(target, *args):
            ready.wait()
            if not self.stop.is_set():
                target(*args)
        try:
            try:
                fcntl.flock(self.owner_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('notification outbox already has an active owner') from None
            os.close(self._private_file(self.database))
            with self._db() as db:
                db.execute('CREATE TABLE IF NOT EXISTS outbox (tenant TEXT, incident TEXT, event TEXT, channel TEXT, payload TEXT, attempts INTEGER DEFAULT 0, status TEXT DEFAULT "pending", next_try REAL DEFAULT 0, PRIMARY KEY(tenant,incident,event,channel))')
            workers = [threading.Thread(target=start_worker, args=(self._dispatch,), daemon=True)]
            workers += [threading.Thread(target=start_worker, args=(self._deliver, channel), daemon=True) for channel in adapters]
            for thread in workers:
                thread.start()
                self.threads.append(thread)
            ready.set()
        except BaseException:
            self.stop.set()
            ready.set()
            for thread in self.threads:
                thread.join()
            os.close(self.owner_fd)
            self.owner_fd = None
            raise

    @staticmethod
    def _private_file(path):
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise PermissionError('outbox and lock must be private regular files owned by Guardian')
            return fd
        except BaseException:
            os.close(fd)
            raise

    @contextmanager
    def _db(self):
        connection = sqlite3.connect(self.database, timeout=1)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def enqueue(self, alert):
        # Reference-only fields: never serialize arbitrary evidence or clinical text.
        safe = {key: alert[key] for key in self.FIELDS if key in alert}
        if any(not isinstance(safe.get(key), str) or not 1 <= len(safe[key]) <= 256 for key in ('tenant', 'incident_id', 'event')):
            raise ValueError('notification identifiers required')
        if any(not isinstance(value, (str, int, float, bool)) or len(str(value)) > 512 for value in safe.values()):
            raise ValueError('notification field invalid')
        with self.lifecycle_lock:
            if self.closing.is_set():
                self.dropped += 1
                return False
            try:
                self.pending.put_nowait(safe)
                return True
            except queue.Full:
                self.dropped += 1
                return False

    def _dispatch(self):
        while not self.stop.is_set():
            try:
                alert = self.pending.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                with self._db() as db:
                    for channel in self.adapters:
                        db.execute('INSERT OR IGNORE INTO outbox(tenant,incident,event,channel,payload) VALUES(?,?,?,?,?)',
                            (alert['tenant'], alert['incident_id'], alert['event'], channel, json.dumps(alert)))
            except Exception:
                self.storage_failures += 1
            finally:
                self.pending.task_done()

    def _deliver(self, channel):
        while not self.stop.wait(.05):
            try:
                with self._db() as db:
                    row = db.execute('SELECT tenant,incident,event,payload,attempts FROM outbox WHERE channel=? AND status="pending" AND next_try<=? LIMIT 1', (channel, time.time())).fetchone()
                if row is None:
                    continue
                tenant, incident, event, payload, attempts = row
                try:
                    self.adapters[channel](json.loads(payload))
                    status = 'accepted'
                except Exception:
                    status = 'failed' if attempts + 1 >= self.max_attempts else 'pending'
                with self._db() as db:
                    db.execute('UPDATE outbox SET attempts=?,status=?,next_try=? WHERE tenant=? AND incident=? AND event=? AND channel=?',
                        (attempts + 1, status, time.time() + min(60, 2 ** attempts), tenant, incident, event, channel))
                self.stop.wait(self.rate)
            except Exception:
                self.storage_failures += 1
                self.stop.wait(.2)

    def status(self, tenant):
        with self._db() as db:
            rows = db.execute('SELECT incident,event,channel,attempts,status FROM outbox WHERE tenant=? ORDER BY rowid DESC LIMIT 100', (tenant,)).fetchall()
        return [dict(zip(('incident_id', 'event', 'channel', 'attempts', 'status'), row)) for row in rows]

    def health(self):
        with self._db() as db:
            failed = db.execute('SELECT COUNT(*) FROM outbox WHERE status="failed"').fetchone()[0]
        return {'failed_deliveries': failed, 'closing': self.closing.is_set(), 'workers_alive':all(t.is_alive() for t in self.threads), 'status': 'UNKNOWN' if self.closing.is_set() or self.dropped or self.storage_failures or failed or not all(t.is_alive() for t in self.threads) else 'AVAILABLE', 'queue_dropped': self.dropped,
            'storage_failures': self.storage_failures, 'delivery_semantics': 'provider acceptance; duplicate delivery possible after crash'}

    def close(self, timeout=6):
        """Bound the entire drain/join operation, including stalled adapters.

        False means a worker or uncommitted queue entry remains. Durable pending
        deliveries resume on startup; Guardian's incident intents replay entries
        that never reached the outbox. Never claim provider delivery on shutdown.
        """
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 <= timeout <= 60:
            raise ValueError('invalid shutdown timeout')
        deadline = time.monotonic() + timeout
        with self.lifecycle_lock:
            self.closing.set()
        with self.pending.all_tasks_done:
            while self.pending.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self.threads[0].is_alive():
                    break
                self.pending.all_tasks_done.wait(min(remaining, .05))
        self.stop.set()
        for thread in self.threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        workers_stopped = not any(thread.is_alive() for thread in self.threads)
        if workers_stopped:
            with self.lifecycle_lock:
                if self.owner_fd is not None:
                    os.close(self.owner_fd)
                    self.owner_fd = None
        return not self.pending.unfinished_tasks and workers_stopped
