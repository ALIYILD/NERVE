"""Receipt-based observer, administered outside the learning worker's authority.

No classifier of model prose is trusted to grant permission or stop all learning.
The controller already denies prohibited calls. This observer reports verifiable
facts and refreshes the independent watchdog only after checking its audit feed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import secrets
from contextlib import contextmanager
from urllib.request import Request, build_opener, ProxyHandler

from .client import MAX_BYTES, RuntimeClient, SafetyUnavailable, _NoRedirect
from .contracts import canonical


class ObservationRejected(PermissionError):
    pass


class ObserverClient:
    """Separately privileged IPC client; never give this object to a learner."""
    def __init__(self, endpoint, observer_secret, *, timeout=3):
        checked = RuntimeClient(endpoint, observer_secret, timeout=timeout)
        self.endpoint, self.timeout = checked.endpoint, checked.timeout
        self.secret = observer_secret

    def _post(self, route, value):
        data = canonical(value).encode()
        if len(data) > MAX_BYTES:
            raise ValueError("observer request too large")
        request = Request(self.endpoint + route, data=data, method="POST",
                          headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.secret})
        try:
            with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("bounded observer response required")
                return json.loads(raw)
        except Exception:
            raise SafetyUnavailable("observer controller unavailable or denied") from None

    def audit_head(self, secret, nonce):
        if not hmac.compare_digest(secret, self.secret):
            raise ObservationRejected("observer secret mismatch")
        return self._post("/head", {"nonce": nonce})

    def events(self, *, after=0, limit=8):
        return self._post("/events", {"after": after, "limit": limit})

    def heartbeat(self, secret):
        if not hmac.compare_digest(secret, self.secret):
            raise ObservationRejected("observer secret mismatch")
        return self._post("/heartbeat", {})

    def report(self, secret, evidence):
        if not hmac.compare_digest(secret, self.secret):
            raise ObservationRejected("observer secret mismatch")
        return self._post("/report", evidence)


class BehaviouralObserver:
    def __init__(self, path, observer_secret: str, *, outbox=None):
        if not isinstance(observer_secret, str) or not observer_secret:
            raise ValueError("observer authentication required")
        self.path, self.secret, self.outbox = str(path), observer_secret, outbox
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS observer_cursor(id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL, digest TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO observer_cursor VALUES(1,0,?)", ("0" * 64,))
            db.execute("CREATE TABLE IF NOT EXISTS observer_liveness(id INTEGER PRIMARY KEY CHECK(id=1), minimum_seq INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO observer_liveness VALUES(1,0)")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _signature(self, event):
        if not isinstance(event, dict):
            raise ObservationRejected("invalid signed receipt")
        value = dict(event)
        signature = value.pop("receipt_signature", None)
        expected = hmac.new(self.secret.encode(), canonical(value).encode(), hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(expected, signature):
            raise ObservationRejected("receipt authentication failed")
        return value

    def _verified(self, events, cursor):
        if not isinstance(events, list):
            raise ObservationRejected("invalid receipt feed")
        previous = cursor[1]
        for seq, event in enumerate(events, cursor[0] + 1):
            value = self._signature(event)
            body = {key: value[key] for key in ("kind", "time", "data")}
            digest = hashlib.sha256((previous + canonical(body)).encode()).hexdigest()
            if (value.get("seq") != seq or value.get("event_id") != seq or
                    value.get("previous") != previous or value.get("previous_hash") != previous or
                    value.get("event_hash") != digest or value.get("digest") != digest):
                raise ObservationRejected("receipt sequence or hash chain failed")
            previous = digest
        return cursor[0] + len(events), previous

    def _snapshot(self, controller, cursor, minimum):
        nonce = secrets.token_hex(24)
        head = self._signature(controller.audit_head(self.secret, nonce))
        if (head.get("nonce") != nonce or type(head.get("seq")) is not int or
                head["seq"] < max(cursor[0], minimum)):
            raise ObservationRejected("stale or replayed audit head")
        events = []
        current = cursor
        while current[0] < head["seq"]:
            page = controller.events(after=current[0], limit=8)
            if not isinstance(page, list) or not 1 <= len(page) <= 8:
                raise ObservationRejected("audit tail missing or oversized")
            # Concurrent controller activity can append beyond the signed snapshot.
            page = page[:head["seq"] - current[0]]
            current = self._verified(page, current)
            events.extend(page)
        if current[1] != head.get("event_hash"):
            raise ObservationRejected("audit head digest mismatch")
        return events, current

    def _report(self, controller, evidence, *, scope=""):
        if self.outbox is not None:
            self.outbox.enqueue({**evidence, "scope": scope})
        controller.report(self.secret, evidence)

    def poll(self, controller) -> dict:
        with self._db() as db:
            cursor = db.execute("SELECT seq,digest FROM observer_cursor WHERE id=1").fetchone()
            minimum = db.execute("SELECT minimum_seq FROM observer_liveness WHERE id=1").fetchone()[0]
        try:
            events, next_cursor = self._snapshot(controller, cursor, minimum)
        except Exception:
            evidence = {"kind": "tamper", "severity": "critical",
                        "evidence_ref": hashlib.sha256(canonical(cursor).encode()).hexdigest(),
                        "detail": "receipt verification failed; watchdog not refreshed"}
            try:
                self._report(controller, evidence)
            except Exception:
                pass  # A corrupt/unreachable controller must not refresh liveness.
            raise ObservationRejected("audit feed rejected; watchdog not refreshed") from None
        incidents = 0
        for event in events:
            if event["kind"] != "dispatch_denied":
                continue
            reason = event["data"].get("reason")
            kind = {"model identity mismatch": "model_mismatch",
                    "observer watchdog stale": "watchdog"}.get(reason, "tool_denial")
            evidence = {"kind": kind, "severity": "warning", "evidence_ref": event["event_hash"],
                        "detail": "controller verified and denied protected dispatch"}
            self._report(controller, evidence, scope=canonical(event["data"].get("scope", {})))
            incidents += 1
        with self._db() as db:
            db.execute("UPDATE observer_cursor SET seq=?,digest=? WHERE id=1", next_cursor)
        heartbeat = controller.heartbeat(self.secret)
        if not isinstance(heartbeat, dict) or type(heartbeat.get("event_id")) is not int or heartbeat["event_id"] <= next_cursor[0]:
            raise ObservationRejected("invalid heartbeat receipt")
        with self._db() as db:
            db.execute("UPDATE observer_liveness SET minimum_seq=? WHERE id=1", (heartbeat["event_id"],))
        return {"verified_through": next_cursor[0], "incidents": incidents,
                "watchdog_refreshed": True, "automatic_stop": False}
