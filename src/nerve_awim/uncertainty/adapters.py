"""Adapters to actual NERVE Hermes proposal, governed dispatch and scoped memory."""
from .propagation import Propagator
from .policy import Policy
from .output_guard import OutputGuard


class UncertaintyBlocked(PermissionError):
    pass


class UncertaintyAdapter:
    def __init__(self, ledger, actor, *, task_id, dependency_claim_ids=(), required=True):
        ledger.engine._scope(actor, 'runtime', 'operator')
        self.ledger, self.actor, self.task_id = ledger, actor, task_id
        self.dependencies = list(dependency_claim_ids)
        self.required = required
        self.propagator, self.policy = Propagator(ledger), Policy(ledger)
        self.output = OutputGuard(ledger, self.policy)

    def match_memory_actor(self, memory_actor):
        self.ledger.engine._scope(self.actor, 'runtime', 'operator')
        if (memory_actor.tenant_id, memory_actor.agent_id) != (self.actor.tenant, self.actor.agent):
            raise PermissionError('memory and uncertainty scopes must match')

    def handoff(self, memory_actor, envelope=None):
        self.match_memory_actor(memory_actor)
        if envelope is None:
            return self.propagator.envelope(self.actor, self.task_id)
        return self.propagator.consume(self.actor, envelope)

    def permit_learning(self, memory_actor):
        self.match_memory_actor(memory_actor)
        assessment = self.policy.assess(self.actor, self.task_id, self.task_id + '.learning',
            'skill-proposal', self.dependencies, impact='restricted', required=self.required)
        if assessment.status not in {'proceed', 'proceed_with_qualification'}:
            raise UncertaintyBlocked('Required learning evidence remains disputed')
        return assessment

    def retrieve(self, memory_ledger, memory_actor, *, context, query, limit=5):
        self.match_memory_actor(memory_actor)
        return memory_ledger.retrieve(memory_actor, context=context, query=query, limit=limit, uncertainty=self)

    def final(self, conclusions, assessments=(), regenerate=None):
        return self.output.render(self.actor, self.task_id, conclusions, assessments, regenerate)


def memory_boundary(memory_ledger, actor, context, uncertainty=None):
    """Persistent opt-in; reopening or omitting the adapter cannot erase state."""
    import sqlite3
    with sqlite3.connect(memory_ledger.path) as con:
        exists = con.execute("SELECT 1 FROM sqlite_master WHERE name='uc_memory_bindings'").fetchone()
        previous = con.execute('SELECT task FROM uc_memory_bindings WHERE tenant=? AND agent=? AND context=?',
            (actor.tenant_id, actor.agent_id, context)).fetchone() if exists else None
        if uncertainty is None:
            if previous: raise PermissionError('uncertainty-enabled memory context requires its scoped adapter')
            return
        uncertainty.match_memory_actor(actor)
        if previous and previous[0] != uncertainty.task_id:
            raise PermissionError('memory context already bound to a different uncertainty task')
        con.execute('CREATE TABLE IF NOT EXISTS uc_memory_bindings(tenant TEXT,agent TEXT,context TEXT,task TEXT,PRIMARY KEY(tenant,agent,context))')
        con.execute('INSERT OR IGNORE INTO uc_memory_bindings VALUES(?,?,?,?)',
            (actor.tenant_id, actor.agent_id, context, uncertainty.task_id))


def memory_result(adapter, actor, records):
    if adapter is None: return records
    return {'records': records, 'uncertainty': adapter.handoff(actor), 'guidance_authority': False}
