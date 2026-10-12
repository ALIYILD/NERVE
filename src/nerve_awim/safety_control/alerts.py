"""Durable, bounded incident notifications. Notification channels have no authority."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Callable


KINDS = frozenset({"tool_denial", "model_mismatch", "tamper", "behavioural_anomaly", "watchdog"})
SEVERITIES = frozenset({"info", "warning", "critical"})


def _digest(value: object) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()


def notification(incident: dict) -> dict:
    """Do not export arbitrary evidence, error messages, prompts, tokens or scope names."""
    kind = incident.get("kind")
    severity = incident.get("severity")
    if kind not in KINDS or severity not in SEVERITIES:
        raise ValueError("unsupported incident metadata")
    result = {"kind": kind, "severity": severity,
              "scope_digest": _digest(incident.get("scope", "")),
              "evidence_digest": _digest(incident.get("evidence_ref", "")),
              "notification_only": True}
    result["incident_id"] = _digest(json.dumps(result, sort_keys=True))
    return result


class DurableAlertOutbox:
    def __init__(self, path, *, clock: Callable = time.time, max_attempts: int = 3,
                 retry_seconds: float = 60):
        if not 1 <= max_attempts <= 10 or retry_seconds <= 0:
            raise ValueError("invalid retry bounds")
        self.path, self.clock = str(path), clock
        self.max_attempts, self.retry_seconds = max_attempts, retry_seconds
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS safety_alert_outbox (incident_id TEXT, channel TEXT, payload TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0, delivered INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(incident_id, channel))")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, incident: dict) -> str:
        payload = notification(incident)
        encoded = json.dumps(payload, sort_keys=True)
        with self._db() as db:
            for channel in ("email", "telegram"):
                db.execute("INSERT OR IGNORE INTO safety_alert_outbox(incident_id,channel,payload) VALUES(?,?,?)",
                           (payload["incident_id"], channel, encoded))
        return payload["incident_id"]

    def deliver(self, channel: str, transport: Callable[[dict], object], *, limit: int = 10) -> dict:
        if channel not in {"email", "telegram"} or not 1 <= limit <= 100:
            raise ValueError("unsupported channel or batch limit")
        result = {"attempted": 0, "delivered": 0, "failed": 0}
        for _ in range(limit):
            # Reserve before side effects; a crash cannot produce a tight retry loop.
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT incident_id,payload FROM safety_alert_outbox WHERE channel=? AND delivered=0 AND attempts<? AND next_attempt<=? ORDER BY rowid LIMIT 1",
                                 (channel, self.max_attempts, self.clock())).fetchone()
                if row is None:
                    break
                db.execute("UPDATE safety_alert_outbox SET attempts=attempts+1,next_attempt=? WHERE incident_id=? AND channel=?",
                           (self.clock() + self.retry_seconds, row[0], channel))
            result["attempted"] += 1
            try:
                response = transport(json.loads(row[1]))
                if response is False:
                    raise RuntimeError("transport declined notification")
            except Exception:
                # Persist neither transport errors nor credentials they might contain.
                result["failed"] += 1
            else:
                with self._db() as db:
                    db.execute("UPDATE safety_alert_outbox SET delivered=1 WHERE incident_id=? AND channel=?", (row[0], channel))
                result["delivered"] += 1
        return result

    def status(self) -> list[dict]:
        with self._db() as db:
            return [dict(zip(("incident_id", "channel", "attempts", "delivered"), row))
                    for row in db.execute("SELECT incident_id,channel,attempts,delivered FROM safety_alert_outbox ORDER BY rowid")]


class EmailAlertAdapter:
    def __init__(self, sender: str, recipient: str, send: Callable):
        if any("\n" in x or "\r" in x for x in (sender, recipient)):
            raise ValueError("invalid email address")
        self.sender, self.recipient, self.send = sender, recipient, send

    def __call__(self, payload: dict):
        return self.send(sender=self.sender, recipient=self.recipient,
                         subject="NERVE incident notification",
                         body=json.dumps(payload, sort_keys=True))


class TelegramAlertAdapter:
    def __init__(self, chat_id: str, send: Callable):
        self.chat_id, self.send = chat_id, send

    def __call__(self, payload: dict):
        return self.send(chat_id=self.chat_id, text=json.dumps(payload, sort_keys=True))
