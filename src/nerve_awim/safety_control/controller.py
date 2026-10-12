"""Durable controller for host-owned tools, independent of learner decisions.

An owner stop prevents *new* dispatches. It cannot cancel an already running
callable or isolate a process: those require an external OS supervisor. Never
place this database or owner/observer secrets in a learner-writable account.
"""
from contextlib import contextmanager
import hashlib
import hmac
import json
import math
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from .contracts import SafetyDenied, bounded, canonical, model_identity, sign_owner_request


class Controller:
    def __init__(self, path, owner_secret, observer_secret, *, clock=time.time, watchdog_seconds=60, isolation_callback=None):
        for key in (owner_secret, observer_secret):
            if not isinstance(key, str) or len(key) < 32:
                raise ValueError('controller secrets require at least 32 characters')
        if hmac.compare_digest(owner_secret, observer_secret):
            raise ValueError('owner and observer credentials must differ')
        if not isinstance(watchdog_seconds, (float, int)) or not 0 < watchdog_seconds <= 3600:
            raise ValueError('invalid watchdog interval')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.owner_secret, self.observer_secret = owner_secret, observer_secret
        self.clock, self.watchdog_seconds = clock, watchdog_seconds
        self._tools, self._lock = {}, threading.RLock()
        self.isolation_callback = isolation_callback
        with self._db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS control_state (id INTEGER PRIMARY KEY CHECK(id=1), stopped INTEGER NOT NULL, epoch INTEGER NOT NULL, heartbeat REAL, owner_hash TEXT NOT NULL, observer_hash TEXT NOT NULL, watchdog REAL NOT NULL);
CREATE TABLE IF NOT EXISTS integrity_incident (id INTEGER PRIMARY KEY CHECK(id=1), active INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS runtime_credentials (digest TEXT PRIMARY KEY, scope TEXT NOT NULL, tools TEXT NOT NULL, models TEXT NOT NULL, epoch INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS owner_nonces (nonce TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL);''')
            db.execute('INSERT OR IGNORE INTO integrity_incident VALUES(1,0)')
            row = db.execute('SELECT * FROM control_state WHERE id=1').fetchone()
            if row is None:
                db.execute('INSERT INTO control_state VALUES(1,0,0,NULL,?,?,?)', (self._hash(owner_secret), self._hash(observer_secret), watchdog_seconds))
                self._event(db, 'initialized', {})
            elif (not hmac.compare_digest(row['owner_hash'], self._hash(owner_secret)) or not hmac.compare_digest(row['observer_hash'], self._hash(observer_secret)) or row['watchdog'] != watchdog_seconds):
                raise SafetyDenied('controller authority/configuration mismatch')
        if not self.verify_audit():
            with self._db() as db:
                db.execute('UPDATE control_state SET stopped=1,epoch=epoch+1 WHERE id=1')
                db.execute('UPDATE integrity_incident SET active=1 WHERE id=1')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _hash(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def _event(self, db, kind, data):
        previous = db.execute('SELECT digest FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
        previous = previous[0] if previous else '0' * 64
        payload = canonical({'kind': kind, 'time': self.clock(), 'data': data})
        digest = self._hash(previous + payload)
        cursor = db.execute('INSERT INTO audit(payload,previous,digest) VALUES(?,?,?)', (payload, previous, digest))
        return cursor.lastrowid

    def _verify(self, db):
        previous = '0' * 64
        count = 0
        for row in db.execute('SELECT * FROM audit ORDER BY seq'):
            count += 1
            if row['seq'] != count or row['previous'] != previous or row['digest'] != self._hash(previous + row['payload']):
                return False
            previous = row['digest']
        return count > 0

    def verify_audit(self):
        with self._db() as db:
            return self._verify(db)

    def _integrity(self, db):
        if not self._verify(db):
            raise SafetyDenied('audit integrity failure')

    def owner_request(self, action, payload, nonce, timestamp, signature):
        bounded(nonce, 'nonce', 128)
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not math.isfinite(timestamp) or abs(self.clock() - timestamp) > 60:
            raise SafetyDenied('expired owner request')
        if not isinstance(payload, dict) or len(canonical(payload)) > 16384:
            raise ValueError('invalid owner payload')
        expected = sign_owner_request(self.owner_secret, action, payload, nonce, timestamp)
        if not isinstance(signature, str) or not hmac.compare_digest(expected, signature):
            raise SafetyDenied('invalid owner authentication')
        with self._lock, self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            integrity_valid = self._verify(db)
            if action != 'stop' and not integrity_valid:
                raise SafetyDenied('audit integrity failure')
            try:
                db.execute('INSERT INTO owner_nonces VALUES(?)', (nonce,))
            except sqlite3.IntegrityError as exc:
                raise SafetyDenied('replayed owner request') from exc
            state = db.execute('SELECT * FROM control_state WHERE id=1').fetchone()
            if action == 'issue_runtime':
                if set(payload) != {'scope', 'tools', 'models'}:
                    raise ValueError('invalid credential fields')
                if state['stopped']:
                    raise SafetyDenied('controller stopped')
                scope = self._scope(payload['scope'])
                for name in ('tools', 'models'):
                    if not isinstance(payload[name], list) or not 1 <= len(payload[name]) <= 64 or len(set(payload[name])) != len(payload[name]):
                        raise ValueError('invalid ' + name)
                for name in payload['tools']:
                    bounded(name, 'tool', 128)
                    if name not in self._tools:
                        raise ValueError('unregistered tool')
                for model in payload['models']:
                    model_identity(model)
                token = secrets.token_urlsafe(48)
                db.execute('INSERT INTO runtime_credentials VALUES(?,?,?,?,?)', (self._hash(token), scope, canonical(payload['tools']), canonical(payload['models']), state['epoch']))
                self._event(db, 'credential_issued', {'scope': scope, 'tools': payload['tools'], 'models': payload['models'], 'epoch': state['epoch']})
                return {'credential': token, 'epoch': state['epoch']}
            if action == 'stop':
                if set(payload) != {'reason'}:
                    raise ValueError('invalid stop fields')
                bounded(payload['reason'], 'reason', 1024)
                db.execute('UPDATE control_state SET stopped=1,epoch=epoch+1 WHERE id=1')
                if not integrity_valid:
                    db.execute('UPDATE integrity_incident SET active=1 WHERE id=1')
                    self._event(db, 'integrity_incident', {'reason': 'audit verification failed during emergency stop'})
                self._event(db, 'owner_stop', payload)
            elif action == 'acknowledge_integrity_repair':
                if set(payload) != {'reason', 'review_ref'} or not state['stopped']:
                    raise SafetyDenied('integrity repair review requires stopped state')
                bounded(payload['reason'], 'reason', 1024)
                bounded(payload['review_ref'], 'review reference', 512)
                db.execute('UPDATE integrity_incident SET active=0 WHERE id=1')
                self._event(db, 'owner_integrity_repair_review', payload)
                return {'action': action, 'epoch': state['epoch'], 'stopped': True}
            elif action == 'recover':
                if db.execute('SELECT active FROM integrity_incident WHERE id=1').fetchone()[0]:
                    raise SafetyDenied('integrity incident requires independently reviewed repair')
                if set(payload) != {'reason', 'review_ref'} or not state['stopped']:
                    raise SafetyDenied('recovery requires stopped state and review')
                bounded(payload['reason'], 'reason', 1024)
                bounded(payload['review_ref'], 'review reference', 512)
                db.execute('UPDATE control_state SET stopped=0,epoch=epoch+1,heartbeat=NULL WHERE id=1')
                self._event(db, 'owner_recovery', payload)
            else:
                raise ValueError('unknown owner action')
            result = {'action': action, 'epoch': state['epoch'] + 1}
        if action == 'stop' and self.isolation_callback is not None:
            try:
                self.isolation_callback()
                isolated = True
            except Exception:
                isolated = False
            with self._lock, self._db() as db:
                self._event(db, 'isolation_completed' if isolated else 'isolation_failed', {})
            result['isolation_completed'] = isolated
        return result

    @staticmethod
    def _scope(scope):
        if not isinstance(scope, dict) or set(scope) != {'tenant', 'agent', 'context'}:
            raise ValueError('scope requires tenant, agent, context')
        for name, value in scope.items():
            bounded(value, name, 128)
        return canonical(scope)

    def _observer_auth(self, secret):
        if not isinstance(secret, str) or not hmac.compare_digest(secret, self.observer_secret):
            raise SafetyDenied('invalid observer authentication')

    def heartbeat(self, observer_secret):
        self._observer_auth(observer_secret)
        with self._lock, self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._integrity(db)
            db.execute('UPDATE control_state SET heartbeat=? WHERE id=1', (self.clock(),))
            event = self._event(db, 'observer_heartbeat', {})
        return {'event_id': event}

    def report(self, observer_secret, evidence):
        self._observer_auth(observer_secret)
        if not isinstance(evidence, dict) or set(evidence) != {'kind', 'severity', 'evidence_ref', 'detail'}:
            raise ValueError('invalid observer evidence fields')
        if evidence['kind'] not in {'tool_denial', 'model_mismatch', 'tamper', 'behavioural_anomaly', 'watchdog'} or evidence['severity'] not in {'info', 'warning', 'critical'}:
            raise ValueError('invalid observer evidence type')
        bounded(evidence['evidence_ref'], 'evidence reference', 512)
        bounded(evidence['detail'], 'detail', 2048)
        with self._lock, self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._integrity(db)
            event = self._event(db, 'observer_alert', evidence)
        return {'event_id': event, 'action': 'alert', 'automatic_stop': False}

    def register_tool(self, name, handler):
        bounded(name, 'tool', 128)
        if not callable(handler) or name in self._tools:
            raise ValueError('tool handler must be unique and callable')
        self._tools[name] = handler

    def dispatch(self, credential, scope, tool, model_digest, arguments):
        bounded(credential, 'credential', 256)
        scope_key = self._scope(scope)
        bounded(tool, 'tool', 128)
        model_identity(model_digest)
        if len(canonical(arguments)) > 16384:
            raise ValueError('invalid tool arguments')
        denied = None
        with self._lock, self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._integrity(db)
            state = db.execute('SELECT * FROM control_state WHERE id=1').fetchone()
            token = db.execute('SELECT * FROM runtime_credentials WHERE digest=?', (self._hash(credential),)).fetchone()
            if state['stopped']:
                denied = 'controller stopped'
            elif not token or token['epoch'] != state['epoch'] or token['scope'] != scope_key:
                denied = 'invalid or revoked runtime credential'
            elif tool not in json.loads(token['tools']) or tool not in self._tools:
                denied = 'tool not authorized'
            elif model_digest not in json.loads(token['models']):
                denied = 'model identity mismatch'
            elif state['heartbeat'] is None or not 0 <= self.clock() - state['heartbeat'] <= self.watchdog_seconds:
                denied = 'observer watchdog stale'
            event_id = self._event(db, 'dispatch_denied' if denied else 'dispatch_authorized', {'scope': scope, 'tool': tool, 'model_digest': model_digest, 'arguments_digest': self._hash(canonical(arguments)), 'reason': denied})
        if denied:
            raise SafetyDenied(denied)
        try:
            value = self._tools[tool](arguments)
        except Exception:
            with self._lock, self._db() as db:
                self._event(db, 'dispatch_failed', {'dispatch_event': event_id})
            raise
        with self._lock, self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._integrity(db)
            current = db.execute('SELECT stopped,epoch FROM control_state WHERE id=1').fetchone()
            invalidated = current['stopped'] or current['epoch'] != state['epoch']
            self._event(db, 'dispatch_response_discarded' if invalidated else 'dispatch_completed', {'dispatch_event': event_id})
        if invalidated:
            raise SafetyDenied('dispatch response discarded after owner revocation; side effects may already have occurred')
        return value

    def status(self):
        with self._db() as db:
            state = db.execute('SELECT * FROM control_state WHERE id=1').fetchone()
            fresh = state['heartbeat'] is not None and 0 <= self.clock() - state['heartbeat'] <= self.watchdog_seconds
            return {'stopped': bool(state['stopped']), 'epoch': state['epoch'], 'observer_fresh': fresh, 'audit_valid': self._verify(db), 'os_isolation_verified': False, 'inflight_cancellation': False, 'integrity_incident': bool(db.execute('SELECT active FROM integrity_incident WHERE id=1').fetchone()[0])}

    def audit_head(self, observer_secret, nonce):
        self._observer_auth(observer_secret)
        bounded(nonce, 'observer challenge', 128)
        with self._db() as db:
            self._integrity(db)
            row = db.execute('SELECT seq,digest FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
            result = {'seq': row['seq'], 'event_hash': row['digest'], 'nonce': nonce}
            result['receipt_signature'] = hmac.new(self.observer_secret.encode(), canonical(result).encode(), hashlib.sha256).hexdigest()
            return result

    def events(self, *, after=0, limit=None):
        if not isinstance(after, int) or isinstance(after, bool) or after < 0 or (limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100)):
            raise ValueError('invalid audit page')
        with self._db() as db:
            self._integrity(db)
            result = []
            for row in db.execute('SELECT * FROM audit WHERE seq>? ORDER BY seq LIMIT ?', (after, limit if limit is not None else -1)):
                event = dict(event_id=row['seq'], seq=row['seq'], digest=row['digest'], event_hash=row['digest'], previous=row['previous'], previous_hash=row['previous'], **json.loads(row['payload']))
                event['receipt_signature'] = hmac.new(self.observer_secret.encode(), canonical(event).encode(), hashlib.sha256).hexdigest()
                result.append(event)
            return result

    def verify_event(self, event):
        if not isinstance(event, dict):
            return False
        payload = dict(event)
        signature = payload.pop('receipt_signature', None)
        expected = hmac.new(self.observer_secret.encode(), canonical(payload).encode(), hashlib.sha256).hexdigest()
        return isinstance(signature, str) and hmac.compare_digest(signature, expected)
