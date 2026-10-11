"""Local Agent OS learning host. Agents supply answers, never their own rewards.

The initial supported task is evidence handoff: deterministic checks over host
observations. Learned text is scoped advice, never code or release authority.
"""
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import time

from .adaptive_memory import OutcomeMemoryRanker
from .learning_study import canonical
from .memory_v18 import MemoryAuthority, TrustedMemoryLedger, _id

CONTEXT = 'agentos-evidence-handoff-v1'
REVISION = 'handoff-judge-v1'
BASELINE = ('Report evidence honestly. A task is complete only when its command '
            'exited zero, its artifact exists, and independent verification passed. '
            'Missing evidence is unknown. Never claim an unobserved memory write.')


def expected_handoff(task):
    """Host facts, not an agent's completion claim, determine the answer."""
    if type(task) is not dict or set(task) != {'id', 'exit_code', 'artifact_exists', 'qa_passed', 'memory_written'}:
        raise ValueError('exact host evidence schema required')
    _id(task['id'], 'task')
    if task['exit_code'] is not None and type(task['exit_code']) is not int:
        raise ValueError('integer exit code or unknown required')
    if any(task[k] is not None and type(task[k]) is not bool
           for k in ('artifact_exists', 'qa_passed', 'memory_written')):
        raise ValueError('boolean or unknown evidence required')
    values = (task['exit_code'], task['artifact_exists'], task['qa_passed'])
    failed = (task['exit_code'] is not None and task['exit_code'] != 0) or any(v is False for v in values[1:])
    status = 'failed' if failed else 'unknown' if any(v is None for v in values) else 'done'
    return {'status': status, 'passed': status == 'done',
            'memory_saved': task['memory_written'] is True}


def judge_handoff(task, output, expected=None):
    answer = expected_handoff(task)
    return (type(output) is dict and set(output) == set(answer)
            and all(type(output[k]) is type(v) and output[k] == v for k, v in answer.items()))


@contextmanager
def host_lock(directory):
    """Separate lock inode avoids macOS flock interference with SQLite writes."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'host.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


class AgentOSLearning:
    """Trusted local host; keep this class out of untrusted web write endpoints."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'learning.sqlite3'
        self.authority = MemoryAuthority()
        self.ledger = TrustedMemoryLedger(self.path, self.authority)
        with sqlite3.connect(self.path) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS nerve_runs (
                id TEXT PRIMARY KEY, profile TEXT, task_hash TEXT, success INTEGER,
                lesson TEXT, created REAL, mode TEXT, UNIQUE(profile,task_hash,mode))''')
            db.execute('''CREATE TABLE IF NOT EXISTS nerve_calls (
                id INTEGER PRIMARY KEY, day TEXT, provider TEXT, status TEXT)''')
            db.execute('''CREATE TABLE IF NOT EXISTS nerve_holdouts (
                hash TEXT PRIMARY KEY, study TEXT)''')
            db.execute('''CREATE TABLE IF NOT EXISTS nerve_lessons (
                profile TEXT, memory TEXT PRIMARY KEY, study TEXT, failures INTEGER DEFAULT 0)''')
            db.execute('''CREATE TABLE IF NOT EXISTS nerve_missions (
                id TEXT PRIMARY KEY, profile TEXT, success INTEGER, duration REAL, source TEXT)''')

    def actor(self, profile):
        _id(profile, 'profile')
        return self.authority.issue('agentos-local', profile,
                                    permissions=('read', 'propose', 'approve'))

    def recall(self, profile):
        actor = self.actor(profile)
        ranker = OutcomeMemoryRanker(self.ledger, evaluator=lambda record, task, output:
            judge_handoff(task, output), evaluator_revision=REVISION)
        pool = self.ledger.retrieve(actor, context=CONTEXT, query='', limit=20)
        return ranker.rank(actor, pool)

    def observe(self, profile, task, output, *, lesson=None, mode='live'):
        """One outcome per profile/task/mode; failed predictions also count."""
        _id(mode, 'mode')
        accepted = judge_handoff(task, output)
        digest = sha256(canonical(task).encode()).hexdigest()
        run_id = sha256(canonical([profile, mode, digest]).encode()).hexdigest()
        actor = self.actor(profile)
        # Initialise utility schema before the transaction; receipt, reward and
        # drift revocation then commit together, including across host processes.
        if lesson and mode == 'live':
            OutcomeMemoryRanker(self.ledger, evaluator=lambda record, t, o:
                judge_handoff(t, o), evaluator_revision=REVISION)
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            duplicate = db.execute('SELECT success FROM nerve_runs WHERE id=?', (run_id,)).fetchone()
            if duplicate:
                return {'id':run_id, 'duplicate':True, 'success':bool(duplicate[0])}
            if lesson:
                record = self.ledger._get(db, actor, lesson)
                if (record.status != 'approved' or record.context != CONTEXT
                        or (record.valid_until is not None and record.valid_until <= int(time.time()))):
                    raise ValueError('current approved unexpired in-scope lesson required')
            db.execute('INSERT INTO nerve_runs VALUES(?,?,?,?,?,?,?)',
                (run_id, profile, digest, int(accepted), lesson, time.time(), mode))
            if lesson and mode == 'live':
                self.authority.require(actor, 'approve')
                db.execute('INSERT INTO memory_utility VALUES(NULL,?,?,?,?,?,?,?,?)',
                    (actor.tenant_id, actor.agent_id, run_id, digest, lesson,
                     REVISION, 'judged', int(accepted)))
                recent = db.execute('SELECT success FROM nerve_runs WHERE profile=? AND lesson=? '
                    "AND mode='live' ORDER BY created DESC, rowid DESC LIMIT 5", (profile, lesson)).fetchall()
                if len(recent) >= 3 and sum(not r[0] for r in recent) >= 3:
                    db.execute("UPDATE trusted_memory_v18 SET status='revoked',evaluator_id=? "
                        'WHERE memory_id=? AND tenant_id=? AND agent_id=?',
                        (REVISION + '-drift', lesson, actor.tenant_id, actor.agent_id))
        return {'id':run_id, 'duplicate':False, 'success':accepted}

    def reserve_calls(self, provider, count, *, daily_limit=12):
        if (provider not in ('hermes-free', 'jev') or type(count) is not int
                or type(daily_limit) is not int or not 1 <= count <= daily_limit <= 20):
            raise ValueError('bounded provider reservation required')
        day = time.strftime('%Y-%m-%d', time.gmtime())
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            used = db.execute('SELECT COUNT(*) FROM nerve_calls WHERE day=? AND provider=?', (day, provider)).fetchone()[0]
            if used + count > daily_limit:
                raise RuntimeError('durable daily call limit reached')
            db.executemany('INSERT INTO nerve_calls(day,provider,status) VALUES(?,?,?)',
                           [(day, provider, 'reserved')] * count)

    @staticmethod
    def evidence_hash(task):
        """Evidence identity excludes cosmetic IDs to prevent holdout recycling."""
        expected_handoff(task)
        return sha256(canonical({k: v for k, v in task.items() if k != 'id'}).encode()).hexdigest()

    def reserved_evidence(self):
        with sqlite3.connect(self.path) as db:
            return {row[0] for row in db.execute('SELECT hash FROM nerve_holdouts')}

    def reserve_holdout(self, study, tasks):
        _id(study, 'study')
        hashes = [self.evidence_hash(t) for t in tasks]
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            db.executemany('INSERT INTO nerve_holdouts VALUES(?,?)', [(h, study) for h in hashes])

    def accept_study(self, profile, study, report):
        """Only a trusted host invokes this after the NERVE loop finishes.

        Passing the narrow fixture permits scoped advice retrieval only. This is
        not approval for tool changes, profile mutation or source-code changes.
        """
        _id(study, 'study')
        if type(report) is not dict:
            raise ValueError('trusted host study report required')
        final = report.get('final') or {}
        if report.get('status') != 'observed_final_gain' or not report.get('selected_lesson'):
            return None
        fields = ('tasks', 'wins', 'losses', 'baseline_hits', 'lesson_hits')
        if type(final) is not dict or any(type(final.get(k)) is not int for k in fields):
            raise ValueError('integer paired evaluation counts required')
        n, wins, losses, baseline, hits = (final[k] for k in fields)
        if (n < 5 or not 0 <= wins <= n or not 0 <= losses <= n
                or not 0 <= baseline <= n or not 0 <= hits <= n
                or hits - baseline != wins - losses or wins > n - baseline
                or losses > baseline or wins + losses > n):
            raise ValueError('consistent paired evaluation counts required')
        if wins < 1 or losses != 0:
            return None
        actor = self.actor(profile)
        # Separate from the bridge's outer host lock. Retry after interruption
        # recovers the original proposal instead of creating duplicate advice.
        with host_lock(self.directory / 'acceptance'):
            with sqlite3.connect(self.path) as db:
                count = db.execute('SELECT COUNT(*) FROM nerve_holdouts WHERE study=?', (study,)).fetchone()[0]
                existing = db.execute('SELECT memory_id,content,status FROM trusted_memory_v18 '
                    'WHERE tenant_id=? AND agent_id=? AND source_id=? AND context=?',
                    (actor.tenant_id, actor.agent_id, study, CONTEXT)).fetchone()
            if count != n:
                raise ValueError('durably reserved final tasks must match report')
            if existing:
                mid, content, status = existing
                if content != report['selected_lesson']:
                    raise ValueError('study already bound to another lesson')
                if status not in ('pending', 'approved'):
                    return None
            else:
                mid = self.ledger.propose(actor, context=CONTEXT, content=report['selected_lesson'],
                    source_id=study, kind='procedural', valid_until=int(time.time())+30*86400)
                status = 'pending'
            if status == 'pending':
                self.ledger.decide(actor, mid, approve=True, evaluator_id=REVISION, score=hits/n)
            with sqlite3.connect(self.path) as db:
                db.execute('INSERT OR IGNORE INTO nerve_lessons(profile,memory,study) VALUES(?,?,?)',
                           (profile,mid,study))
            return mid

    def ingest_mission(self, run_id, profile, *, success, duration, source):
        """Host adapter supplies independently checked terminal/QA metadata only."""
        _id(run_id, 'run'); _id(profile, 'profile')
        if type(success) is not bool or type(duration) not in (int,float) or not 0 <= duration <= 86400:
            raise ValueError('verified outcome and bounded duration required')
        with sqlite3.connect(self.path) as db:
            return db.execute('INSERT OR IGNORE INTO nerve_missions VALUES(?,?,?,?,?)',
                (run_id,profile,int(success),duration,source)).rowcount == 1

    def recommend_profiles(self, candidates, *, incumbent=None):
        """Rank explicitly capable profiles by recent verified mission outcomes.

        This heuristic is not a calibrated success probability or a capability
        detector. Three observations are required before changing the incumbent;
        equal scores retain it. Latest means ingestion order, not completion time.
        """
        if (type(candidates) not in (list, tuple) or not 1 <= len(candidates) <= 20
                or any(type(p) is not str for p in candidates)
                or len(set(candidates)) != len(candidates)):
            raise ValueError('one to twenty distinct capable profiles required')
        for profile in candidates:
            _id(profile, 'profile')
        if incumbent is None:
            incumbent = candidates[0]
        if incumbent not in candidates:
            raise ValueError('incumbent must be a capable candidate')
        ranked = []
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN')
            for index, profile in enumerate(candidates):
                rows = db.execute('SELECT success FROM nerve_missions WHERE profile=? '
                    'ORDER BY rowid DESC LIMIT 20', (profile,)).fetchall()
                samples, passed = len(rows), sum(r[0] for r in rows)
                ranked.append(dict(profile=profile, samples=samples, passed=passed,
                    score=(1 + passed)/(2 + samples), eligible=samples >= 3,
                    candidate_order=index))
        ranked.sort(key=lambda r: (-r['score'], r['profile'] != incumbent, r['candidate_order']))
        current = next(r for r in ranked if r['profile'] == incumbent)
        challengers = [r for r in ranked if r['eligible'] and r['score'] > current['score']]
        recommended = challengers[0]['profile'] if challengers else incumbent
        for row in ranked:
            row.pop('candidate_order')
        return dict(recommended=recommended, incumbent=incumbent, changed=recommended != incumbent,
                    ranked=ranked, window=20, minimum_samples=3,
                    scope='Heuristic recent verified outcomes; caller must establish task capability.')

    def status(self):
        with sqlite3.connect(self.path) as db:
            runs = [dict(profile=r[0], mode=r[1], tasks=r[2], passed=r[3]) for r in db.execute(
                'SELECT profile,mode,COUNT(*),SUM(success) FROM nerve_runs GROUP BY profile,mode')]
            missions = [dict(profile=r[0], tasks=r[1], passed=r[2], mean_seconds=r[3]) for r in db.execute(
                'SELECT profile,COUNT(*),SUM(success),AVG(duration) FROM nerve_missions GROUP BY profile')]
            memories = dict(db.execute('SELECT status,COUNT(*) FROM trusted_memory_v18 GROUP BY status'))
        return {'updated_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                'context':CONTEXT, 'runs':runs, 'missions':missions, 'memories':memories,
                'scope':'Evidence handoff lessons and observed operational results; no model weight training.',
                'automatic_paid_calls':False}
