"""Externally supplied, host-reviewed holdout; durable one-use research claims.

The host protects the claim database and external answer key. Hash binding is
integrity, not secrecy or protection from an operator deleting this database.
"""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from ..recursive_evolution_v19 import RetrievalGenome, select
from .contracts import MemoryRequest, MemoryScope

MAX_BYTES = 65536


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def read_artifact(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('artifact exceeds byte budget')
    value = json.loads(raw, object_pairs_hook=_unique)
    if (type(value) is not dict or set(value) != {'version', 'study_id', 'cases'}
            or type(value['version']) is not int or value['version'] != 1
            or type(value['study_id']) is not str
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value['study_id'])
            or type(value['cases']) is not list or not 1 <= len(value['cases']) <= 100):
        raise ValueError('invalid holdout schema')
    queries = set()
    for case in value['cases']:
        if (type(case) is not dict or set(case) != {'query', 'expected_source_id'}
                or type(case['query']) is not str or not 1 <= len(case['query']) <= 256
                or case['query'] in queries):
            raise ValueError('invalid or duplicate case')
        expected = case['expected_source_id']
        if expected is not None and (type(expected) is not str or not 1 <= len(expected) <= 160):
            raise ValueError('invalid expected source')
        queries.add(case['query'])
    # Study names, whitespace and case ordering cannot create fresh reuse rights.
    cases = sorted(value['cases'], key=lambda case: case['query'])
    digest = sha256(_encoded(cases).encode()).hexdigest()
    return value, digest


def _db(path):
    if str(path) == ':memory:':
        raise ValueError('durable claim database required')
    con = sqlite3.connect(path, timeout=5)
    con.execute('PRAGMA synchronous=FULL')
    con.execute('''CREATE TABLE IF NOT EXISTS holdout_claims (
        study TEXT PRIMARY KEY, dataset TEXT UNIQUE NOT NULL,
        binding TEXT NOT NULL, binding_hash TEXT NOT NULL, status TEXT NOT NULL)''')
    return con


def freeze_holdout(claim_db, *, study_id, dataset_sha256, selected, baseline, scope):
    if (type(study_id) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', study_id)
            or type(dataset_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', dataset_sha256)
            or type(selected) is not RetrievalGenome or type(baseline) is not RetrievalGenome
            or type(scope) is not MemoryScope):
        raise ValueError('fixed study, dataset, genomes and scope required')
    binding = _encoded({'selected': asdict(selected), 'baseline': asdict(baseline),
                        'scope': asdict(scope), 'dataset': dataset_sha256, 'study': study_id})
    con = _db(claim_db)
    try:
        with con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute('SELECT COUNT(*) FROM holdout_claims').fetchone()[0] >= 10000:
                raise ValueError('claim store capacity exhausted')
            con.execute('INSERT INTO holdout_claims VALUES (?,?,?,?,?)',
                (study_id, dataset_sha256, binding, sha256(binding.encode()).hexdigest(), 'frozen'))
    except sqlite3.IntegrityError:
        raise ValueError('study or dataset already reserved') from None
    finally:
        con.close()
    return {'status': 'frozen', 'study_id': study_id, 'dataset_sha256': dataset_sha256}


def evaluate_holdout(claim_db, artifact_path, *, study_id, gateway, actor, scope):
    # Authorise before consuming a study, but never read answers until claim is
    # durable. Process death/errors leave a consumed claim, never a reusable one.
    gateway._require(actor, scope, 'read')
    con = _db(claim_db)
    try:
        with con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT dataset,binding,binding_hash,status FROM holdout_claims WHERE study=?',
                              (study_id,)).fetchone()
            if row is None or row[3] != 'frozen':
                raise ValueError('no unused frozen study')
            # A different authorised scope must not burn this host's study.
            # Read binding metadata only; answer keys remain unopened. Invalid
            # metadata is still consumed by the authorised evaluation attempt.
            try:
                frozen_scope = json.loads(row[1]).get('scope')
            except (ValueError, AttributeError):
                frozen_scope = None
            if frozen_scope is not None and frozen_scope != asdict(scope):
                raise PermissionError('frozen scope denied')
            con.execute("UPDATE holdout_claims SET status='consumed' WHERE study=?", (study_id,))
        if sha256(row[1].encode()).hexdigest() != row[2]:
            raise ValueError('frozen binding corrupted')
        binding = json.loads(row[1])
        if binding['scope'] != asdict(scope) or binding['dataset'] != row[0] or binding['study'] != study_id:
            raise ValueError('frozen scope or dataset mismatch')
        selected = RetrievalGenome(**binding['selected'])
        baseline = RetrievalGenome(**binding['baseline'])
        artifact, digest = read_artifact(artifact_path)
        if artifact['study_id'] != study_id or digest != row[0]:
            raise ValueError('holdout artifact changed')
        hits = {'selected': 0, 'baseline': 0}
        for case in artifact['cases']:
            result = gateway.retrieve(actor, MemoryRequest(scope, case['query'], limit=20))
            documents = {r.source_id: r.content for r in result.records}
            if len(documents) != len(result.records):
                raise ValueError('ambiguous source identity')
            for name, genome in (('selected', selected), ('baseline', baseline)):
                hits[name] += select(case['query'], documents, genome) == case['expected_source_id']
        report = {'status': 'report_only', 'study_id': study_id, 'dataset_sha256': digest,
                  'cases': len(artifact['cases']), 'hits': hits, 'selected': asdict(selected),
                  'baseline': asdict(baseline), 'deployed': False, 'cryptographically_secret': False}
        with con:
            con.execute("UPDATE holdout_claims SET status='complete' WHERE study=?", (study_id,))
        return report
    finally:
        con.close()
