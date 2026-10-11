"""Trusted local repository-learning ledger; no provider calls or remote auth.

The host owns task execution and judging. The ledger enforces split identity,
matched configured budgets and models, candidate freezing, and atomic rollback.
It cannot prove that a host-supplied judgment came from an actual execution.
"""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import time

SCOPE = 'agentos-repository-repair-v1'


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def identifier(value):
    if type(value) is not str or not 1 <= len(value) <= 200:
        raise ValueError('bounded nonempty identifier required')
    return value


def checked_budget(value):
    if type(value) is not dict or set(value) != {'max_tokens', 'max_iterations', 'timeout_seconds'}:
        raise ValueError('exact per-arm budget required')
    if any(type(v) is not int or not 1 <= v <= 100000 for v in value.values()):
        raise ValueError('positive bounded integer budgets required')
    return encode(value)


class RepositoryExperiments:
    def __init__(self, path, *, clock=time.time):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS studies (
                  id TEXT PRIMARY KEY, profile TEXT, model TEXT, revision TEXT,
                  budget TEXT, status TEXT, lesson TEXT, summary TEXT);
                CREATE TABLE IF NOT EXISTS tasks (
                  hash TEXT PRIMARY KEY, study TEXT, id TEXT, phase TEXT, family TEXT,
                  payload TEXT, UNIQUE(study,id));
                CREATE TABLE IF NOT EXISTS lessons (
                  id TEXT PRIMARY KEY, study TEXT UNIQUE, profile TEXT, scope TEXT,
                  model TEXT, revision TEXT, content TEXT, expires REAL, active INTEGER);
                CREATE TABLE IF NOT EXISTS receipts (
                  id TEXT PRIMARY KEY, lesson TEXT, profile TEXT, model TEXT, revision TEXT,
                  passed INTEGER, baseline INTEGER, created REAL);
                CREATE TABLE IF NOT EXISTS events (
                  seq INTEGER PRIMARY KEY, study TEXT, kind TEXT, payload TEXT, created REAL);
                CREATE INDEX IF NOT EXISTS tasks_family_study ON tasks(family, study);
                CREATE TRIGGER IF NOT EXISTS reserve_task_family
                  BEFORE INSERT ON tasks
                  WHEN EXISTS (SELECT 1 FROM tasks WHERE family=NEW.family AND study!=NEW.study)
                  BEGIN SELECT RAISE(ABORT,"function family already reserved by another study"); END;
            ''')
            for table in ('tasks', 'receipts', 'events'):
                for action in ('UPDATE', 'DELETE'):
                    db.execute(f'CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action} '
                               f'BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,"immutable receipt"); END')

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _event(self, db, study, kind, payload):
        db.execute('INSERT INTO events(study,kind,payload,created) VALUES(?,?,?,?)',
                   (study, kind, encode(payload), self.clock()))

    @staticmethod
    def _study(db, study_id):
        row = db.execute('SELECT * FROM studies WHERE id=?', (study_id,)).fetchone()
        if row is None:
            raise LookupError('unknown study')
        return row

    def start(self, study_id, *, profile, model, judge_revision, tasks, budget):
        for value in (study_id, profile, model, judge_revision):
            identifier(value)
        budget = checked_budget(budget)
        if type(tasks) is not list or not 6 <= len(tasks) <= 200:
            raise ValueError('six to 200 task records required')
        rows, counts, final_families, development_families = [], {}, set(), set()
        for task in tasks:
            if type(task) is not dict or set(task) != {'id', 'phase', 'family', 'task'}:
                raise ValueError('exact task manifest required')
            tid, family, phase = identifier(task['id']), identifier(task['family']), task['phase']
            if phase not in ('train', 'selection', 'retention', 'final') or type(task['task']) is not dict:
                raise ValueError('valid phase and task payload required')
            # Cosmetic IDs never make an existing fixture fresh. The insertion
            # trigger also reserves its family across studies, including when a
            # new mutation changes the payload hash. Existing evidence stays
            # immutable; repeated family members within one study are allowed.
            payload = encode({k:v for k,v in task['task'].items() if k != 'id'})
            if len(payload.encode()) > 200000:
                raise ValueError('task too large')
            digest = sha256(payload.encode()).hexdigest()
            rows.append((digest, study_id, tid, phase, family, payload))
            counts[phase] = counts.get(phase, 0) + 1
            if phase == 'final':
                final_families.add(family)
            else:
                development_families.add(family)
        if counts.get('selection', 0) < 1 or counts.get('retention', 0) < 1 or len(final_families) < 3:
            raise ValueError('selection, retention and three distinct final families required')
        if final_families & development_families:
            raise ValueError('final families must be disjoint from development families')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO studies VALUES(?,?,?,?,?,?,NULL,NULL)',
                       (study_id, profile, model, judge_revision, budget, 'started'))
            db.executemany('INSERT INTO tasks VALUES(?,?,?,?,?,?)', rows)
            self._event(db, study_id, 'started', dict(profile=profile, model=model,
                        judge_revision=judge_revision, budget=json.loads(budget), counts=counts))
        return self.status(study_id)

    def development(self, study_id):
        """Only these records may reach a proposer; final records are excluded."""
        with self._db() as db:
            self._study(db, study_id)
            return [dict(id=r['id'], phase=r['phase'], family=r['family'], task=json.loads(r['payload']))
                    for r in db.execute("SELECT * FROM tasks WHERE study=? AND phase!='final' ORDER BY rowid", (study_id,))]

    def freeze(self, study_id, lesson):
        if type(lesson) is not str or not 1 <= len(lesson) <= 8192:
            raise ValueError('bounded lesson required')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._study(db, study_id)
            if row['status'] == 'frozen' and row['lesson'] == lesson:
                return
            if row['status'] != 'started':
                raise ValueError('candidate already frozen or study terminal')
            db.execute("UPDATE studies SET status='frozen',lesson=? WHERE id=?", (lesson, study_id))
            self._event(db, study_id, 'candidate_frozen', {'lesson': lesson})

    def complete(self, study_id, *, results, early_stop=False):
        """Record a full host-judged paired experiment after candidate freezing.

        Each result contains task_id, arm, passed, model, budget. A malformed
        or incomplete experiment never becomes an improvement receipt.
        """
        if type(results) is not list or type(early_stop) is not bool:
            raise ValueError('paired result list required')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            study = self._study(db, study_id)
            if study['status'] != 'frozen':
                raise ValueError('frozen unfinished study required')
            all_tasks = {r['id']:r for r in db.execute('SELECT * FROM tasks WHERE study=?', (study_id,))}
            manifest = {tid:r for tid,r in all_tasks.items() if r['phase'] != 'train'}
            paired = {}
            seen_results = set()
            for item in results:
                if type(item) is not dict or set(item) != {'task_id','arm','passed','model','budget'}:
                    raise ValueError('exact judged result schema required')
                tid, arm = item['task_id'], item['arm']
                if tid not in all_tasks or arm not in ('baseline','lesson') or type(item['passed']) is not bool:
                    raise ValueError('unknown task, arm or nonboolean judgment')
                if item['model'] != study['model'] or checked_budget(item['budget']) != study['budget']:
                    raise ValueError('same model and per-arm configured budget required')
                if (tid, arm) in seen_results:
                    raise ValueError('duplicate judged result')
                seen_results.add((tid,arm))
                if all_tasks[tid]['phase'] == 'train':
                    if arm != 'baseline':
                        raise ValueError('training is baseline only')
                    continue
                paired[tid, arm] = item['passed']
            if not early_stop and len(paired) != 2 * len(manifest):
                raise ValueError('complete paired evidence required')
            summary = {}
            for phase in ('selection','retention','final'):
                ids = [tid for tid, r in manifest.items() if r['phase'] == phase]
                observed = [(tid, arm) in paired for tid in ids for arm in ('baseline','lesson')]
                if not any(observed) and early_stop:
                    summary[phase] = dict(tasks=0, baseline_hits=0, lesson_hits=0, wins=0, losses=0, evaluated=False)
                    continue
                if not all(observed):
                    raise ValueError('complete paired phase required')
                base = [paired[tid,'baseline'] for tid in ids]
                learned = [paired[tid,'lesson'] for tid in ids]
                summary[phase] = dict(tasks=len(ids), evaluated=True, baseline_hits=sum(base), lesson_hits=sum(learned),
                    wins=sum(b and not a for a,b in zip(base,learned)),
                    losses=sum(a and not b for a,b in zip(base,learned)))
            if early_stop and (not summary['selection']['evaluated'] or summary['final']['evaluated'] or
                    (summary['selection']['wins'] > 0 and summary['selection']['losses'] == 0
                     and (not summary['retention']['evaluated'] or summary['retention']['losses'] == 0))):
                raise ValueError('early stop requires selection rejection or retention regression; final stays unopened')
            gain = (not early_stop and summary['selection']['wins'] > 0 and summary['selection']['losses'] == 0
                    and summary['retention']['losses'] == 0 and summary['final']['wins'] > 0
                    and summary['final']['losses'] == 0)
            lesson_id = 'lesson-' + sha256(study_id.encode()).hexdigest()[:24] if gain else None
            summary.update(status='observed_gain' if gain else 'no_gain', lesson_id=lesson_id,
                           scope=SCOPE, general_improvement_proven=False)
            if gain:
                db.execute('UPDATE lessons SET active=0 WHERE profile=? AND scope=? AND model=? AND revision=?',
                           (study['profile'], SCOPE, study['model'], study['revision']))
                db.execute('INSERT INTO lessons VALUES(?,?,?,?,?,?,?,?,1)',
                           (lesson_id, study_id, study['profile'], SCOPE, study['model'], study['revision'],
                            study['lesson'], self.clock()+30*86400,))
            db.execute("UPDATE studies SET status='completed',summary=? WHERE id=?", (encode(summary), study_id))
            self._event(db, study_id, 'completed', dict(summary=summary, results=results))
        return summary

    def finish_no_gain(self, study_id, *, results):
        """Close rejected development without spending calls on final holdouts."""
        return self.complete(study_id, results=results, early_stop=True)

    def fail(self, study_id, reason, *, results=None):
        if type(reason) is not str or not 1 <= len(reason) <= 500:
            raise ValueError('sanitized bounded failure reason required')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            study = self._study(db, study_id)
            if study['status'] not in ('started','frozen'):
                raise ValueError('unfinished study required')
            tasks = {r['id']:r for r in db.execute('SELECT * FROM tasks WHERE study=?', (study_id,))}
            results = [] if results is None else results
            if type(results) is not list:
                raise ValueError('partial result list required')
            seen = set()
            for item in results:
                if (type(item) is not dict or set(item) != {'task_id','arm','passed','model','budget'}
                        or item['task_id'] not in tasks or item['arm'] not in ('baseline','lesson')
                        or type(item['passed']) is not bool or item['model'] != study['model']
                        or checked_budget(item['budget']) != study['budget']):
                    raise ValueError('valid matching partial results required')
                key = (item['task_id'],item['arm'])
                if key in seen:
                    raise ValueError('duplicate partial result')
                seen.add(key)
                if tasks[item['task_id']]['phase']=='train' and item['arm']!='baseline':
                    raise ValueError('training is baseline only')
                if study['status']=='started' and tasks[item['task_id']]['phase']!='train':
                    raise ValueError('candidate must freeze before evaluation')
            db.execute("UPDATE studies SET status='failed' WHERE id=?", (study_id,))
            self._event(db, study_id, 'failed', {'reason':reason, 'results':results})

    def recall(self, profile, model, judge_revision, *, scope=SCOPE):
        with self._db() as db:
            row = db.execute('SELECT * FROM lessons WHERE profile=? AND scope=? AND model=? '
                'AND revision=? AND active=1 AND expires>?',
                (profile, scope, model, judge_revision, self.clock())).fetchone()
            return dict(row) if row else None

    def observe(self, episode_id, *, profile, model, judge_revision, lesson_id,
                passed, baseline_passed=None, scope=SCOPE):
        identifier(episode_id)
        if scope != SCOPE:
            raise ValueError('exact repository scope required')
        if type(passed) is not bool or (baseline_passed is not None and type(baseline_passed) is not bool):
            raise ValueError('host boolean judgments required')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT * FROM receipts WHERE id=?', (episode_id,)).fetchone()
            if previous:
                if (previous['lesson'], previous['profile'], previous['model'], previous['revision']) != (lesson_id, profile, model, judge_revision):
                    raise ValueError('episode already bound to another observation')
                return dict(duplicate=True, passed=bool(previous['passed']))
            lesson = db.execute('SELECT * FROM lessons WHERE id=?', (lesson_id,)).fetchone()
            if (not lesson or (lesson['profile'],lesson['scope'],lesson['model'],lesson['revision']) !=
                    (profile,scope,model,judge_revision) or not lesson['active'] or lesson['expires'] <= self.clock()):
                raise ValueError('active exact-scope unexpired lesson required')
            db.execute('INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)',
                       (episode_id,lesson_id,profile,model,judge_revision,int(passed),baseline_passed,self.clock()))
            recent = db.execute('SELECT passed FROM receipts WHERE lesson=? ORDER BY rowid DESC LIMIT 5', (lesson_id,)).fetchall()
            rollback = (baseline_passed is True and not passed) or sum(not r['passed'] for r in recent) >= 2
            if rollback:
                db.execute('UPDATE lessons SET active=0 WHERE id=?', (lesson_id,))
            self._event(db, lesson['study'], 'live_outcome', dict(episode_id=episode_id, lesson_id=lesson_id,
                        passed=passed, baseline_passed=baseline_passed, rollback=rollback))
            return dict(duplicate=False, passed=passed, rollback=rollback)

    def status(self, study_id):
        with self._db() as db:
            row = dict(self._study(db, study_id))
            row['budget'] = json.loads(row['budget'])
            row['summary'] = json.loads(row['summary']) if row['summary'] else None
            return row

    def summary(self):
        """Compact dashboard view; counts refer to the latest completed phase."""
        with self._db() as db:
            latest = db.execute('SELECT * FROM studies ORDER BY rowid DESC LIMIT 1').fetchone()
            active = db.execute('SELECT COUNT(*) FROM lessons WHERE active=1 AND expires>?', (self.clock(),)).fetchone()[0]
            events = db.execute("SELECT kind,payload FROM events ORDER BY seq").fetchall()
        details = json.loads(latest['summary']) if latest and latest['summary'] else {}
        measured = next((details[p] for p in ('final','retention','selection')
                         if details.get(p,{}).get('evaluated')), {})
        failures = [json.loads(e['payload'])['reason'] for e in events if e['kind']=='failed']
        state = details.get('status',latest['status'] if latest else 'not_started')
        state = {'not_started':'not_run','started':'running','frozen':'running',
                 'no_gain':'no_verified_improvement','observed_gain':'observed_final_gain'}.get(state,state)
        return dict(status=state, scope=SCOPE,
                    study_id=latest['id'] if latest else None,
                    baseline_passed=measured.get('baseline_hits',0), learned_passed=measured.get('lesson_hits',0),
                    tasks=measured.get('tasks',0), wins=measured.get('wins',0), losses=measured.get('losses',0),
                    active_lessons=active,
                    rollbacks=sum(bool(json.loads(e['payload']).get('rollback')) for e in events if e['kind']=='live_outcome'),
                    last_error=failures[-1] if failures else '',
                    limitation='Scoped repository fixtures; observed paired gains are not statistical or general improvement proof.')
