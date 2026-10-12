"""Optional uncertainty evidence gate on existing governed releases and canaries.

This stores references to host-produced evaluation receipts, not supplied scores.
The offline pilot remains inconclusive and cannot authorize promotion.
"""
import json
from hashlib import sha256
from ..governed_learning_v20 import _id


def _exists(con, name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _receipt(con, tenant, run_id):
    if not _exists(con, 'ue_runs'): raise PermissionError('uncertainty evaluation receipt unavailable')
    row = con.execute('SELECT * FROM ue_runs WHERE id=? AND tenant=?', (run_id, tenant)).fetchone()
    if row is None: raise PermissionError('uncertainty evaluation outside authenticated scope')
    if row['state'] != 'complete' or not row['final']:
        raise PermissionError('complete sealed uncertainty evaluation required')
    final = json.loads(row['final'])
    from .evaluation import code_revision, load_suite, digest
    _, manifest = load_suite()
    if (row['revision'] != code_revision() or final.get('revision') != row['revision'] or
            row['dataset'] != manifest['dataset_sha256'] or final.get('dataset_sha256') != row['dataset'] or
            row['policy'] != digest(manifest['policy']) or final.get('policy') != manifest['policy'] or
            final.get('run_id') != run_id or final.get('split') != 'sealed-final'):
        raise ValueError('uncertainty receipt is stale or violates frozen integrity')
    return row, sha256(row['final'].encode()).hexdigest()


class ReleaseEligibility:
    def __init__(self, engine):
        self.engine = engine
        with engine._db() as con:
            con.executescript('''CREATE TABLE IF NOT EXISTS uc_release_scopes(
                tenant TEXT,agent TEXT,context TEXT,PRIMARY KEY(tenant,agent,context));
                CREATE TABLE IF NOT EXISTS uc_candidate_reports(
                tenant TEXT,agent TEXT,candidate TEXT,run TEXT,revision TEXT,report_hash TEXT,
                PRIMARY KEY(tenant,agent,candidate));''')

    def enable(self, actor, context):
        scope = self.engine._scope(actor, 'operator')
        if context not in self.engine._baseline: raise ValueError('registered release context required')
        with self.engine._db() as con:
            con.execute('INSERT OR IGNORE INTO uc_release_scopes VALUES(?,?,?)', (*scope, context))
            self.engine._event(con, scope, 'uncertainty_release_gate_enabled', {'context': context})

    def bind(self, actor, candidate_id, run_id):
        scope = self.engine._scope(actor, 'evaluator')
        _id(candidate_id); _id(run_id)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            candidate = self.engine._candidate(con, scope, candidate_id)
            receipt, fingerprint = _receipt(con, actor.tenant, run_id)
            old = con.execute('SELECT * FROM uc_candidate_reports WHERE tenant=? AND agent=? AND candidate=?',
                              (*scope, candidate_id)).fetchone()
            if old and (old['run'], old['revision'], old['report_hash']) != (run_id, receipt['revision'], fingerprint):
                raise PermissionError('candidate uncertainty receipt binding is immutable')
            con.execute('INSERT OR IGNORE INTO uc_candidate_reports VALUES(?,?,?,?,?,?)',
                        (*scope, candidate_id, run_id, receipt['revision'], fingerprint))
            for context in json.loads(candidate['routes']):
                con.execute('INSERT OR IGNORE INTO uc_release_scopes VALUES(?,?,?)', (*scope, context))
            self.engine._event(con, scope, 'uncertainty_candidate_report_bound',
                               {'candidate': candidate_id, 'run_id': run_id, 'revision': receipt['revision']})
        return {'candidate_id': candidate_id, 'run_id': run_id, 'activation_authorized': False}


def require_eligibility(con, engine, actor, candidate_id):
    """Run inside the existing activation transaction; missing evidence fails closed."""
    scope = engine._scope(actor, 'operator', 'runtime')
    candidate = engine._candidate(con, scope, candidate_id)
    contexts = set(json.loads(candidate['routes']))
    enabled = False
    for table in ('uc_release_scopes', 'uc_contexts'):
        if _exists(con, table):
            enabled = enabled or any(r['context'] in contexts for r in con.execute(
                'SELECT context FROM ' + table + ' WHERE tenant=? AND agent=?', scope))
    if not enabled: return
    if not _exists(con, 'uc_candidate_reports'):
        raise PermissionError('uncertainty-enabled release requires a bound evaluated report')
    bound = con.execute('SELECT * FROM uc_candidate_reports WHERE tenant=? AND agent=? AND candidate=?',
                        (*scope, candidate_id)).fetchone()
    if bound is None: raise PermissionError('candidate missing uncertainty evaluation binding')
    receipt, fingerprint = _receipt(con, actor.tenant, bound['run'])
    if (receipt['revision'], fingerprint) != (bound['revision'], bound['report_hash']):
        raise ValueError('bound uncertainty receipt changed; promotion denied')
    from .evaluation import eligibility
    verdict = eligibility(engine.path, bound['run'], tenant=actor.tenant)
    if verdict.get('eligible') is not True:
        raise PermissionError('uncertainty evaluation remains ineligible; retain incumbent or shadow')
