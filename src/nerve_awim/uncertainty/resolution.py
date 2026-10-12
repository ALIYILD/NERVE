"""Only trusted host predicates and registered scoped evidence can close a conflict."""
from dataclasses import replace
from .contracts import Resolution,OPEN
from .ledger import StaleRevision
class ResolutionService:
    def __init__(self,ledger,*,predicates):
        self.ledger,self.predicates=ledger,dict(predicates)
        if any(not callable(p) for p in self.predicates.values()):raise TypeError('host resolution predicates required')
    def resolve(self,actor,resolution):
        ledger=self.ledger;ledger.scope(actor,roles=('operator',))
        if type(resolution) is not Resolution:raise TypeError('typed Resolution required')
        if resolution.resolver_identity!=actor.agent:raise PermissionError('authenticated resolver identity required')
        if resolution.resolution_type not in self.predicates:raise PermissionError('resolution type has no host evidence predicate')
        with ledger.engine._db() as con:
            con.execute('BEGIN IMMEDIATE');c=ledger.get_conflict(actor,resolution.conflict_id,con=con)
            if c.revision!=resolution.expected_conflict_revision:raise StaleRevision('conflict changed before resolution')
            if c.status not in OPEN:raise ValueError('conflict already closed')
            named=resolution.accepted_claim_ids+resolution.rejected_or_superseded_claim_ids
            if not named or set(named)!=set(c.claim_ids) or set(resolution.accepted_claim_ids)&set(resolution.rejected_or_superseded_claim_ids):raise ValueError('resolution must partition known claims without overlap')
            if not resolution.evidence_refs:raise PermissionError('evidence-free closure denied')
            sources=[ledger.source(actor,r['source_ref'],r['source_revision'],con=con) for r in resolution.evidence_refs]
            claims=[ledger._claim(con,actor,cid) for cid in c.claim_ids]
            if self.predicates[resolution.resolution_type](c,claims,sources,resolution) is not True:raise PermissionError('host evidence predicate did not justify resolution')
            con.execute('INSERT INTO uc_resolutions VALUES(?,?,?,?,?)',(resolution.resolution_id,*ledger.scope(actor,c.scope['task_id']),resolution.to_json()))
            closed=replace(c,status='dismissed_with_evidence' if resolution.resolution_type in {'different_context','unit_normalized','corrected_extraction'} else 'resolved',resolution_ref=resolution.resolution_id,revision=c.revision+1,updated_at=ledger.clock())
            key=con.execute('SELECT family FROM uc_conflicts WHERE id=?',(c.conflict_id,)).fetchone()['family']
            ledger._write_conflict(con,ledger.scope(actor,c.scope['task_id']),closed,key,'conflict_resolved')
            return closed
