"""Trusted-host outcome learning; no evaluator or reward is supplied by agents.

The host freezes an independent evaluator before observing an outcome. Its task
inputs must come from the host's experiment, never an agent's claimed answer key.
Utility is a recent-outcome preference, not causal proof or model training.
"""
from hashlib import sha256
import sqlite3
import time

from ..adaptive_memory import OutcomeMemoryRanker
from ..memory_retrieval_v18 import SecureMemoryRetriever
from .gateway import MemoryGateway
from .session import BoundMemorySession


class VerifiedOutcomeLearning:
    def __init__(self, gateway, reviewer, scope, evaluator, evaluator_revision, window=3,
                 max_observations=10000):
        if type(gateway) is not MemoryGateway or type(gateway.retriever) is not SecureMemoryRetriever:
            raise TypeError('authoritative gateway and secure retriever required')
        if not callable(evaluator):
            raise TypeError('trusted host evaluator required')
        if type(max_observations) is not int or not 1 <= max_observations <= 100000:
            raise ValueError('observation quota must be 1..100000')
        gateway._require(reviewer, scope, 'approve')
        gateway._require(reviewer, scope, 'read')
        self.gateway, self.reviewer, self.scope = gateway, reviewer, scope

        def judge(record, task, output):
            current = self._checked(record.memory_id)
            if current != record:
                raise ValueError('memory changed before evaluation')
            result = evaluator(record, task, output)
            if self._checked(record.memory_id) != current:
                raise ValueError('memory changed during evaluation')
            return result

        with gateway._lock:
            if gateway.retriever.utility is not None:
                raise ValueError('existing utility evaluator cannot be overwritten')
            self.ranker = OutcomeMemoryRanker(gateway.ledger, evaluator=judge,
                evaluator_revision=evaluator_revision, window=window)
            with sqlite3.connect(gateway.ledger.path) as con:
                con.execute('''CREATE TABLE IF NOT EXISTS memory_learning_limits_v1 (
                    tenant TEXT, agent TEXT, maximum INTEGER NOT NULL,
                    PRIMARY KEY(tenant,agent))''')
                # Restart cannot silently relax an existing cap. Replay history
                # is never trimmed to make space for more rewards. Explicit authorised
                # source deletion removes utility/replay rows under lifecycle policy.
                con.execute('''INSERT INTO memory_learning_limits_v1 VALUES(?,?,?)
                    ON CONFLICT(tenant,agent) DO UPDATE SET maximum=MIN(maximum,excluded.maximum)''',
                    (scope.tenant_id, scope.agent_id, max_observations))
                con.execute('''CREATE TRIGGER IF NOT EXISTS memory_learning_quota_v1
                    BEFORE INSERT ON memory_utility
                    WHEN (SELECT COUNT(*) FROM memory_utility
                          WHERE tenant=NEW.tenant AND agent=NEW.agent) >=
                         (SELECT maximum FROM memory_learning_limits_v1
                          WHERE tenant=NEW.tenant AND agent=NEW.agent)
                    BEGIN SELECT RAISE(ABORT,'learning_observation_quota_reached'); END''')
            gateway.retriever.utility = self.ranker

    def _checked(self, memory_id):
        self.gateway._require(self.reviewer, self.scope, 'approve')
        record = self.gateway._record_in_scope(self.reviewer, memory_id, self.scope)
        if (record.status != 'approved'
                or (record.valid_until is not None and record.valid_until <= int(time.time()))
                or sha256(record.content.encode()).hexdigest() != record.source_sha256):
            raise ValueError('approved unexpired intact source required')
        return record

    def observe(self, memory_id, episode_id, task, output, *, expected_record=None):
        """Host only. Replay protection and raw-data minimisation use NERVE's ranker."""
        with self.gateway._lock:
            before = self._checked(memory_id)
            if expected_record is not None and before != expected_record:
                raise ValueError('selected memory changed before feedback')
            result = self.ranker.observe(self.reviewer, memory_id=memory_id,
                episode_id=episode_id, task=task, output=output)
            try:
                if self._checked(memory_id) != before:
                    raise ValueError('memory changed during observation')
            except (PermissionError, LookupError, ValueError):
                # The underlying evaluator failure is consumed, never retryable
                # under this episode. Recheck scope as well as legacy status.
                with sqlite3.connect(self.gateway.ledger.path) as con:
                    con.execute('''UPDATE memory_utility SET status='memory_unavailable',success=NULL
                        WHERE tenant=? AND agent=? AND episode=?''',
                        (self.scope.tenant_id, self.scope.agent_id, episode_id))
                raise
            return result

    def session(self, reader):
        """Return an agent facade using a separately issued unprivileged actor."""
        self.gateway._require(reader, self.scope, 'read')
        if reader is self.reviewer or reader.permissions & {'approve', 'delete'}:
            raise PermissionError('separate unprivileged reader capability required')
        return BoundMemorySession(self.gateway, reader, self.scope,
            can_propose='propose' in reader.permissions,
            retrieval_mode='adaptive', retrieval_limit=1)
