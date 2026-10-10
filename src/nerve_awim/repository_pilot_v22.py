"""Persistent, sealed studies for local read-only repository shadow pilots."""
from hashlib import sha256
import json
from pathlib import Path

from .agent_learning_v12 import AgentTask
from .governed_learning_v20 import _id, _json
from .repository_agents_v20 import CONTEXT


def file_task(root, name):
    root = Path(root).resolve(strict=True)
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root) or path.suffix != '.py' or not path.is_file():
        raise ValueError('select a Python file within the repository root')
    with path.open('rb') as handle:
        data = handle.read(16385)
    if len(data) > 16384:
        raise ValueError('source exceeds research payload budget')
    return AgentTask('source-' + sha256(data).hexdigest(), CONTEXT, data.decode('utf-8'))


class RepositoryPilot:
    """Trusted host runner; local capabilities are not remote authentication.

    Plans pin input bytes and roles. New studies may reuse training evidence but
    must supply unused holdouts. Source identity is canonical repository path;
    renamed/semantically related files still require independent human curation.
    """
    def __init__(self, engine, root):
        if set(engine._baseline) != {CONTEXT}:
            raise ValueError('repository inventory registry required')
        self.engine, self.root = engine, Path(root).resolve(strict=True)
        with engine._db() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS gl_pilot_sources (
                    tenant TEXT, agent TEXT, repository TEXT, path TEXT, split TEXT,
                    PRIMARY KEY(tenant,agent,repository,path));
                CREATE TABLE IF NOT EXISTS gl_pilot_studies (
                    tenant TEXT, agent TEXT, study TEXT, manifest TEXT,
                    manifest_hash TEXT, candidate TEXT,
                    PRIMARY KEY(tenant,agent,study));
            ''')

    def plan(self, actor, *, study, repository, train, holdout):
        scope = self.engine._scope(actor, 'evaluator', 'operator')
        _id(study)
        _id(repository)
        if not 3 <= len(train) <= 128 or not 5 <= len(holdout) <= 128:
            raise ValueError('plan needs 3-128 training and 5-128 held-out files')
        manifest = {'repository': repository, 'train': [], 'holdout': []}
        prepared, paths, hashes = [], set(), set()
        for split, names in (('train', train), ('holdout', holdout)):
            for name in names:
                task = file_task(self.root, name)
                task, digest = self.engine._task(task)
                path = (self.root / name).resolve().relative_to(self.root).as_posix()
                if path in paths or digest in hashes:
                    raise ValueError('duplicate source path or content within study')
                paths.add(path)
                hashes.add(digest)
                manifest[split].append({'path': path, 'payload_hash': digest, 'task_id': task.task_id})
                prepared.append((split, path, task, digest))
        encoded = _json(manifest)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            self.engine._state(con, scope)
            for split, path, task, digest in prepared:
                prior = con.execute('''SELECT split FROM gl_pilot_sources
                    WHERE tenant=? AND agent=? AND repository=? AND path=?''',
                    (*scope, repository, path)).fetchone()
                if prior and prior['split'] != split:
                    raise ValueError('source path cannot change training/holdout assignment')
                seen = con.execute('''SELECT split FROM gl_tasks WHERE tenant=? AND agent=?
                    AND (task_id=? OR payload_hash=?)''', (*scope, task.task_id, digest)).fetchone()
                reserved = con.execute('''SELECT 1 FROM gl_holdout_reservations WHERE tenant=?
                    AND agent=? AND (task_id=? OR payload_hash=?)''',
                    (*scope, task.task_id, digest)).fetchone()
                if (split == 'holdout' and (seen or reserved)) or (split == 'train' and (
                        reserved or (seen and seen['split'] != 'train'))):
                    raise ValueError('holdout must be unused and isolated from training')
                con.execute('INSERT OR IGNORE INTO gl_pilot_sources VALUES(?,?,?,?,?)',
                            (*scope, repository, path, split))
                if split == 'holdout':
                    con.execute('INSERT INTO gl_holdout_reservations VALUES(?,?,?,?)',
                                (*scope, task.task_id, digest))
            con.execute('INSERT INTO gl_pilot_studies VALUES(?,?,?,?,?,NULL)',
                        (*scope, study, encoded, sha256(encoded.encode()).hexdigest()))
        return self.review(actor, study)

    def _study(self, con, scope, study):
        self.engine._state(con, scope)
        row = con.execute('SELECT * FROM gl_pilot_studies WHERE tenant=? AND agent=? AND study=?',
                          (*scope, study)).fetchone()
        if not row:
            raise LookupError('study not found in this scope')
        if sha256(row['manifest'].encode()).hexdigest() != row['manifest_hash']:
            raise ValueError('manifest integrity failure')
        return row

    def _tasks(self, manifest, split):
        tasks = []
        for entry in manifest[split]:
            task, digest = self.engine._task(file_task(self.root, entry['path']))
            if task.task_id != entry['task_id'] or digest != entry['payload_hash']:
                raise ValueError('source changed since planning; create a new reviewed study')
            tasks.append(task)
        return tasks

    def collect(self, actor, study, shadow):
        scope = self.engine._scope(actor, 'trainer')
        if shadow.engine is not self.engine or self.engine._scope(shadow.trainer, 'trainer') != scope:
            raise PermissionError('shadow adapter must match study scope and engine')
        if shadow.pending:
            raise ValueError('drain earlier observations before collecting a study')
        with self.engine._db() as con:
            row = self._study(con, scope, study)
            if row['candidate']:
                raise ValueError('study already frozen')
        tasks = self._tasks(json.loads(row['manifest']), 'train')
        counts = {'recorded': 0, 'rejected': 0, 'failed': 0, 'runtime_errors': 0}
        for task in tasks:
            try:
                shadow.execute(task)
            except Exception:
                counts['runtime_errors'] += 1
            result = shadow.drain()
            for key in ('recorded', 'rejected', 'failed'):
                counts[key] += result[key]
        return counts

    def freeze(self, actor, study):
        scope = self.engine._scope(actor, 'trainer')
        with self.engine._db() as con:
            row = self._study(con, scope, study)
            if row['candidate']:
                return row['candidate']
            # Require complete judged evidence for every planned training task.
            for entry in json.loads(row['manifest'])['train']:
                count = con.execute('''SELECT COUNT(*) FROM gl_outcomes WHERE tenant=?
                    AND agent=? AND task_id=?''', (*scope, entry['task_id'])).fetchone()[0]
                if count != len(self.engine._registry):
                    raise ValueError('complete training evidence required for planned files')
        candidate = self.engine.freeze_candidate(actor)
        with self.engine._db() as con:
            # Concurrent freezes may create an unused candidate, never replace one.
            con.execute('''UPDATE gl_pilot_studies SET candidate=? WHERE tenant=? AND agent=?
                AND study=? AND candidate IS NULL''', (candidate, *scope, study))
            return self._study(con, scope, study)['candidate']

    def evaluate(self, actor, study):
        scope = self.engine._scope(actor, 'evaluator')
        with self.engine._db() as con:
            row = self._study(con, scope, study)
        if not row['candidate']:
            raise ValueError('freeze study before opening held-out evaluation')
        tasks = self._tasks(json.loads(row['manifest']), 'holdout')
        return self.engine.evaluate_candidate(actor, row['candidate'], tasks)

    def review(self, actor, study):
        scope = self.engine._scope(actor, 'auditor', 'evaluator', 'operator')
        with self.engine._db() as con:
            row = self._study(con, scope, study)
            state = self.engine._state(con, scope)
            candidate = self.engine._candidate(con, scope, row['candidate']) if row['candidate'] else None
        decision = 'collect_training'
        if candidate:
            decision = 'await_independent_evaluation'
            if candidate['base_generation'] != state['generation']:
                decision = 'stale_candidate_reject_rollout'
            elif candidate['status'] == 'passed':
                decision = 'quality_passed_operator_review_required'
            elif candidate['status'] != 'frozen':
                decision = 'reject_rollout'
        manifest = json.loads(row['manifest'])
        return {'study': study, 'manifest_sha256': row['manifest_hash'],
                'training_files': len(manifest['train']), 'holdout_files': len(manifest['holdout']),
                'candidate': row['candidate'], 'recommendation': decision,
                'candidate_status': candidate['status'] if candidate else None,
                'evaluation': json.loads(candidate['evaluation']) if candidate and candidate['evaluation'] else None,
                'active_release': state['active'], 'generation': state['generation'],
                'automatic_deployment': False,
                'remaining_review': ['independent data provenance', 'latency and cost budgets',
                                     'host authentication and rollout/rollback plan']}
