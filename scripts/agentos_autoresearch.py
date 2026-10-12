"""Durable, bounded autoresearch orchestration. Caller holds the bridge host lock.

Karpathy's fixed evaluator / experiment ledger / keep-or-discard pattern is
adapted to the existing receipt-bound Hermes study. Waiting is a valid outcome:
this controller never manufactures fresh holdouts or resets call ledgers.
"""
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import time

from nerve_awim.agentos_learning import atomic_json

_spec = importlib.util.spec_from_file_location('_autoresearch_shadow', Path(__file__).with_name('agentos_audit_shadow.py'))
shadow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shadow)
studies = shadow.studies
LIMITATION = 'Experimental simulated-audit skill learning only; no operational activation or general improvement claim.'


def database(host):
    path = host.directory / 'autoresearch.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS config(id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL,profile TEXT NOT NULL);
        INSERT OR IGNORE INTO config(id,enabled,profile) VALUES(1,0,'qa-release');
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,outcome TEXT NOT NULL,result TEXT NOT NULL,created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS inbox(id TEXT PRIMARY KEY,identity TEXT UNIQUE NOT NULL,family TEXT UNIQUE NOT NULL,task TEXT NOT NULL,state TEXT NOT NULL,result TEXT);
        CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable event'); END;
        CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable event'); END;
        CREATE TRIGGER IF NOT EXISTS inbox_no_rewrite BEFORE UPDATE OF id,identity,family,task ON inbox BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        CREATE TRIGGER IF NOT EXISTS inbox_no_delete BEFORE DELETE ON inbox BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        ''')
        columns = {row[1] for row in db.execute('PRAGMA table_info(config)')}
        if 'configured' not in columns:
            db.execute('ALTER TABLE config ADD COLUMN configured INTEGER NOT NULL DEFAULT 0')
    return path


def configure(host, enabled, profile=None):
    if profile is None:
        profile = status(host)['profile']
    if type(enabled) is not bool or type(profile) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', profile) is None:
        raise ValueError('boolean enabled and valid profile required')
    with sqlite3.connect(database(host)) as db:
        db.execute('UPDATE config SET enabled=?,profile=?,configured=1 WHERE id=1', (int(enabled), profile))
    return status(host)


def status(host):
    with sqlite3.connect(database(host)) as db:
        enabled, profile, configured = db.execute('SELECT enabled,profile,configured FROM config').fetchone()
        latest = db.execute('SELECT kind,outcome,result,created FROM events ORDER BY id DESC LIMIT 1').fetchone()
        counts = dict(db.execute('SELECT state,COUNT(*) FROM inbox GROUP BY state'))
        outcomes = dict(db.execute('SELECT outcome,COUNT(*) FROM events GROUP BY outcome'))
    return dict(enabled=bool(enabled), configured=bool(configured), profile=profile, status=(json.loads(latest[2]).get('status', 'enabled') if latest else 'enabled') if enabled else 'paused',
                latest=dict(kind=latest[0], outcome=latest[1], result=json.loads(latest[2]), created=latest[3]) if latest else None,
                inbox=counts, outcomes=outcomes, remaining_sessions=studies.remaining(host),
                activation_authorized=False, limitation=LIMITATION)


def submit(host, task):
    """Admit host-supplied evidence, not model-generated holdouts. No inference."""
    if type(task) is not dict or set(task) != {'id', 'family', 'bundle'}:
        raise ValueError('exact id,family,bundle required')
    for key in ('id', 'family'):
        if type(task[key]) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}', task[key]) is None:
            raise ValueError('invalid task ' + key)
    shadow.oracle.validate_bundle(task['bundle'])
    encoded = studies.encode(task)
    if len(encoded.encode()) > 1_000_000:
        raise ValueError('task exceeds size limit')
    identity = shadow.cohort.canonical_identity(task)
    known = [row for rows in shadow.cohort.cohort()['splits'].values() for row in rows] + shadow.development_cases()
    if any(identity == shadow.cohort.canonical_identity(row) or task['family'] == row['family'] for row in known):
        return dict(status='reused_evidence', activation_authorized=False)
    with sqlite3.connect(database(host)) as db:
        changed = db.execute("INSERT OR IGNORE INTO inbox VALUES(?,?,?,?,'pending',NULL)",
                             (task['id'], identity, task['family'], encoded)).rowcount
    return dict(status='queued' if changed else 'reused_evidence', activation_authorized=False)


def _event(host, kind, outcome, result):
    with sqlite3.connect(database(host)) as db:
        db.execute('INSERT INTO events(kind,outcome,result,created) VALUES(?,?,?,?)',
                   (kind, outcome, studies.encode(result), int(time.time())))
    return dict(kind=kind, outcome=outcome, result=result, activation_authorized=False)


def _export(host, candidate):
    # Immutable version directory is deliberately outside the installed Hermes skills.
    directory = host.directory / 'autoresearch-skills' / candidate['id']
    directory.mkdir(parents=True, exist_ok=True)
    content = ('---\nname: nerve-audit-experimental\ndescription: Experimental advice for simulated audit evidence only.\n---\n\n'
               '# Experimental audit advice\n\n'
               'Use only in isolated paired evaluation. Not approved for operational use.\n\n'
               + candidate['lesson'] + '\n')
    target = directory / 'SKILL.md'
    if target.exists() and target.read_text() != content:
        raise ValueError('experimental skill artifact mismatch')
    if not target.exists():
        with target.open('x') as handle:
            handle.write(content)
    atomic_json(directory / 'provenance.json', dict(study_id=candidate['id'], revision=candidate['revision'],
                model=candidate['model'], profile=candidate['profile'], lesson_sha256=studies.digest(candidate['lesson']),
                activation_authorized=False, limitation=LIMITATION))
    state = next((row['state'] for row in shadow.status(host)['candidates'] if row['study_id'] == candidate['id']), 'ineligible')
    atomic_json(directory / 'eligibility.json', dict(status=state, checked_at=int(time.time()), activation_authorized=False))
    return str(target)



def _refresh_exports(host, shadow_state=None):
    shadow_state = shadow_state or shadow.status(host)
    for exported in (host.directory / 'autoresearch-skills').glob('audit-*/SKILL.md'):
        state = next((row['state'] for row in shadow_state['candidates'] if row['study_id'] == exported.parent.name), 'ineligible')
        atomic_json(exported.parent / 'eligibility.json', dict(status=state, checked_at=int(time.time()), activation_authorized=False))


def tick(host, native):
    """One study OR one shadow pair; scheduled caller supplies repetition/backoff."""
    current = status(host)
    if not current['enabled']:
        return dict(status='paused', activation_authorized=False)
    path = database(host)
    # A process crash must never silently replay exposed evidence.
    with sqlite3.connect(path) as db:
        interrupted = db.execute("UPDATE inbox SET state='failed',result=? WHERE state='running'",
                                 (studies.encode(dict(reason='interrupted_no_replay')),)).rowcount
    if interrupted:
        # Let the authoritative shadow ledger revoke interrupted candidates without calls.
        with sqlite3.connect(shadow.database(host)) as db:
            for (candidate,) in db.execute("SELECT candidate FROM episodes WHERE state='running'").fetchall():
                db.execute("UPDATE candidates SET state='revoked',reason='interrupted_episode' WHERE id=?", (candidate,))
            db.execute("UPDATE episodes SET state='failed',result=? WHERE state='running'", (studies.encode(dict(reason='interrupted_no_replay')),))
        _refresh_exports(host)
        return _event(host, 'recovery', 'crash', dict(status='interrupted_no_replay', tasks=interrupted))
    candidate = shadow._candidate(host)
    shadow_state = shadow.status(host)
    # Exported advice remains an immutable experimental record; eligibility is live.
    _refresh_exports(host, shadow_state)
    eligible = candidate and any(row['study_id'] == candidate['id'] and row['state'] in ('active', 'eligible_unmonitored') for row in shadow_state['candidates'])
    if eligible:
        try:
            artifact = _export(host, candidate)
        except (OSError, ValueError):
            return _event(host, 'artifact', 'crash', dict(status='artifact_integrity_error'))
        with sqlite3.connect(path) as db:
            row = db.execute("SELECT id,task FROM inbox WHERE state='pending' ORDER BY rowid LIMIT 1").fetchone()
        if row is None:
            return _event(host, 'wait', 'wait', dict(status='awaiting_fresh_evidence', experimental_skill=artifact))
        if studies.remaining(host) < 2:
            return _event(host, 'wait', 'wait', dict(status='waiting_budget', required_sessions=2, next_budget_reset_at=(int(time.time()) // 86400 + 1) * 86400))
        with sqlite3.connect(path) as db:
            db.execute("UPDATE inbox SET state='running' WHERE id=?", (row[0],))
        try:
            result = shadow.monitor(host, native, json.loads(row[1]), study_id=candidate['id'])
            atomic_json(Path(artifact).parent / 'eligibility.json', dict(status=result['status'], checked_at=int(time.time()), activation_authorized=False))
            outcome = 'keep' if result['status'] == 'active' else 'discard'
        except Exception as error:
            result = dict(status='failed', reason=type(error).__name__)
            outcome = 'crash'
            # Leave running for the next tick's authoritative no-replay recovery.
            return _event(host, 'shadow', outcome, result)
        with sqlite3.connect(path) as db:
            db.execute('UPDATE inbox SET state=?,result=? WHERE id=?',
                       ('pending' if result['status'] == 'deferred_daily_budget' else 'completed', studies.encode(result), row[0]))
        if result['status'] == 'deferred_daily_budget':
            outcome = 'wait'
        return _event(host, 'shadow', outcome, result)
    existing = studies.status(host)
    if existing['status'] == 'running':
        with sqlite3.connect(studies.database(host)) as db:
            db.execute("UPDATE studies SET status='failed',result=? WHERE status='running'", (studies.encode(dict(status='failed', reason='interrupted_no_replay')),))
        return _event(host, 'recovery', 'crash', dict(status='interrupted_no_replay'))
    if existing['status'] != 'not_run':
        # Fixed holdouts have been consumed: never hunt for a lucky retry.
        return _event(host, 'wait', 'wait', dict(status='awaiting_fresh_cohort', study_status=existing['status'], candidate_status=shadow_state['status']))
    try:
        result = studies.study(host, native, profile=current['profile'])
    except Exception as error:
        return _event(host, 'study', 'crash', dict(status='failed', reason=type(error).__name__))
    outcome = ('keep' if result['status'] == 'shadow_accepted' else 'wait' if result['status'] in
               ('queued_budget', 'queued_revision_mismatch', 'no_fresh_tasks') else 'crash' if result['status'] == 'failed' else 'discard')
    if outcome == 'keep':
        candidate = shadow._candidate(host, result.get('study_id'))
        if candidate is None:
            return _event(host, 'study', 'discard', dict(status='receipt_verification_failed'))
        result['experimental_skill'] = _export(host, candidate)
    return _event(host, 'study', outcome, result)
