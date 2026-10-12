"""Scoped conflict restrictions for the real Memento registry/planner/coordinator.

The optional package is imported lazily. Existing world-model authority and
uncertainty records must share the same host capability issuer and SQLite file.
This adapter never grants eligibility or changes a source-of-truth claim.
"""
import json
from pathlib import Path
from ..governed_learning_v20 import _id, _json
from .ledger import StaleRevision, digest
from .reconciliation import usable


class WorldModelUncertainty:
    def __init__(self, ledger, world_ledger):
        if (Path(ledger.engine.path).resolve() != Path(world_ledger.path).resolve()
                or ledger.engine.authority is not world_ledger.authority):
            raise PermissionError('world model and uncertainty require the same host store and authority')
        self.ledger, self.world = ledger, world_ledger
        with ledger.engine._db() as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS uc_world_modes(tenant TEXT,agent TEXT,mode TEXT,PRIMARY KEY(tenant,agent));
            CREATE TABLE IF NOT EXISTS uc_world_rules(tenant TEXT,agent TEXT,rule TEXT,task TEXT,claims TEXT,review TEXT,PRIMARY KEY(tenant,agent,rule));
            ''')
        world_ledger._uncertainty_adapter = self

    def enable(self, actor, *, mode='shadow'):
        scope = self.ledger.scope(actor, roles=('operator',))
        if mode not in ('off', 'shadow', 'enforce'):
            raise ValueError('known uncertainty mode required')
        with self.ledger.engine._db() as con:
            con.execute('INSERT OR REPLACE INTO uc_world_modes VALUES(?,?,?)', (*scope, mode))
        return mode

    def bind_rule(self, actor, *, task_id, rule_id, claim_ids, review_ref):
        scope = self.ledger.scope(actor, task_id, roles=('operator',))
        _id(rule_id); _id(review_ref)
        if type(claim_ids) is not list or not 1 <= len(claim_ids) <= 64 or len(set(claim_ids)) != len(claim_ids):
            raise ValueError('bounded explicit rule dependencies required')
        claims = {c.claim_id for c in self.ledger.claims(actor, task_id)}
        if not set(claim_ids) <= claims:
            raise PermissionError('rule dependency outside authenticated task')
        # Host bindings are immutable. New rules need new identities; an agent
        # cannot drop a disputed dependency and preserve its old reviewed rule ID.
        with self.ledger.engine._db() as con:
            old = con.execute('SELECT task,claims FROM uc_world_rules WHERE tenant=? AND agent=? AND rule=?',
                              (*scope[:2], rule_id)).fetchone()
            expected = (task_id, _json(sorted(claim_ids)))
            if old:
                if tuple(old) != expected:
                    raise PermissionError('reviewed rule dependencies are immutable')
                return rule_id
        self.ledger.link(actor, task_id, 'wm-rule-' + digest(rule_id), claim_ids, rule_ids=[rule_id])
        with self.ledger.engine._db() as con:
            con.execute('INSERT OR IGNORE INTO uc_world_rules VALUES(?,?,?,?,?,?)',
                        (*scope[:2], rule_id, task_id, expected[1], review_ref))
        return rule_id

    def report(self, actor, rules, *, con=None):
        from contextlib import nullcontext
        scope = self.ledger.scope(actor)
        result = {'status':'supported', 'rules':[], 'task_revisions':{}, 'conflict_ids':[],
                  'promotion_authorized':False}
        with (nullcontext(con) if con is not None else self.ledger.engine._db()) as db:
            for rule in rules:
                ident = _id(rule['rule_id'])
                row = db.execute('SELECT * FROM uc_world_rules WHERE tenant=? AND agent=? AND rule=?',
                                 (*scope, ident)).fetchone()
                item = {'rule_id':ident, 'status':'unavailable', 'conflict_ids':[]}
                if row:
                    task = row['task']; dependencies = set(json.loads(row['claims']))
                    known = {c.claim_id:c for c in self.ledger.claims(actor, task, con=db)}
                    active = dependencies <= set(known)
                    for cid in dependencies & set(known):
                        claim = known[cid]
                        if not usable(claim, self.ledger.clock()): active = False
                        try:
                            self.ledger.source(actor, claim.source_ref, claim.source_revision, con=db)
                        except PermissionError:
                            active = False
                    conflicts = [c for c in self.ledger.conflicts(actor, task, True, con=db)
                                 if dependencies & set(c.claim_ids) or ident in c.affected_rule_ids]
                    item.update(status='unavailable' if not active else ('hypothesis_disputed' if conflicts else 'supported'),
                                conflict_ids=[c.conflict_id for c in conflicts], task_id=task)
                    result['task_revisions'][task] = self.ledger.revision(actor, task, con=db)
                    result['conflict_ids'].extend(item['conflict_ids'])
                result['rules'].append(item)
                if item['status'] != 'supported':
                    result['status'] = 'review_required'
        result['conflict_ids'] = sorted(set(result['conflict_ids']))
        return result

    def require_supported(self, actor, rules, *, con=None):
        report = self.report(actor, rules, con=con)
        if report['status'] != 'supported':
            raise PermissionError('world-model dependencies unresolved; retain incumbent and review affected rules')
        return report

    def plan(self, actor, model_id, initial, allowed_actions):
        from ..world_model.registry import Registry
        from ..world_model.planner import plan
        model = Registry(self.world).get(actor, model_id)
        if model['state'] not in ('frozen','eligible'):
            raise PermissionError('frozen world model required for scoped simulation planning')
        report = self.require_supported(actor, model['rules'])
        result = plan(model['program'], initial, allowed_actions)
        return {**result, 'model_id':model_id, 'uncertainty':report, 'simulation_only':True, 'deployment_authorized':False}

    def validate_dispatch(self, actor, decision, observed, allowed_actions, remaining_actions):
        from ..world_model.registry import Registry
        from ..world_model.planner import validate_dispatch
        with self.world.db() as con:
            model = Registry(self.world).get(actor, decision['model_id'])
            if model['state'] not in ('frozen','eligible'):
                raise PermissionError('revoked or unfrozen world model cannot dispatch')
            current = self.require_supported(actor, model['rules'], con=con)
            if decision.get('uncertainty', {}).get('task_revisions') != current['task_revisions']:
                raise StaleRevision('world-model plan invalidated by evidence; replan')
            return validate_dispatch(decision, model['program'], observed, allowed_actions, remaining_actions)

    def rulebook(self, actor, model_id):
        from ..world_model.registry import Registry
        from ..world_model.rulebook import render
        model = Registry(self.world).get(actor, model_id)
        report = self.report(actor, model['rules'])
        return {'text':render(model['rules']) + '\n\nUncertainty: ' + _json(report), 'uncertainty':report}


def guard(world_ledger, actor, rules, *, con=None):
    """Called by actual registry/release boundaries; restart omissions fail closed."""
    from contextlib import nullcontext
    world_ledger.scope(actor, 'runtime','trainer','evaluator','operator','auditor')
    with (nullcontext(con) if con is not None else world_ledger.db()) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='uc_world_modes'").fetchone():
            return None
        row = db.execute('SELECT mode FROM uc_world_modes WHERE tenant=? AND agent=?',
                         (actor.tenant, actor.agent)).fetchone()
        if row is None or row['mode'] == 'off':
            return None
        adapter = getattr(world_ledger, '_uncertainty_adapter', None)
        if adapter is None:
            raise PermissionError('persisted world-model uncertainty requires its host adapter')
        return adapter.require_supported(actor, rules, con=db)


def checkpoint_state(world_ledger, actor, body, *, con):
    """Mandatory authoritative IDs survive coordinator summarization/restart."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='uc_world_modes'").fetchone():return None
    row=con.execute('SELECT mode FROM uc_world_modes WHERE tenant=? AND agent=?',(actor.tenant,actor.agent)).fetchone()
    if row is None or row['mode']=='off':return None
    adapter=getattr(world_ledger,'_uncertainty_adapter',None)
    if adapter is None:raise PermissionError('persisted world uncertainty requires its host adapter')
    rules=body.get('proposal',{}).get('rules',[])
    report=adapter.report(actor,rules,con=con)
    # Preserve source-linked conflicts even before a proposal has been generated.
    for row in con.execute('SELECT DISTINCT task FROM uc_world_rules WHERE tenant=? AND agent=?',(actor.tenant,actor.agent)):
        task=row['task']
        report['task_revisions'][task]=adapter.ledger.revision(actor,task,con=con)
        report['conflict_ids'].extend(c.conflict_id for c in adapter.ledger.open_conflicts(actor,task,con=con))
    report['conflict_ids']=sorted(set(report['conflict_ids']))
    report['complete']=True
    return report
