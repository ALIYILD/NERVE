"""Host-reviewed simulated cohorts. All public operations require the host lock.

Admission reserves evidence across future trials and shadow monitoring. A review
record is local host attestation, not cryptographic proof of reviewer identity.
Neither candidate models nor their outputs can admit their own evaluation data.
"""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time

from nerve_awim import agentos_audit_cohort as legacy
from nerve_awim import agentos_audit_evidence as oracle
from nerve_awim.agentos_audit_fixtures import development_cases

COUNTS = dict(train=2, selection=4, retention=4, final=6)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def database(host):
    path = host.directory / 'cohort-registry.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS cohorts(id TEXT PRIMARY KEY,data TEXT NOT NULL,manifest TEXT UNIQUE NOT NULL,oracle TEXT NOT NULL,profile TEXT NOT NULL,review TEXT NOT NULL,created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence(identity TEXT PRIMARY KEY,family TEXT UNIQUE NOT NULL,cohort TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS cohorts_no_update BEFORE UPDATE ON cohorts BEGIN SELECT RAISE(ABORT,'immutable reviewed cohort'); END;
        CREATE TRIGGER IF NOT EXISTS cohorts_no_delete BEFORE DELETE ON cohorts BEGIN SELECT RAISE(ABORT,'immutable reviewed cohort'); END;
        CREATE TRIGGER IF NOT EXISTS evidence_no_update BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        ''')
    return path


def validate(data):
    if (type(data) is not dict or set(data) != {'id', 'scope', 'limitation', 'splits'}
            or data['scope'] != legacy.SCOPE or type(data['id']) is not str
            or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', data['id']) is None
            or type(data['limitation']) is not str or not 1 <= len(data['limitation']) <= 4096
            or type(data['splits']) is not dict or set(data['splits']) != set(COUNTS)):
        raise ValueError('invalid cohort metadata')
    if len(encode(data).encode()) > 1_000_000:
        raise ValueError('cohort exceeds size limit')
    ids, families, identities = set(), set(), set()
    for phase, count in COUNTS.items():
        rows = data['splits'][phase]
        if type(rows) is not list or len(rows) != count:
            raise ValueError('invalid split size: ' + phase)
        for row in rows:
            if (type(row) is not dict or set(row) != {'id', 'family', 'bundle', 'expected'}
                    or any(type(row[k]) is not str or not 1 <= len(row[k]) <= 128 for k in ('id', 'family'))):
                raise ValueError('invalid case')
            identity = legacy.canonical_identity(row)
            if row['id'] in ids or row['family'] in families or identity in identities:
                raise ValueError('duplicate case across splits')
            if digest(oracle.expected_decision(row['bundle'])) != digest(row['expected']):
                raise ValueError('reviewed gold disagrees with evaluator: ' + row['id'])
            ids.add(row['id']); families.add(row['family']); identities.add(identity)
    return data


def _review(review, manifest):
    if (type(review) is not dict or set(review) != {'manifest_sha256', 'reviewer', 'method', 'checks'}
            or review['manifest_sha256'] != manifest
            or any(type(review[k]) is not str or not 1 <= len(review[k]) <= 4096 for k in ('reviewer', 'method'))
            or type(review['checks']) is not dict
            or set(review['checks']) != {'gold', 'novelty', 'split_separation'}
            or any(value is not True for value in review['checks'].values())):
        raise ValueError('explicit matching host review required')


def known_evidence(host):
    rows = development_cases() + [r for group in legacy.cohort()['splits'].values() for r in group]
    identities = {legacy.canonical_identity(r) for r in rows}
    families = {r['family'] for r in rows}
    for filename, table in (('cohort-registry.sqlite3', 'evidence'), ('audit-study.sqlite3', 'evidence'),
                            ('audit-shadow.sqlite3', 'episodes'), ('autoresearch.sqlite3', 'inbox')):
        path = host.directory / filename
        if not path.exists():
            continue
        with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
            if not db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone():
                continue
            for identity, family in db.execute('SELECT identity,family FROM ' + table):
                identities.add(identity); families.add(family)
    return identities, families


def admit(host, data, review, profile='qa-release'):
    validate(data)
    manifest = digest(data)
    _review(review, manifest)
    if type(profile) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', profile) is None:
        raise ValueError('invalid profile')
    path = database(host)
    with sqlite3.connect(path) as db:
        existing = db.execute('SELECT manifest,profile,review FROM cohorts WHERE id=?', (data['id'],)).fetchone()
    if existing:
        if existing != (manifest, profile, encode(review)):
            raise ValueError('cohort ID already bound')
        return dict(status='already_registered', id=data['id'], manifest_sha256=manifest)
    identities, families = known_evidence(host)
    evidence = [(legacy.canonical_identity(row), row['family'], data['id'])
                for group in data['splits'].values() for row in group]
    if any(identity in identities or family in families for identity, family, _ in evidence):
        raise ValueError('reused evidence or scenario family')
    with sqlite3.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO cohorts VALUES(?,?,?,?,?,?,?)',
                   (data['id'], encode(data), manifest, oracle.evaluator_revision(), profile, encode(review), int(time.time())))
        db.executemany('INSERT INTO evidence VALUES(?,?,?)', evidence)
    return dict(status='registered', id=data['id'], manifest_sha256=manifest, cases=len(evidence))


def get(host, ident):
    with sqlite3.connect(database(host)) as db:
        row = db.execute('SELECT data,manifest,oracle,profile,review FROM cohorts WHERE id=?', (ident,)).fetchone()
    if row is None:
        raise ValueError('unregistered cohort')
    data, manifest, revision, profile, review = row
    data, review = json.loads(data), json.loads(review)
    validate(data)
    if data['id'] != ident or digest(data) != manifest or revision != oracle.evaluator_revision():
        raise ValueError('cohort integrity or evaluator drift')
    _review(review, manifest)
    with sqlite3.connect(database(host)) as db:
        reserved = set(db.execute('SELECT identity,family FROM evidence WHERE cohort=?', (ident,)))
    expected = {(legacy.canonical_identity(r), r['family']) for group in data['splits'].values() for r in group}
    if reserved != expected:
        raise ValueError('cohort evidence reservation mismatch')
    # A direct caller must not evaluate a cohort after another path exposed it.
    for filename, table in (('audit-shadow.sqlite3', 'episodes'), ('autoresearch.sqlite3', 'inbox')):
        path = host.directory / filename
        if not path.exists():
            continue
        with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
            if not db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone():
                continue
            for identity, family in db.execute('SELECT identity,family FROM ' + table):
                if identity in {r[0] for r in expected} or family in {r[1] for r in expected}:
                    raise ValueError('registered cohort exposed through monitoring')
    return dict(id=ident, data=data, manifest_sha256=manifest, evaluator_revision=revision, profile=profile, review=review)


def pending(host):
    # All registered entries; the study runner owns the consumed state.
    with sqlite3.connect(database(host)) as db:
        ids = [r[0] for r in db.execute('SELECT id FROM cohorts ORDER BY created,rowid')]
    return [get(host, ident) for ident in ids]


def status(host):
    with sqlite3.connect(database(host)) as db:
        rows = db.execute('SELECT id,manifest,profile,created FROM cohorts ORDER BY created,rowid').fetchall()
    return [dict(id=r[0], manifest_sha256=r[1], profile=r[2], created=r[3]) for r in rows]
