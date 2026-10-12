"""Host policy adds restrictions to existing permissions; never grants authority."""
import json
import time
from .contracts import DecisionAssessment
from .reconciliation import normalized, usable
from ..governed_learning_v20 import _id, _json

POLICY_REVISION = 'uncertainty-policy-v1'
MANDATORY = frozenset({'identity', 'consent', 'authorization'})


def relevant(conflict, decision_id, dependency_ids, required=False):
    return (conflict.materiality != 'irrelevant' and
            (bool(set(conflict.claim_ids) & set(dependency_ids)) or
             decision_id in conflict.affected_decision_ids or
             (required and not dependency_ids)))


class Policy:
    def __init__(self, ledger, clock=time.time):
        self.ledger, self.clock = ledger, clock
        with ledger.engine._db() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS uc_assessments
              (tenant TEXT,agent TEXT,task TEXT,decision TEXT,action TEXT,record TEXT,
               PRIMARY KEY(tenant,agent,decision))''')
            con.execute('''CREATE TABLE IF NOT EXISTS uc_dispatch_bindings
              (tenant TEXT,agent TEXT,execution_task TEXT,decision TEXT,
               PRIMARY KEY(tenant,agent,execution_task))''')
            con.execute('CREATE TABLE IF NOT EXISTS uc_policy_bindings(tenant TEXT,agent TEXT,decision TEXT,config TEXT,PRIMARY KEY(tenant,agent,decision))')
            con.execute('CREATE TABLE IF NOT EXISTS uc_contexts(tenant TEXT,agent TEXT,context TEXT,PRIMARY KEY(tenant,agent,context))')
        ledger.engine._uncertainty_policy = self

    def assess(self, actor, task_id, decision_id, action_id, dependency_claim_ids,
               *, impact='low', required=False, mandatory=None, expires_in=300):
        scope = self.ledger.engine._scope(actor, 'runtime', 'operator')
        for value in (task_id, decision_id, action_id): _id(value)
        if impact not in {'low', 'restricted'} or type(required) is not bool:
            raise ValueError('host-defined impact and prerequisite required')
        if mandatory is not None and mandatory not in MANDATORY:
            raise ValueError('unknown mandatory prerequisite')
        if type(expires_in) not in (int, float) or not 0 < expires_in <= 3600:
            raise ValueError('bounded assessment expiry required')
        # ARC owns the original task and parent relationship. A summary cannot
        # retarget an existing action to a cleaner task or omit parent evidence.
        inherited = []
        with self.ledger.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute("SELECT 1 FROM sqlite_master WHERE name='arc_decisions'").fetchone():
                arc = con.execute('SELECT task,record FROM arc_decisions WHERE id=? AND tenant=? AND agent=?',
                                  (decision_id, *scope)).fetchone()
                if arc:
                    if arc['task'] != task_id: raise PermissionError('ARC assessment belongs to a different task')
                    parent = json.loads(arc['record']).get('parent_decision_id')
                    if parent:
                        inherited = self.ledger.dependencies(actor, task_id, parent, con=con).get('claim_ids', [])
                        binding = con.execute('SELECT config FROM uc_policy_bindings WHERE tenant=? AND agent=? AND decision=?', (*scope, parent)).fetchone()
                        if binding:
                            parent_policy = json.loads(binding['config'])
                            required = required or parent_policy['required']
                            if parent_policy['impact'] == 'restricted': impact = 'restricted'
                            if parent_policy['mandatory']:
                                if mandatory and mandatory != parent_policy['mandatory']:
                                    raise PermissionError('child requires separate assessments for distinct mandatory prerequisites')
                                mandatory = parent_policy['mandatory']
            claims = {c.claim_id: c for c in self.ledger.claims(actor, task_id, con=con)}
            known = set(claims)
            if type(dependency_claim_ids) not in (list, tuple) or not set(dependency_claim_ids) <= known:
                raise ValueError('unknown or cross-scope dependency claims')
            existing = self.ledger.dependencies(actor, task_id, decision_id, con=con)
            deps = sorted(set(dependency_claim_ids) | set(inherited) | set(existing.get('claim_ids', existing.get('claims', []))))
            self.ledger.link(actor, task_id, decision_id, deps, con=con)
            config = _json({'impact': impact, 'required': required, 'mandatory': mandatory, 'action': action_id, 'task': task_id})
            bound = con.execute('SELECT config FROM uc_policy_bindings WHERE tenant=? AND agent=? AND decision=?', (*scope, decision_id)).fetchone()
            if bound and bound['config'] != config: raise PermissionError('host-bound decision policy cannot be downgraded or retargeted')
            con.execute('INSERT OR IGNORE INTO uc_policy_bindings VALUES(?,?,?,?)', (*scope, decision_id, config))
            revision = self.ledger.revision(actor, task_id, con=con)
            conflicts = self.ledger.open_conflicts(actor, task_id, con=con)
            affected = [c for c in conflicts if relevant(c, decision_id, deps, required)]
            mandatory_present = any(claims[cid].predicate == mandatory and usable(claims[cid], self.clock()) and normalized(claims[cid])[2] and
                (normalized(claims[cid])[0] is True if mandatory in {'consent', 'authorization'} else bool(normalized(claims[cid])[0])) for cid in deps)
            unavailable = []
            for cid in deps:
                if not usable(claims[cid], self.clock()): unavailable.append(cid)
                try: self.ledger.source(actor, claims[cid].source_ref, claims[cid].source_revision, con=con)
                except (PermissionError, LookupError): unavailable.append(cid)
            if unavailable:
                status = 'unavailable'
            elif mandatory is not None and (not mandatory_present or affected):
                status = 'defer_affected_action'
            elif required and not deps:
                status = 'verify_first'
            elif affected and (required or impact == 'restricted'):
                status = 'verify_first' if all(c.kind != 'tool_status_unknown' for c in affected) else 'unavailable'
            elif affected:
                status = 'proceed_with_qualification'
            else:
                status = 'proceed'
            permitted = status in {'proceed', 'proceed_with_qualification'}
            record = DecisionAssessment(decision_id, deps, [c.conflict_id for c in affected], status,
                [action_id] if permitted else [], [] if permitted else [action_id],
                [c.kind for c in affected] + ([mandatory] if mandatory and not mandatory_present else []) + (['source_unavailable'] if unavailable else []) + (['missing_required_evidence'] if required and not deps else []),
                'Only affected dependencies constrain this action; existing permissions still apply',
                POLICY_REVISION, revision, self.clock() + expires_in)
            con.execute('INSERT OR REPLACE INTO uc_assessments VALUES(?,?,?,?,?,?)',
                        (*scope, task_id, decision_id, action_id, record.to_json()))
            self.ledger.engine._event(con, scope, 'uncertainty_assessed',
                {'task_id': task_id, 'decision_id': decision_id, 'status': status, 'ledger_revision': revision})
        return record

    def bind(self, actor, decision_id, execution_task_id=None):
        scope = self.ledger.engine._scope(actor, 'runtime', 'operator')
        _id(execution_task_id or decision_id)
        with self.ledger.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute('SELECT 1 FROM uc_assessments WHERE tenant=? AND agent=? AND decision=?',
                           (*scope, decision_id)).fetchone() is None:
                raise ValueError('scoped assessment required before binding')
            previous = con.execute('SELECT decision FROM uc_dispatch_bindings WHERE tenant=? AND agent=? AND execution_task=?', (*scope, execution_task_id or decision_id)).fetchone()
            if previous and previous['decision'] != decision_id: raise PermissionError('execution uncertainty binding cannot be replaced')
            assessment = con.execute('SELECT action,task FROM uc_assessments WHERE tenant=? AND agent=? AND decision=?', (*scope, decision_id)).fetchone()
            if con.execute("SELECT 1 FROM sqlite_master WHERE name='arc_decisions'").fetchone():
                arc = con.execute('SELECT id,task,record FROM arc_decisions WHERE id=? AND tenant=? AND agent=?',
                                  (execution_task_id or decision_id, *scope)).fetchone()
                if arc and (arc['id'] != decision_id or arc['task'] != assessment['task'] or
                            json.loads(arc['record'])['action']['registered_tool'] != assessment['action']):
                    raise PermissionError('ARC dispatch requires its own task-bound action assessment')
            for context, strategy in self.ledger.engine._registry:
                if strategy == assessment['action']:
                    con.execute('INSERT OR IGNORE INTO uc_contexts VALUES(?,?,?)', (*scope, context))
            con.execute('INSERT OR REPLACE INTO uc_dispatch_bindings VALUES(?,?,?,?)',
                        (*scope, execution_task_id or decision_id, decision_id))

    def get(self, actor, decision_id, *, task_id=None):
        scope = self.ledger.engine._scope(actor, 'runtime', 'operator', 'auditor', 'evaluator', 'trainer')
        with self.ledger.engine._db() as con:
            row = con.execute('SELECT record,task FROM uc_assessments WHERE tenant=? AND agent=? AND decision=?',
                              (*scope, decision_id)).fetchone()
        if row is None: raise LookupError('scoped decision assessment unavailable')
        if task_id is not None and row['task'] != task_id: raise PermissionError('assessment belongs to a different task')
        return DecisionAssessment.from_json(row['record'])

    def recheck(self, con, actor, decision_id, action_id=None):
        scope = self.ledger.engine._scope(actor, 'runtime', 'operator', 'auditor')
        row = con.execute('SELECT * FROM uc_assessments WHERE tenant=? AND agent=? AND decision=?',
                          (*scope, decision_id)).fetchone()
        if row is None: raise PermissionError('uncertainty assessment unavailable')
        record = DecisionAssessment.from_json(row['record'])
        if record.ledger_revision != self.ledger.revision(actor, row['task'], con=con):
            raise RuntimeError('uncertainty ledger changed; reassessment required')
        if record.expires_at <= self.clock() or record.policy_revision != POLICY_REVISION:
            raise RuntimeError('uncertainty assessment expired or incompatible')
        claims = {c.claim_id:c for c in self.ledger.claims(actor, row['task'], con=con)}
        for cid in record.dependency_claim_ids:
            claim = claims.get(cid)
            if claim is None or not usable(claim, self.clock()):
                raise RuntimeError('prerequisite expired or unavailable; reassessment required')
            self.ledger.source(actor, claim.source_ref, claim.source_revision, con=con)
        if record.status not in {'proceed', 'proceed_with_qualification'}:
            raise PermissionError('unresolved prerequisite blocks this action')
        if action_id is not None and action_id not in record.permitted_action_ids:
            raise PermissionError('assessment does not authorize this registered action')
        return record


def dispatch_guard(con, engine, actor, task, strategy):
    """Existing dispatcher transaction calls this even after bare-engine restart."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='uc_dispatch_bindings'").fetchone(): return
    row = con.execute('SELECT decision FROM uc_dispatch_bindings WHERE tenant=? AND agent=? AND execution_task=?',
                      (actor.tenant, actor.agent, task.task_id)).fetchone()
    if row is None:
        enabled = con.execute('SELECT 1 FROM uc_contexts WHERE tenant=? AND agent=? AND context=?', (actor.tenant, actor.agent, task.context)).fetchone()
        if enabled: raise PermissionError('uncertainty-enabled context requires a bound assessment')
        return
    policy = getattr(engine, '_uncertainty_policy', None)
    if policy is None: raise PermissionError('persistent uncertainty binding requires configured ledger gate')
    policy.recheck(con, actor, row['decision'], strategy)
