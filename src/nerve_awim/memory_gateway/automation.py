"""Bounded host-owned execution and independent outcome feedback.

Only registered synthetic string tools execute. Claims survive process failure;
there is no retry of a pending episode and no raw task/output persistence.
"""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from ..agent_bridge_v13 import DemoAgentBridge
from ..memory_v18 import _id
from .learning import VerifiedOutcomeLearning


class AutomaticLearningRun:
    def __init__(self, learning, reader, agent_database, run_id, max_episodes=20, max_failures=3):
        if type(learning) is not VerifiedOutcomeLearning:
            raise TypeError('trusted outcome learning required')
        _id(run_id, 'run')
        if type(max_episodes) is not int or not 1 <= max_episodes <= 1000:
            raise ValueError('episode budget must be 1..1000')
        if type(max_failures) is not int or not 1 <= max_failures <= 100:
            raise ValueError('failure budget must be 1..100')
        self.learning, self.reader, self.run_id = learning, reader, run_id
        self.agent_database = Path(agent_database).resolve()
        self.session = replace(learning.session(reader), can_propose=False)
        self._check_access()
        scope = learning.scope
        self.key = (scope.tenant_id, scope.agent_id, run_id)
        self.config = json.dumps({'context': scope.context, 'revision': learning.ranker.revision,
            'window': learning.ranker.window, 'max_episodes': max_episodes,
            'max_failures': max_failures,
            'agent_database_hash': sha256(str(self.agent_database).encode()).hexdigest()}, sort_keys=True)
        with sqlite3.connect(self.path) as con:
            con.execute('''CREATE TABLE IF NOT EXISTS memory_automatic_runs_v1 (
                tenant TEXT, agent TEXT, run TEXT, config TEXT NOT NULL,
                maximum INTEGER NOT NULL, failure_limit INTEGER NOT NULL,
                claimed INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(tenant,agent,run))''')
            con.execute('''CREATE TABLE IF NOT EXISTS memory_automatic_episodes_v1 (
                tenant TEXT, agent TEXT, run TEXT, episode TEXT, task_hash TEXT,
                status TEXT NOT NULL, success INTEGER, memory TEXT,
                UNIQUE(tenant,agent,episode), UNIQUE(tenant,agent,task_hash))''')
            # Caps include failed and abandoned episodes; utility quotas alone
            # do not cover those. Existing runs remain reopenable at the cap.
            con.execute('''CREATE TRIGGER IF NOT EXISTS memory_automatic_run_quota_v1
                BEFORE INSERT ON memory_automatic_runs_v1
                WHEN NOT EXISTS (SELECT 1 FROM memory_automatic_runs_v1
                    WHERE tenant=NEW.tenant AND agent=NEW.agent AND run=NEW.run)
                AND (SELECT COUNT(*) FROM memory_automatic_runs_v1
                    WHERE tenant=NEW.tenant AND agent=NEW.agent) >= 128
                BEGIN SELECT RAISE(ABORT,'automatic_run_quota_reached'); END''')
            con.execute('''CREATE TRIGGER IF NOT EXISTS memory_automatic_episode_quota_v1
                BEFORE INSERT ON memory_automatic_episodes_v1
                WHEN (SELECT COUNT(*) FROM memory_automatic_episodes_v1
                    WHERE tenant=NEW.tenant AND agent=NEW.agent) >= 10000
                BEGIN SELECT RAISE(ABORT,'automatic_episode_quota_reached'); END''')
            con.execute('BEGIN IMMEDIATE')
            con.execute('INSERT OR IGNORE INTO memory_automatic_runs_v1 VALUES(?,?,?,?,?,?,0,0)',
                        (*self.key, self.config, max_episodes, max_failures))
            if con.execute('SELECT config FROM memory_automatic_runs_v1 WHERE tenant=? AND agent=? AND run=?',
                           self.key).fetchone()[0] != self.config:
                raise ValueError('frozen run configuration mismatch')

    @property
    def path(self):
        return self.learning.gateway.ledger.path

    def _check_access(self):
        gateway, scope = self.learning.gateway, self.learning.scope
        gateway._require(self.reader, scope, 'read')
        gateway._require(self.learning.reviewer, scope, 'read')
        gateway._require(self.learning.reviewer, scope, 'approve')

    def _claim(self, episode, digest):
        with sqlite3.connect(self.path) as con:
            con.execute('BEGIN IMMEDIATE')
            maximum, failure_limit, claimed, failures = con.execute('''SELECT maximum,failure_limit,claimed,failures
                FROM memory_automatic_runs_v1 WHERE tenant=? AND agent=? AND run=?''', self.key).fetchone()
            if claimed >= maximum or failures >= failure_limit:
                raise ValueError('automatic learning budget exhausted')
            # Serialize one active episode per run. A crash consumes its claim;
            # the host must investigate rather than silently repeat execution.
            if con.execute('''SELECT 1 FROM memory_automatic_episodes_v1
                WHERE tenant=? AND agent=? AND run=? AND status='pending' ''', self.key).fetchone():
                raise ValueError('pending episode requires host investigation')
            con.execute('INSERT INTO memory_automatic_episodes_v1 VALUES(?,?,?,?,?,\'pending\',NULL,NULL)',
                        (*self.key, episode, digest))
            con.execute('UPDATE memory_automatic_runs_v1 SET claimed=claimed+1 WHERE tenant=? AND agent=? AND run=?', self.key)

    def _finish(self, episode, status, success=None, memory=None, strategies=None):
        with sqlite3.connect(self.path) as con:
            con.execute('BEGIN IMMEDIATE')
            updated = con.execute('''UPDATE memory_automatic_episodes_v1 SET status=?,success=?,memory=?
                WHERE tenant=? AND agent=? AND run=? AND episode=? AND status='pending' ''',
                (status, success, memory, *self.key, episode)).rowcount
            if updated != 1:
                raise ValueError('episode already finalized')
            if status == 'judged' and success is True:
                con.execute('UPDATE memory_automatic_runs_v1 SET failures=0 WHERE tenant=? AND agent=? AND run=?', self.key)
            else:
                con.execute('UPDATE memory_automatic_runs_v1 SET failures=failures+1 WHERE tenant=? AND agent=? AND run=?', self.key)
        return {'status': status, 'success': success, 'memory_id': memory,
                'strategies': strategies or {}, 'synthetic_only': True}

    def status(self):
        self._check_access()
        with sqlite3.connect(self.path) as con:
            maximum, threshold, used, failures = con.execute("SELECT maximum,failure_limit,claimed,failures FROM memory_automatic_runs_v1 WHERE tenant=? AND agent=? AND run=?", self.key).fetchone()
            pending = bool(con.execute("SELECT 1 FROM memory_automatic_episodes_v1 WHERE tenant=? AND agent=? AND run=? AND status='pending'", self.key).fetchone())
        reason = ('pending_episode' if pending else 'episode_budget' if used >= maximum
                  else 'failure_budget' if failures >= threshold else None)
        return {'consumed': used, 'failures': failures, 'stop_reason': reason,
                'max_episodes': maximum, 'max_failures': threshold}

    def execute(self, episode_id, task):
        """Host-only: task fields and evaluator are never supplied by an agent."""
        _id(episode_id, 'episode')
        if type(task) is not dict or type(task.get('document')) is not str or not 1 <= len(task['document']) <= 512:
            raise ValueError('bounded synthetic document required')
        try:
            encoded = json.dumps(task, sort_keys=True, allow_nan=False, separators=(',', ':'))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError('bounded JSON task required') from exc
        if len(encoded.encode()) > 16384:
            raise ValueError('bounded JSON task required')
        task = json.loads(encoded)
        self._check_access()
        self._claim(episode_id, sha256(task['document'].encode()).hexdigest())
        try:
            self._check_access()
            evidence = self.session.query('email normalization')
            if (len(evidence['records']) != 1
                    or evidence['fallback_reason'] == 'retrieval_backend_unavailable'):
                return self._finish(episode_id, 'no_evidence')
            bridge = DemoAgentBridge(self.agent_database,
                agent_id=self.learning.scope.agent_id, memory_session=self.session,
                require_verified_memory=True)
            result = bridge.run_pipeline(task_id=sha256(episode_id.encode()).hexdigest()[:32],
                                         email_document=task['document'])
            self._check_access()
            evidence = result.get('verified_memory', {})
            provenance = evidence.get('provenance', [])
            if (evidence.get('status') != 'used' or len(provenance) != 1
                    or evidence.get('fallback_reason') == 'retrieval_backend_unavailable'):
                return self._finish(episode_id, 'no_evidence')
            selected = provenance[0]
            current = self.learning._checked(selected['memory_id'])
            if current.source_sha256 != selected['source_sha256'] or current.source_id != selected['source_id']:
                return self._finish(episode_id, 'memory_unavailable')
            judged = self.learning.observe(current.memory_id, episode_id, task, result['result'],
                                           expected_record=current)
            try:
                self._check_access()
            except PermissionError:
                with sqlite3.connect(self.path) as con:
                    con.execute("UPDATE memory_utility SET status='memory_unavailable',success=NULL WHERE tenant=? AND agent=? AND episode=?",
                                (*self.key[:2], episode_id))
                raise
            status = judged['status'] if judged['status'] in ('judged', 'evaluator_failed', 'memory_unavailable') else 'evaluator_failed'
            return self._finish(episode_id, status, judged['success'], current.memory_id, result['strategies'])
        except (PermissionError, LookupError):
            return self._finish(episode_id, 'memory_unavailable')
        except Exception:
            return self._finish(episode_id, 'execution_failed')
