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
import sys
import time

from nerve_awim.agentos_learning import atomic_json

_spec = importlib.util.spec_from_file_location('_autoresearch_shadow', Path(__file__).with_name('agentos_audit_shadow.py'))
shadow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shadow)
studies = shadow.studies
_registry_spec = importlib.util.spec_from_file_location('_autoresearch_registry', Path(__file__).with_name('agentos_cohort_registry.py'))
registry = importlib.util.module_from_spec(_registry_spec)
_registry_spec.loader.exec_module(registry)
_runner_spec = importlib.util.spec_from_file_location('_autoresearch_cohort_runner', Path(__file__).with_name('agentos_cohort_study.py'))
cohort_runner = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(cohort_runner)
# Share one module identity with the bridge and injected trusted adapter registry.
cue_jobs = sys.modules.get('agentos_cue_jobs')
if cue_jobs is None:
    _cue_spec = importlib.util.spec_from_file_location('agentos_cue_jobs', Path(__file__).with_name('agentos_cue_jobs.py'))
    cue_jobs = importlib.util.module_from_spec(_cue_spec)
    sys.modules['agentos_cue_jobs'] = cue_jobs
    _cue_spec.loader.exec_module(cue_jobs)
LIMITATION = 'Experimental audit and explicitly queued CCE research only; no operational activation or general improvement claim.'


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
        CREATE TABLE IF NOT EXISTS research_findings(
          fingerprint TEXT PRIMARY KEY,origin TEXT NOT NULL,source_digest TEXT NOT NULL,
          profile TEXT NOT NULL,category TEXT NOT NULL,metadata TEXT NOT NULL,created INTEGER NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS research_findings_source ON research_findings(origin,source_digest);
        CREATE TRIGGER IF NOT EXISTS research_findings_no_update BEFORE UPDATE ON research_findings
          BEGIN SELECT RAISE(ABORT,'immutable research finding'); END;
        CREATE TRIGGER IF NOT EXISTS research_findings_no_delete BEFORE DELETE ON research_findings
          BEGIN SELECT RAISE(ABORT,'immutable research finding'); END;
        CREATE TABLE IF NOT EXISTS finding_reviews(
          id INTEGER PRIMARY KEY,fingerprint TEXT NOT NULL,review TEXT NOT NULL,
          digest TEXT UNIQUE NOT NULL,created INTEGER NOT NULL);
        CREATE TRIGGER IF NOT EXISTS finding_reviews_no_update BEFORE UPDATE ON finding_reviews
          BEGIN SELECT RAISE(ABORT,'immutable finding review'); END;
        CREATE TRIGGER IF NOT EXISTS finding_reviews_no_delete BEFORE DELETE ON finding_reviews
          BEGIN SELECT RAISE(ABORT,'immutable finding review'); END;
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
                registered_cohorts=registry.status(host),
                registered_study=cohort_runner.status(host), cce_jobs=cue_jobs.status(host),
                research_findings=finding_status(host),
                activation_authorized=False, limitation=LIMITATION)


def finding_status(host):
    """Local metadata only; findings are research leads, never evaluation gold."""
    with sqlite3.connect(database(host)) as db:
        count = db.execute('SELECT COUNT(*) FROM research_findings').fetchone()[0]
        rows = db.execute('SELECT fingerprint,origin,profile,category FROM research_findings '
                          'ORDER BY created DESC,rowid DESC LIMIT 20').fetchall()
        pending = db.execute('SELECT COUNT(*) FROM research_findings f WHERE NOT EXISTS '
            '(SELECT 1 FROM finding_reviews r WHERE r.fingerprint=f.fingerprint)').fetchone()[0]
        dispositions = dict(db.execute("SELECT json_extract(review,'$.disposition'),COUNT(*) FROM finding_reviews "
            'WHERE id IN (SELECT MAX(id) FROM finding_reviews GROUP BY fingerprint) GROUP BY 1'))
        latest = []
        for r in rows:
            review = db.execute('SELECT review,digest FROM finding_reviews WHERE fingerprint=? '
                                'ORDER BY id DESC LIMIT 1',(r[0],)).fetchone()
            latest.append(dict(fingerprint=r[0],origin=r[1],profile=r[2],category=r[3],
                disposition=json.loads(review[0])['disposition'] if review else 'unreviewed',
                review_digest=review[1] if review else None))
    return dict(count=count, pending_review=pending, dispositions=dispositions, latest=latest,
                status='awaiting_host_review' if pending else ('reviewed' if count else 'empty'),
                benchmark_gold=False, activation_authorized=False)


def review_finding(host, review):
    """Trusted local triage only. Caller holds host lock; no release authority.

    Reviews are append-only and compare the previous digest to prevent stale
    operators overwriting newer conclusions. Reasons are never model context.
    """
    keys = {'fingerprint','source_record_digest','previous_review','disposition','reviewer','reason'}
    if type(review) is not dict or set(review) != keys:
        raise ValueError('exact finding review fields required')
    for key in ('fingerprint','source_record_digest'):
        if type(review[key]) is not str or re.fullmatch(r'[a-f0-9]{64}',review[key]) is None:
            raise ValueError('invalid '+key)
    previous = review['previous_review']
    if previous is not None and (type(previous) is not str or re.fullmatch(r'[a-f0-9]{64}',previous) is None):
        raise ValueError('invalid previous review')
    if review['disposition'] not in ('investigate','monitor','closed_no_action'):
        raise ValueError('invalid disposition')
    for key,limit in (('reviewer',160),('reason',2000)):
        value = review[key]
        if type(value) is not str or not value.strip() or len(value.encode()) > limit or any(ord(c)<32 for c in value):
            raise ValueError('invalid '+key)
    digest = studies.digest(review)
    with sqlite3.connect(database(host)) as db:
        db.execute('BEGIN IMMEDIATE')
        source = db.execute('SELECT metadata FROM research_findings WHERE fingerprint=?',(review['fingerprint'],)).fetchone()
        if source is None or json.loads(source[0])['source_record_digest'] != review['source_record_digest']:
            raise ValueError('unknown or mismatched finding')
        latest = db.execute('SELECT digest FROM finding_reviews WHERE fingerprint=? ORDER BY id DESC LIMIT 1',
                            (review['fingerprint'],)).fetchone()
        if previous != (latest[0] if latest else None):
            raise ValueError('stale finding review')
        db.execute('INSERT INTO finding_reviews(fingerprint,review,digest,created) VALUES(?,?,?,?)',
                   (review['fingerprint'],studies.encode(review),digest,int(time.time())))
    return dict(status='finding_reviewed',review_digest=digest,provider_calls=0,
                benchmark_gold=False,activation_authorized=False)


def collect_findings(host):
    """Bounded incremental intake from existing trusted host outcome ledgers.

    Never opens mission source paths or copies task/output/lesson text. Each
    finding identifies a failed observation, not its cause or a model defect.
    Independent task design and registry review remain required before testing.
    The existing scheduler supplies the lock and repetition; no provider call.
    """
    path = database(host)
    added = 0
    with sqlite3.connect(path,uri=True) as db:
        # Attach read-only host outcomes; this also lets SQL exclude previously
        # seen source identities before applying the per-tick bound.
        db.execute('ATTACH DATABASE ? AS learning', (f'file:{host.path}?mode=ro',))
        db.create_function('mission_digest',1,lambda ident: studies.digest(dict(origin='mission',id=ident)),deterministic=True)
        db.create_function('research_profile',1,lambda profile: int(type(profile) is str and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',profile) is not None),deterministic=True)
        sources = db.execute('SELECT id,profile,duration,source FROM learning.nerve_missions m '
            'WHERE success=0 AND research_profile(profile)=1 AND NOT EXISTS '
            "(SELECT 1 FROM research_findings f WHERE f.origin='mission' AND f.source_digest=mission_digest(m.id)) "
            'ORDER BY m.rowid LIMIT 32').fetchall()
        candidates = []
        for ident,profile,duration,source in sources:
            source_digest = studies.digest(dict(origin='mission',id=ident))
            if type(profile) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',profile) is None:
                continue
            # Store only a source fingerprint, not a filesystem location or raw
            # supervisor text. Unknown imported outcomes get no causal label.
            category = 'supervisor_timeout' if source=='agentos-maintenance:supervisor-timeout' else 'verified_mission_failure'
            metadata = dict(outcome='failed',source_record_digest=studies.digest(
                dict(id=ident,profile=profile,duration=duration,source=source)),
                hypothesis='Investigate this observed failure using independently reviewed new tasks.',
                benchmark_gold=False,requested_provider_calls=0,activation_authorized=False)
            candidates.append((source_digest,'mission',profile,category,metadata))
            if len(candidates)>=32:
                break
        for source_digest,origin,profile,category,metadata in candidates:
            fingerprint = studies.digest(dict(origin=origin,source_digest=source_digest))
            added += db.execute('INSERT OR IGNORE INTO research_findings VALUES(?,?,?,?,?,?,?)',
                (fingerprint,origin,source_digest,profile,category,studies.encode(metadata),int(time.time()))).rowcount
    return dict(added=added,provider_calls=0,benchmark_gold=False,activation_authorized=False)


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
    identities, families = registry.known_evidence(host)
    if identity in identities or task['family'] in families:
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


def _cohort_export(host, verified):
    directory = host.directory / 'autoresearch-cohort-skills' / verified['study_id']
    directory.mkdir(parents=True, exist_ok=True)
    content = ('---\nname: nerve-audit-experimental\ndescription: Evaluated advice for isolated simulated audit experiments.\n---\n\n'
               'Experimental only; no operational activation or ongoing shadow monitoring.\n\n' + verified['lesson'] + '\n')
    target = directory / 'SKILL.md'
    if target.exists() and target.read_text() != content:
        raise ValueError('experimental skill artifact mismatch')
    if not target.exists():
        with target.open('x') as handle:
            handle.write(content)
    atomic_json(directory / 'provenance.json', verified)
    atomic_json(directory / 'eligibility.json', dict(status='experimental_unmonitored',
                activation_authorized=False, checked_at=int(time.time())))
    return str(target)


def _registered_tick(host, native):
    """Persist errors as outcomes; evidence remains consumed after any failure."""
    try:
        return _registered_work(host, native)
    except Exception as error:
        return _event(host, 'reviewed_cohort', 'crash', dict(status='cohort_review_required', reason=type(error).__name__))


def _registered_work(host, native):
    """Consume a new reviewed cohort, never regenerate or reuse a final set."""
    runner = cohort_runner
    recovered = runner.recover(host)
    if recovered:
        return _event(host, 'recovery', 'crash', dict(status='interrupted_no_replay', studies=recovered))
    # Recover missing exports without rerunning inference; refresh their eligibility.
    with sqlite3.connect(runner.database(host)) as db:
        accepted = [row[0] for row in db.execute("SELECT id FROM studies WHERE status='shadow_accepted'")]
    for ident in accepted:
        try:
            _cohort_export(host, runner.verify_candidate(host, ident))
        except Exception:
            directory = host.directory / 'autoresearch-cohort-skills' / ident
            if re.fullmatch(r'cohort-[a-f0-9]{32}', ident) and directory.is_dir():
                atomic_json(directory / 'eligibility.json', dict(status='ineligible',
                            activation_authorized=False, checked_at=int(time.time())))
    for entry in registry.pending(host):
        if runner.consumed(host, entry['id']):
            continue
        result = runner.run(host, native, entry)
        state = result['status']
        outcome = ('keep' if state == 'shadow_accepted' else 'wait' if state in
                   ('queued_budget', 'queued_revision_mismatch') else 'crash' if state == 'failed' else 'discard')
        if outcome == 'keep':
            verified = runner.verify_candidate(host, result['study_id'])
            result['experimental_skill'] = _cohort_export(host, verified)
        return _event(host, 'reviewed_cohort', outcome, result)
    return None


def tick(host, native, *, cue_adapters=None):
    """One queued CCE job OR audit work; existing scheduler supplies repetition.

    The caller holds the existing host lock. A waiting queued cue job has priority
    and deliberately suppresses unrelated audit dispatches until resolved; this
    prevents surprising provider calls while its required adapters are missing.
    Built-in bridge calls load only the explicitly enabled local registry;
    other missing measured adapters leave their jobs waiting.
    """
    current = status(host)
    if not current['enabled']:
        return dict(status='paused', activation_authorized=False)
    collect_findings(host)
    recovered_cues = cue_jobs.recover(host)
    if recovered_cues.get('abandoned'):
        return _event(host, 'cce_recovery', 'crash',
                      dict(status='interrupted_no_replay', jobs=recovered_cues['abandoned']))
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
    existing = studies.status(host)
    if existing['status'] == 'running':
        with sqlite3.connect(studies.database(host)) as db:
            db.execute("UPDATE studies SET status='failed',result=? WHERE status='running'",
                       (studies.encode(dict(status='failed', reason='interrupted_no_replay')),))
        return _event(host, 'recovery', 'crash', dict(status='interrupted_no_replay'))
    recovered_cohorts = cohort_runner.recover(host)
    if recovered_cohorts:
        return _event(host, 'recovery', 'crash',
                      dict(status='interrupted_no_replay', studies=recovered_cohorts))
    if cue_adapters is None and current['cce_jobs']['counts'].get('pending'):
        local_spec = importlib.util.spec_from_file_location(
            '_cce_local_adapter', Path(__file__).with_name('agentos_cue_local.py'))
        local_adapter = importlib.util.module_from_spec(local_spec)
        local_spec.loader.exec_module(local_adapter)
        cue_adapters = local_adapter.adapters_for(host)
    cue_result = cue_jobs.tick(host, adapters=cue_adapters)
    if cue_result is not None:
        state = cue_result.get('status')
        cycle_state = (cue_result.get('result') or {}).get('state')
        outcome = ('keep' if state == 'completed' and cycle_state == 'awaiting_approval' else
                   'discard' if state == 'completed' else
                   'crash' if state in ('failed', 'interrupted_no_replay') else 'wait')
        return _event(host, 'cce_job', outcome, cue_result)
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
            researched = _registered_tick(host, native)
            if researched is not None:
                return researched
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
    if existing['status'] != 'not_run':
        # Fixed holdouts have been consumed: never hunt for a lucky retry.
        researched = _registered_tick(host, native)
        if researched is not None:
            return researched
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
