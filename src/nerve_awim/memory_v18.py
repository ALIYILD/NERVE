"""NERVE Memory v1.8 research store: scoped, verified and revocable memory.

Only a trusted in-process host issues capabilities. This is NOT remote
authentication or a production medical-data system. Never give capability
issuing authority to an untrusted agent or a network request handler.
Legacy NERVE Learn SQLite remains unchanged for compatibility.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from pathlib import Path
from secrets import token_hex
import re
import sqlite3
import time
import uuid

_WORDS = re.compile(r"[a-z0-9]+", re.I)
_ALLOWED_TYPES = frozenset(("episodic", "semantic", "procedural"))
_ALLOWED_PERMS = frozenset(("propose", "approve", "read", "delete"))
_PLACEHOLDER = re.compile(
    r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"apikey_[a-f0-9]{10,}|"
    r"sk-[a-zA-Z0-9_-]{20,}|"
    r"password\s*[:=]\s*\S+)", re.I
)


def _id(text, label):
    if type(text) is not str or not 1 <= len(text) <= 96 \
            or not re.fullmatch(r"[a-zA-Z0-9_.:-]+", text):
        raise ValueError("invalid " + label)
    return text


@dataclass(frozen=True)
class MemoryActor:
    tenant_id: str
    agent_id: str
    permissions: frozenset
    _capability: str


class MemoryAuthority:
    """Trusted host constructs contexts; agents cannot self-issue privileges."""

    def __init__(self):
        self._issued = {}

    def issue(self, tenant_id, agent_id, *, permissions=("read", "propose")):
        tenant_id = _id(tenant_id, "tenant")
        agent_id = _id(agent_id, "agent")
        rights = frozenset(permissions)
        if not rights or not rights <= _ALLOWED_PERMS:
            raise ValueError("invalid host-issued permissions")
        actor = MemoryActor(tenant_id, agent_id, rights, token_hex(32))
        self._issued[actor._capability] = actor
        return actor

    def require(self, actor, permission):
        if type(actor) is not MemoryActor \
                or self._issued.get(actor._capability) is not actor \
                or permission not in actor.permissions:
            raise PermissionError("valid host-issued memory capability required")

    def revoke(self, actor):
        self.require(actor, next(iter(actor.permissions)))
        self._issued.pop(actor._capability, None)


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    tenant_id: str
    agent_id: str
    context: str
    kind: str
    content: str
    source_id: str
    source_sha256: str
    status: str
    evaluator_id: str | None
    outcome_score: float | None
    created_at: int
    valid_until: int | None
    supersedes_id: str | None


class TrustedMemoryLedger:
    """Research-grade local SQL memory with exact-scope trust boundaries.

    Not an encrypted DB, an auth service, or a clinical record store.
    The application MUST control MemoryAuthority and validate inputs before
    granting access to actors. This service is NOT exposed on public MCP.
    """

    def __init__(self, path, authority):
        if not isinstance(authority, MemoryAuthority):
            raise TypeError("host-issued memory authority required")
        self.authority = authority
        self.path = str(Path(path))
        with sqlite3.connect(self.path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS trusted_memory_v18 (
                memory_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                context TEXT NOT NULL, kind TEXT NOT NULL,
                content TEXT NOT NULL, source_id TEXT NOT NULL,
                source_sha256 TEXT NOT NULL, status TEXT NOT NULL,
                evaluator_id TEXT, outcome_score REAL,
                created_at INTEGER NOT NULL, valid_until INTEGER,
                supersedes_id TEXT)""")
            con.execute("""CREATE INDEX IF NOT EXISTS idx_memory_scope_v18
                ON trusted_memory_v18 (tenant_id,agent_id,context,status)""")

    @staticmethod
    def _record(row):
        return MemoryRecord(*row)

    def _get(self, con, actor, memory_id):
        result = con.execute(
            """SELECT * FROM trusted_memory_v18
               WHERE memory_id=? AND tenant_id=? AND agent_id=?""",
            (memory_id, actor.tenant_id, actor.agent_id),
        ).fetchone()
        if result is None:
            raise LookupError("memory not found in authorised scope")
        return self._record(result)

    def propose(self, actor, *, context, content, source_id,
                kind="episodic", valid_until=None, supersedes_id=None):
        self.authority.require(actor, "propose")
        _id(context, "context")
        _id(source_id, "source")
        if kind not in _ALLOWED_TYPES:
            raise ValueError("unsupported memory type")
        if type(content) is not str or not 1 <= len(content) <= 2048 \
                or _PLACEHOLDER.search(content):
            raise ValueError("bounded public, non-secret memory text required")
        if valid_until is not None and (
                type(valid_until) is not int or
                valid_until <= int(time.time())):
            raise ValueError("expiry must be in the future")
        if supersedes_id is not None:
            _id(supersedes_id, "supersedes reference")
        mid = uuid.uuid4().hex
        now = int(time.time())
        with sqlite3.connect(self.path) as con:
            if supersedes_id is not None:
                self._get(con, actor, supersedes_id)
            con.execute(
                """INSERT INTO trusted_memory_v18 VALUES (
                   ?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (mid, actor.tenant_id, actor.agent_id, context, kind,
                 content, source_id, sha256(content.encode()).hexdigest(),
                 "pending", None, None, now, valid_until, supersedes_id),
            )
        return mid

    def decide(self, actor, memory_id, *, approve, evaluator_id, score=None):
        self.authority.require(actor, "approve")
        _id(memory_id, "memory ID")
        _id(evaluator_id, "evaluator")
        if type(approve) is not bool:
            raise ValueError("approval must be explicit boolean")
        if score is not None and (type(score) not in (int, float)
                                  or not isfinite(score)
                                  or not 0 <= score <= 1):
            raise ValueError("outcome score must be finite 0..1")
        if not approve and score is not None:
            raise ValueError("rejected memories cannot have trusted scores")
        with sqlite3.connect(self.path) as con:
            item = self._get(con, actor, memory_id)
            if item.status != "pending":
                raise ValueError("pending record required for review")
            if item.valid_until is not None and item.valid_until <= int(time.time()):
                raise ValueError("expired memory cannot be promoted")
            if item.supersedes_id and approve:
                predecessor = self._get(con, actor, item.supersedes_id)
                if predecessor.status != "approved":
                    raise ValueError("only approved memory can be superseded")
                # Supersession occurs in the same SQLite transaction.
                con.execute(
                    """UPDATE trusted_memory_v18 SET status='superseded'
                    WHERE memory_id=? AND tenant_id=? AND agent_id=?""",
                    (predecessor.memory_id, actor.tenant_id, actor.agent_id),
                )
            con.execute(
                """UPDATE trusted_memory_v18
                SET status=?,evaluator_id=?,outcome_score=?
                WHERE memory_id=? AND tenant_id=? AND agent_id=?""",
                ("approved" if approve else "rejected", evaluator_id,
                 float(score) if score is not None else None,
                 memory_id, actor.tenant_id, actor.agent_id),
            )

    def revoke(self, actor, memory_id, *, evaluator_id):
        self.authority.require(actor, "approve")
        _id(evaluator_id, "evaluator")
        with sqlite3.connect(self.path) as con:
            item = self._get(con, actor, memory_id)
            if item.status != "approved":
                raise ValueError("only approved memories can be revoked")
            con.execute(
                """UPDATE trusted_memory_v18 SET
                   status='revoked',evaluator_id=?
                   WHERE memory_id=? AND tenant_id=? AND agent_id=?""",
                (evaluator_id, memory_id, actor.tenant_id, actor.agent_id),
            )

    def forget(self, actor, memory_id):
        """Hard-delete single local record; external caches need own purge."""
        self.authority.require(actor, "delete")
        with sqlite3.connect(self.path) as con:
            self._get(con, actor, memory_id)
            con.execute(
                """DELETE FROM trusted_memory_v18
                   WHERE memory_id=? AND tenant_id=? AND agent_id=?""",
                (memory_id, actor.tenant_id, actor.agent_id),
            )

    def retrieve(self, actor, *, context, query, limit=5, now=None):
        self.authority.require(actor, "read")
        _id(context, "context")
        if type(query) is not str or len(query) > 256:
            raise ValueError("bounded query required")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("bounded retrieval limit required")
        if now is None:
            now = int(time.time())
        if type(now) is not int or now < 0:
            raise ValueError("invalid evaluation clock")
        with sqlite3.connect(self.path) as con:
            rows = con.execute(
                """SELECT * FROM trusted_memory_v18
                   WHERE tenant_id=? AND agent_id=? AND context=?
                   AND status='approved'
                   AND (valid_until IS NULL OR valid_until>?)""",
                (actor.tenant_id, actor.agent_id, context, now),
            ).fetchall()
        tokens = set(_WORDS.findall(query.lower()))
        scored = []
        for row in rows:
            record = self._record(row)
            words = set(_WORDS.findall(record.content.lower()))
            overlap = len(tokens & words) if tokens else 1
            if not overlap:
                continue
            # Simple transparent lexical baseline. Never put content into
            # system instructions or turn scores into authorisations.
            utility = record.outcome_score if record.outcome_score is not None else 0.
            rank = (overlap / max(1, len(tokens)), utility, record.created_at)
            scored.append((rank, record))
        scored.sort(key=lambda p: (p[0], p[1].memory_id), reverse=True)
        return [record for _, record in scored[:limit]]

    def approved_pool(self, actor, *, context, now=None, limit=500):
        """Authorised approved pool for optional semantic re-ranking.

        Unlike lexical retrieve, this yields all approved in-scope memories
        in a bounded window. Untrusted external ranking results never bypass
        the ledger's exact tenant/agent/context/expiry/status filters.
        """
        self.authority.require(actor, "read")
        _id(context, "context")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid pool limit")
        if now is None:
            now = int(time.time())
        if type(now) is not int or now < 0:
            raise ValueError("invalid evaluation clock")
        with sqlite3.connect(self.path) as con:
            rows = con.execute(
                """SELECT * FROM trusted_memory_v18
                   WHERE tenant_id=? AND agent_id=? AND context=?
                     AND status='approved'
                     AND (valid_until IS NULL OR valid_until>?)
                   ORDER BY created_at DESC, memory_id DESC LIMIT ?""",
                (actor.tenant_id, actor.agent_id, context, now, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    def status(self, actor, memory_id):
        self.authority.require(actor, "read")
        with sqlite3.connect(self.path) as con:
            return self._get(con, actor, memory_id)
