"""Mandatory compact state; model summaries never own the open-conflict set."""
import json
import time
from ..governed_learning_v20 import _id, _json


class Propagator:
    def __init__(self, ledger):
        self.ledger = ledger
        with ledger.engine._db() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS uc_checkpoints
              (tenant TEXT, agent TEXT, task TEXT, id TEXT, envelope TEXT,
               PRIMARY KEY(tenant,agent,task,id))''')

    def envelope(self, actor, task_id, decision_id=None, max_items=64):
        self.ledger.engine._scope(actor, 'runtime', 'operator', 'auditor', 'evaluator', 'trainer')
        _id(task_id)
        if type(max_items) is not int or not 1 <= max_items <= 256:
            raise ValueError('bounded handoff limit required')
        # All reads share a snapshot: an envelope cannot combine different revisions.
        with self.ledger.engine._db() as con:
            con.execute('BEGIN')
            revision = self.ledger.revision(actor, task_id, con=con)
            conflicts = self.ledger.open_conflicts(actor, task_id, decision_id=decision_id, con=con)
        unavailable = []
        for claim in self.ledger.claims(actor, task_id):
            try: self.ledger.source(actor, claim.source_ref, claim.source_revision)
            except (PermissionError, LookupError): unavailable.append(claim.claim_id)
        ids = sorted(c.conflict_id for c in conflicts)
        claims = sorted({cid for c in conflicts for cid in c.claim_ids})
        envelope = {'schema_version': 'uncertainty-handoff-v1',
            'scope': {'tenant_id': actor.tenant, 'agent_id': actor.agent},
            'task_id': task_id, 'ledger_revision': revision,
            'open_conflict_ids': ids[:max_items],
            'impacted_decisions': sorted({d for c in conflicts for d in c.affected_decision_ids})[:max_items],
            'unknowns': sorted({c.kind for c in conflicts} | ({'source_unavailable'} if unavailable else set())), 'evidence_refs': claims[:max_items],
            'state': 'unavailable' if unavailable else 'incomplete' if len(ids) > max_items or len(claims) > max_items else 'complete',
            'unavailable_claim_ids': unavailable[:max_items],
            'open_conflict_count': len(ids), 'decision_id': decision_id}
        return envelope

    def consume(self, actor, envelope, decision_id=None):
        if type(envelope) is not dict:
            raise ValueError('mandatory uncertainty envelope unavailable')
        if envelope.get('schema_version') != 'uncertainty-handoff-v1':
            raise ValueError('unsupported uncertainty envelope')
        if envelope.get('scope') != {'tenant_id': actor.tenant, 'agent_id': actor.agent}:
            raise PermissionError('handoff outside actor scope')
        supplied = envelope.get('ledger_revision')
        if type(supplied) is not int or supplied < 0:
            raise ValueError('mandatory ledger revision unavailable')
        current = self.envelope(actor, envelope['task_id'], decision_id=decision_id)
        if supplied > current['ledger_revision']:
            raise ValueError('handoff references unavailable ledger state')
        # Deliberately ignore caller conflict IDs and unknowns: omitted != empty.
        current['refreshed'] = supplied != current['ledger_revision']
        self.event(actor, envelope['task_id'], 'handoff_restored', {
            'revision': current['ledger_revision'], 'open_conflicts': current['open_conflict_count'],
            'state': current['state']})
        return current

    def event(self, actor, task_id, event, details):
        scope = self.ledger.engine._scope(actor, 'runtime', 'operator', 'auditor', 'evaluator', 'trainer')
        with self.ledger.engine._db() as con:
            self.ledger.engine._event(con, scope, 'uncertainty_' + event, {'task_id': task_id, **details})

    def checkpoint(self, actor, task_id, checkpoint_id):
        _id(checkpoint_id)
        scope = self.ledger.engine._scope(actor, 'runtime', 'operator')
        envelope = self.envelope(actor, task_id)
        with self.ledger.engine._db() as con:
            con.execute('INSERT OR REPLACE INTO uc_checkpoints VALUES(?,?,?,?,?)',
                        (*scope, task_id, checkpoint_id, _json(envelope)))
        self.event(actor, task_id, 'checkpoint', {'checkpoint_id': checkpoint_id})
        return envelope

    def resume(self, actor, task_id, checkpoint_id):
        scope = self.ledger.engine._scope(actor, 'runtime', 'operator', 'auditor')
        with self.ledger.engine._db() as con:
            row = con.execute('SELECT envelope FROM uc_checkpoints WHERE tenant=? AND agent=? AND task=? AND id=?',
                              (*scope, task_id, checkpoint_id)).fetchone()
        if row is None:
            raise LookupError('scoped checkpoint unavailable; no silent empty state')
        return self.consume(actor, json.loads(row['envelope']))
