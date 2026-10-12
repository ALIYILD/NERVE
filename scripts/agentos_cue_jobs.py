"""Immutable CCE jobs in the existing autoresearch ledger; no scheduler/providers.

The orchestrator holds its existing host lock. Recovery is explicit at locked
startup, never part of worker tick: interrupted work is abandoned, never replayed.
Trusted adapters must enforce durable provider/daily/cost budgets and timeouts;
their preflight checks readiness without performing inference. JSON cannot name
Python imports, install an adapter, or authorize activation.
"""
from dataclasses import asdict, fields
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

from nerve_awim.cue_dataset import parse_dataset_json
from nerve_awim.cue_evaluation import ModelParity
from nerve_awim.cue_host import CueHost

MAX_SPEC_BYTES = 5 * 1024 * 1024
_KEYS = {'job_id', 'profile', 'dataset', 'model', 'generator_id', 'evaluator_id',
         'adapter_id', 'adapter_revision', 'max_calls', 'max_cost_usd',
         'discovery_cost_cap_usd', 'per_call_cost_cap_usd', 'permission_granted'}
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/@+\-]{0,127}\Z')


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate job JSON key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonfinite job JSON')


def load_spec(path):
    fd = os.open(os.fspath(path), os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SPEC_BYTES:
            raise ValueError('bounded regular job JSON file required')
        raw = handle.read(MAX_SPEC_BYTES + 1)
    if len(raw) > MAX_SPEC_BYTES:
        raise ValueError('job JSON exceeds size cap')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError('valid bounded UTF-8 job JSON required') from None
    if type(value) is not dict:
        raise ValueError('job object required')
    return value


def _path(host):
    return host.directory / 'autoresearch.sqlite3'


def _database(host):
    path = _path(host)
    with sqlite3.connect(path) as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,outcome TEXT NOT NULL,result TEXT NOT NULL,created INTEGER NOT NULL);
          CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable event'); END;
          CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable event'); END;
          CREATE TABLE IF NOT EXISTS cce_jobs(
            job_id TEXT PRIMARY KEY,profile TEXT NOT NULL,dataset_digest TEXT NOT NULL,
            spec TEXT NOT NULL,spec_digest TEXT NOT NULL,state TEXT NOT NULL,
            waiting_reason TEXT,result TEXT,created INTEGER NOT NULL,
            UNIQUE(profile,dataset_digest),CHECK(state IN('pending','running','completed','failed','abandoned','cancelled')));
          CREATE TRIGGER IF NOT EXISTS cce_jobs_no_rewrite BEFORE UPDATE OF job_id,profile,dataset_digest,spec,spec_digest,created ON cce_jobs BEGIN SELECT RAISE(ABORT,'immutable cue job'); END;
          CREATE TRIGGER IF NOT EXISTS cce_jobs_no_delete BEFORE DELETE ON cce_jobs BEGIN SELECT RAISE(ABORT,'immutable cue job'); END;
          CREATE TRIGGER IF NOT EXISTS cce_jobs_state BEFORE UPDATE OF state ON cce_jobs
            WHEN NOT (OLD.state=NEW.state OR (OLD.state='pending' AND NEW.state IN('running','cancelled')) OR
              (OLD.state='running' AND NEW.state IN('completed','failed','abandoned')))
            BEGIN SELECT RAISE(ABORT,'invalid cue job transition'); END;
        ''')
    return path


def _event(db, outcome, result):
    db.execute('INSERT INTO events(kind,outcome,result,created) VALUES(?,?,?,?)',
               ('cce_job', outcome, _json(result), int(time.time())))


def _validated(spec):
    if type(spec) is not dict or set(spec) != _KEYS:
        raise ValueError('strict cue job schema required')
    for key in ('job_id', 'profile', 'generator_id', 'evaluator_id', 'adapter_id', 'adapter_revision'):
        if type(spec[key]) is not str or not _ID.fullmatch(spec[key]):
            raise ValueError('bounded cue job identifiers required')
    if spec['permission_granted'] is not True or spec['generator_id'] == spec['evaluator_id']:
        raise ValueError('explicit permission and independent evaluator required')
    try:
        encoded = _json(spec)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError('finite JSON job data required') from None
    if len(encoded.encode()) > MAX_SPEC_BYTES:
        raise ValueError('job exceeds size cap')
    frozen = parse_dataset_json(_json(spec['dataset']))
    if frozen.schema_version != 2 or len(frozen.holdout_tasks) < 30:
        raise ValueError('schema 2 dataset with at least 30 holdout tasks required')
    if type(spec['model']) is not dict or set(spec['model']) != {f.name for f in fields(ModelParity)}:
        raise ValueError('complete exact model configuration required')
    model = ModelParity(**spec['model'])
    calls = 1 + 2 * (len(frozen.selection_tasks) + len(frozen.regression_tasks) + len(frozen.holdout_tasks))
    if type(spec['max_calls']) is not int or not calls <= spec['max_calls'] <= 20000:
        raise ValueError('complete bounded cycle call budget required')
    for key in ('max_cost_usd', 'discovery_cost_cap_usd', 'per_call_cost_cap_usd'):
        amount = spec[key]
        if type(amount) not in (int, float) or not math.isfinite(amount) or amount <= 0:
            raise ValueError('finite positive job budgets required')
    if spec['discovery_cost_cap_usd'] + (calls - 1) * spec['per_call_cost_cap_usd'] > spec['max_cost_usd']:
        raise ValueError('worst-case complete cycle must fit cost budget')
    return frozen, model, encoded


def _profile_state(host, profile_name, model):
    profiles, state = CueHost(host)._config()
    profile = profiles.get(profile_name)
    if profile is None:
        return 'waiting_for_profile'
    if (model.profile_key != profile.key or any(getattr(model, key) != getattr(profile, key)
            for key in ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision'))):
        return 'waiting_for_profile'
    return None if state == 'enabled' else 'disabled'


def submit(host, spec):
    frozen, model, encoded = _validated(spec)
    if _profile_state(host, spec['profile'], model) == 'waiting_for_profile':
        raise ValueError('configured exact CCE profile and model required')
    digest = sha256(encoded.encode()).hexdigest()
    with sqlite3.connect(_database(host)) as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT spec_digest,state FROM cce_jobs WHERE job_id=?', (spec['job_id'],)).fetchone()
        if existing:
            if existing[0] != digest:
                raise ValueError('job ID cannot be rewritten')
            return {'status': 'already_submitted', 'job_id': spec['job_id'], 'state': existing[1], 'activation_authorized': False}
        if db.execute('SELECT 1 FROM cce_jobs WHERE profile=? AND dataset_digest=?', (spec['profile'], frozen.digest)).fetchone():
            return {'status': 'reused_dataset', 'activation_authorized': False}
        if db.execute("SELECT COUNT(*) FROM cce_jobs WHERE state IN('pending','running')").fetchone()[0] >= 32:
            raise ValueError('pending cue job capacity exhausted')
        db.execute("INSERT INTO cce_jobs VALUES(?,?,?,?,?,'pending',NULL,NULL,?)",
                   (spec['job_id'], spec['profile'], frozen.digest, encoded, digest, int(time.time())))
        result = {'status': 'queued', 'job_id': spec['job_id'], 'dataset_digest': frozen.digest, 'activation_authorized': False}
        _event(db, 'queued', result)
    return result


def status(host):
    result = {'counts': {}, 'jobs': [], 'activation_authorized': False}
    path = _path(host)
    if not path.exists():
        return result
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cce_jobs'").fetchone():
            return result
        result['counts'] = dict(db.execute('SELECT state,COUNT(*) FROM cce_jobs GROUP BY state'))
        for row in db.execute('SELECT job_id,profile,dataset_digest,state,waiting_reason,result FROM cce_jobs ORDER BY created DESC,rowid DESC LIMIT 64'):
            summary = dict(zip(('job_id', 'profile', 'dataset_digest', 'state', 'waiting_reason'), row[:5]))
            if row[5]:
                stored = json.loads(row[5])
                summary['outcome'] = {key: stored[key] for key in ('status', 'reason', 'error_category') if key in stored}
                if type(stored.get('result')) is dict:
                    summary['outcome']['result'] = {key: stored['result'][key] for key in
                        ('state','reason','candidate','attempted_calls','known_cost_usd','dataset_digest',
                         'selection_digest','regression_digest','holdout_digest','memory_id','activated',
                         'learning_context_digest','learning_context_candidates')
                        if key in stored['result']}
            result['jobs'].append(summary)
    return result



def cancel(host, job_id):
    """Cancel only pending work. Identity remains consumed; no candidate is revoked."""
    if type(job_id) is not str or not _ID.fullmatch(job_id):
        raise ValueError('bounded job ID required')
    if not _path(host).exists():
        raise LookupError('cue job not found')
    with sqlite3.connect(_database(host)) as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT state FROM cce_jobs WHERE job_id=?', (job_id,)).fetchone()
        if existing is None:
            raise LookupError('cue job not found')
        if existing[0] != 'pending':
            raise ValueError('only pending cue jobs may be cancelled')
        result = {'status': 'cancelled', 'job_id': job_id, 'activation_authorized': False}
        db.execute("UPDATE cce_jobs SET state='cancelled',waiting_reason=NULL,result=? WHERE job_id=?",
                   (_json(result), job_id))
        _event(db, 'cancelled', result)
    return result


def recover(host):
    """Caller MUST hold the orchestrator host lock; never call from worker tick."""
    if not _path(host).exists():
        return {'status': 'recovered', 'abandoned': [], 'activation_authorized': False}
    with sqlite3.connect(_database(host)) as db:
        db.execute('BEGIN IMMEDIATE')
        abandoned = [row[0] for row in db.execute("SELECT job_id FROM cce_jobs WHERE state='running'")]
        for job_id in abandoned:
            result = {'status': 'abandoned', 'job_id': job_id, 'reason': 'interrupted_no_replay', 'activation_authorized': False}
            db.execute("UPDATE cce_jobs SET state='abandoned',waiting_reason=NULL,result=? WHERE job_id=?", (_json(result), job_id))
            _event(db, 'abandoned', result)
    return {'status': 'recovered', 'abandoned': abandoned, 'activation_authorized': False}


def tick(host, adapters=None):
    """Claim at most one job. No configured adapter/budget means wait, not inference."""
    if not status(host)['counts'].get('pending'):
        return None
    with sqlite3.connect(_database(host)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM cce_jobs WHERE state='pending' ORDER BY created,rowid LIMIT 1").fetchone()
        if row is None:
            return None
        def wait(reason):
            db.execute('UPDATE cce_jobs SET waiting_reason=? WHERE job_id=?', (reason, row['job_id']))
            return {'status': reason, 'job_id': row['job_id'], 'activation_authorized': False}
        has_config = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='config'").fetchone()
        config = db.execute('SELECT enabled FROM config WHERE id=1').fetchone() if has_config else None
        if config is None or config['enabled'] != 1:
            return wait('disabled')
        spec = json.loads(row['spec'])
        frozen, model, encoded = _validated(spec)
        if (sha256(encoded.encode()).hexdigest() != row['spec_digest']
                or spec['job_id'] != row['job_id'] or spec['profile'] != row['profile']
                or frozen.digest != row['dataset_digest']):
            db.execute("UPDATE cce_jobs SET state='running' WHERE job_id=?", (row['job_id'],))
            failure = {'status':'failed','job_id':row['job_id'],'reason':'job_integrity_failed','activation_authorized':False}
            db.execute("UPDATE cce_jobs SET state='failed',waiting_reason=NULL,result=? WHERE job_id=?",
                       (_json(failure),row['job_id']))
            _event(db,'failed',failure)
            return failure
        profile_state = _profile_state(host, row['profile'], model)
        if profile_state:
            return wait(profile_state)
        adapter = adapters.get(spec['adapter_id']) if type(adapters) is dict else None
        if type(adapter) is not dict or not all(callable(adapter.get(name)) for name in ('discovery_execute', 'provider', 'judge')):
            return wait('waiting_for_adapter')
        if adapter.get('revision') != spec['adapter_revision']:
            return wait('waiting_for_adapter_revision')
        if not callable(adapter.get('preflight')):
            return wait('waiting_for_budget')
        admission = {'job_id': spec['job_id'], 'profile': spec['profile'], 'dataset_digest': frozen.digest,
                     'model': asdict(model), **{name: spec[name] for name in
                     ('max_calls', 'max_cost_usd', 'discovery_cost_cap_usd', 'per_call_cost_cap_usd')}}
        try:
            ready = adapter['preflight'](host, admission)
        except Exception:
            ready = False
        if ready is not True:
            return wait('waiting_for_budget')
        db.execute("UPDATE cce_jobs SET state='running',waiting_reason=NULL WHERE job_id=?", (row['job_id'],))
        _event(db, 'running', {'status': 'running', 'job_id': row['job_id'], 'activation_authorized': False})
    # Running claim committed before the first discovery/provider callback.
    try:
        result = CueHost(host).run_dataset_cycle(spec['profile'], frozen, model=model,
            **{name: spec[name] for name in ('generator_id', 'evaluator_id', 'max_calls', 'max_cost_usd',
                'discovery_cost_cap_usd', 'per_call_cost_cap_usd', 'permission_granted')},
            **{name: adapter[name] for name in ('discovery_execute', 'provider', 'judge')})
        keys = ('state', 'reason', 'candidate', 'attempted_calls', 'known_cost_usd', 'dataset_digest',
                'selection_digest', 'regression_digest', 'holdout_digest', 'memory_id', 'activated',
                'learning_context_digest', 'learning_context_candidates')
        safe = {key: result[key] for key in keys if key in result}
        state = 'failed' if result['state'] == 'blocked' else 'completed'
        outcome = {'status': state, 'job_id': spec['job_id'], 'result': safe, 'activation_authorized': False}
    except Exception as error:
        state = 'failed'
        outcome = {'status': state, 'job_id': spec['job_id'], 'reason': 'cycle_exception',
                   'error_category': type(error).__name__[:80], 'activation_authorized': False}
    with sqlite3.connect(_database(host)) as db:
        db.execute('BEGIN IMMEDIATE')
        changed = db.execute("UPDATE cce_jobs SET state=?,result=? WHERE job_id=? AND state='running'",
                             (state, _json(outcome), row['job_id'])).rowcount
        if changed != 1:
            raise RuntimeError('cue job claim lost; no replay allowed')
        _event(db, state, outcome)
    return outcome
