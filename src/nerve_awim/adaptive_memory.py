"""Opt-in outcome-based memory ranking; not model training or a MemRL reproduction.

The host owns the independent evaluator and approval capability. Only public or
synthetic episodes belong here. Raw task/output data are never stored.
"""
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3
import time

from .memory_v18 import _id


class OutcomeMemoryRanker:
    def __init__(self, ledger, *, evaluator, evaluator_revision, window=20, tie_break="relevance",
                 decay_half_life=None):
        if not callable(evaluator):
            raise TypeError('trusted host evaluator required')
        _id(evaluator_revision, 'evaluator revision')
        if type(window) is not int or not 3 <= window <= 100:
            raise ValueError('window must be between 3 and 100')
        if type(tie_break) is not str or tie_break not in ('relevance', 'least_recent'):
            raise ValueError('registered tie-breaking policy required')
        if decay_half_life is not None and (type(decay_half_life) is not int or not 1 <= decay_half_life <= 100):
            raise ValueError('decay half-life must be None or 1..100 judged episodes')
        self.decay_half_life = decay_half_life
        self.tie_break = tie_break
        self.ledger, self.evaluator = ledger, evaluator
        self.revision, self.window = evaluator_revision, window
        with sqlite3.connect(ledger.path) as con:
            con.execute('''CREATE TABLE IF NOT EXISTS memory_utility (
                sequence INTEGER PRIMARY KEY, tenant TEXT, agent TEXT,
                episode TEXT, payload_hash TEXT, memory TEXT, revision TEXT,
                status TEXT, success INTEGER,
                UNIQUE(tenant,agent,episode), UNIQUE(tenant,agent,payload_hash))''')
            # Gateway-owned ledgers preserve utility cleanup even when this
            # optional ranker is created after the gateway. Legacy-only stores
            # retain their existing schema/behaviour.
            if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_scope_revocations_v1'").fetchone():
                from .memory_gateway.policy import install_utility_cleanup
                install_utility_cleanup(con)

    @staticmethod
    def _active(record, now):
        return record.status == 'approved' and (record.valid_until is None or record.valid_until > now)

    def observe(self, reviewer, *, memory_id, episode_id, task, output):
        """One credited memory per fresh episode, independently scored by host.

        Caller cannot submit rewards. Approval capability is host-only; the
        evaluator must validate task/output independently, not echo agent claims.
        Changing evaluator semantics requires a new evaluator_revision.
        """
        self.ledger.authority.require(reviewer, 'approve')
        _id(episode_id, 'episode')
        encoded = json.dumps(task, sort_keys=True, allow_nan=False, separators=(',', ':'))
        result = json.dumps(output, allow_nan=False)
        if len(encoded.encode()) > 16384 or len(result.encode()) > 16384:
            raise ValueError('bounded task/output required')
        digest = sha256(encoded.encode()).hexdigest()
        scope = (reviewer.tenant_id, reviewer.agent_id)
        with sqlite3.connect(self.ledger.path) as con:
            con.execute('BEGIN IMMEDIATE')
            record = self.ledger._get(con, reviewer, memory_id)
            if not self._active(record, int(time.time())):
                raise ValueError('approved unexpired memory required')
            con.execute('INSERT INTO memory_utility VALUES(NULL,?,?,?,?,?,?,?,NULL)',
                        (*scope, episode_id, digest, memory_id, self.revision, 'pending'))
        success, status = None, 'evaluator_failed'
        try:
            judged = self.evaluator(deepcopy(record), json.loads(encoded), json.loads(result))
            if type(judged) is bool:
                success, status = int(judged), 'judged'
        except Exception:
            pass
        self.ledger.authority.require(reviewer, 'approve')
        with sqlite3.connect(self.ledger.path) as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                current = self.ledger._get(con, reviewer, memory_id)
            except LookupError:
                current = None
            if current is None or not self._active(current, int(time.time())):
                success, status = None, 'memory_unavailable'
            con.execute('UPDATE memory_utility SET status=?,success=? WHERE tenant=? AND agent=? AND episode=?',
                        (status, success, *scope, episode_id))
        return {'status': status, 'success': None if success is None else bool(success)}

    def rank(self, actor, candidates, *, now=None):
        """Reorder at most 20 relevant approved candidates; never grant access.

        Recent-window Beta(1,1) means are heuristic preferences, not calibrated
        confidence or evidence that this memory causally improved performance.
        Default ties preserve relevance; least_recent is opt-in exact-tie exploration.
        Unseen memories have neutral score 0.5; relevance order breaks ties.
        """
        self.ledger.authority.require(actor, 'read')
        if now is None:
            now = int(time.time())
        if type(now) is not int or now < 0 or len(candidates) > 20:
            raise ValueError('bounded candidates and clock required')
        ranked, seen = [], set()
        with sqlite3.connect(self.ledger.path) as con:
            con.execute('BEGIN')
            for index, candidate in enumerate(candidates):
                if candidate.memory_id in seen:
                    continue
                seen.add(candidate.memory_id)
                try:
                    current = self.ledger._get(con, actor, candidate.memory_id)
                except LookupError:
                    continue
                if not self._active(current, now):
                    continue
                rows = con.execute('''SELECT success,sequence FROM memory_utility
                    WHERE tenant=? AND agent=? AND memory=? AND revision=? AND status='judged'
                    ORDER BY sequence DESC LIMIT ?''',
                    (actor.tenant_id, actor.agent_id, current.memory_id, self.revision, self.window)).fetchall()
                utility = (1 + sum(row[0] for row in rows)) / (2 + len(rows))
                if self.decay_half_life is not None and rows:
                    # Count authorised same-context judged episodes since this
                    # source was used, not global SQL sequence gaps (which can
                    # contain other tenants, contexts or evaluator revisions).
                    age = con.execute("""SELECT COUNT(*) FROM memory_utility u
                        JOIN trusted_memory_v18 m ON m.memory_id=u.memory
                        AND m.tenant_id=u.tenant AND m.agent_id=u.agent
                        WHERE u.tenant=? AND u.agent=? AND m.context=? AND u.revision=?
                        AND u.status='judged' AND u.sequence>?""",
                        (actor.tenant_id, actor.agent_id, current.context, self.revision, rows[0][1])).fetchone()[0]
                    utility = 0.5 + (utility - 0.5) * 2 ** (-age / self.decay_half_life)
                # Equal recent utility can otherwise trap the policy on the
                # same repeatedly failing memory. Opt-in bounded exploration
                # tries the least recently judged candidate only on exact ties.
                recent = rows[0][1] if rows else -1
                tie = recent if self.tie_break == 'least_recent' else index
                ranked.append((-utility, tie, index, current))
        return [row[3] for row in sorted(ranked, key=lambda row: row[:3])]
