"""Revocation and proposal-only cross-agent transfer of synthetic rules."""
from copy import deepcopy
from .contracts import Rule, REVISION
from .registry import Registry


def transferred_proposals(rules, *, permission=False):
    if permission is not True:
        raise PermissionError('explicit synthetic rule transfer permission required')
    result=[]
    for raw in rules:
        rule=Rule.load(raw).to_dict()
        rule['status']='hypothesis'
        rule['authoring_run_id']='transfer_pending'
        # Foreign evidence IDs remain provenance only, cannot satisfy local registry.
        result.append(deepcopy(rule))
    return result


def require_revision(model, revision):
    if revision != model['environment_revision']:
        raise PermissionError('environment drift; suspend planning pending revalidation')


def tombstone_episode(ledger, actor, episode):
    scope=ledger.scope(actor,'operator')
    # Conservative invalidation: every model in scope is suspended, including
    # descendants. No private payload is copied into an event or Git artifact.
    with ledger.db() as db:
        if not db.execute('SELECT 1 FROM wm_episodes WHERE scope=? AND episode=?',(scope,episode)).fetchone():
            raise LookupError('episode outside scope')
        db.execute('UPDATE wm_transitions SET previous=\'null\',prediction=\'null\',outcome=\'null\',completion=NULL,status=\'redacted\' '
                   'WHERE scope=? AND episode=?',(scope,episode))
        db.execute("UPDATE wm_episodes SET initial='null' WHERE scope=? AND episode=?",(scope,episode))
        # Rules can contain copied observation data. Remove canonical artifact bodies
        # as well as revoking them; all subsequent content checks fail closed.
        db.execute("UPDATE wm_artifacts SET state='revoked',body='{}' WHERE scope=?",(scope,))
        db.execute("UPDATE wm_runs SET phase='stopped',body='{}',owner=NULL,lease_until=0 WHERE scope=?",(scope,))
        db.execute('DELETE FROM wm_releases WHERE scope=?',(scope,))
    # Logical deletion only. Host must handle backups/SQLite free pages separately.
    return {'status':'tombstoned','dependent_models':'invalidated','physical_erasure':False}
