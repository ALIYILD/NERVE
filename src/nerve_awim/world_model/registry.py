"""Immutable content-addressed artifacts; eligibility is not activation."""
import json
from .contracts import digest, canonical, IntegrityError, REVISION, Rule
from .compiler import validate_program
from .fidelity import assess


class Registry:
    def __init__(self, ledger):
        self.ledger = ledger

    def put(self, actor, rules, program, policy, *, parent=None):
        scope = self.ledger.scope(actor,'trainer')
        validate_program(program)
        if type(rules) is not list or not 1 <= len(rules) <= 256:
            raise ValueError('bounded canonical rules required')
        rules = [Rule.load(raw).to_dict() for raw in rules]
        episodes = self.ledger.episodes(actor)
        evidence = {r['id']:r for e in episodes for r in e['transitions']}
        for rule in rules:
            for reference in rule['supporting_transition_ids'] + rule['contradicting_transition_ids']:
                if reference not in evidence or evidence[reference]['status'] != 'observed':
                    raise ValueError('rule references missing observed training evidence')
            for reference in rule['supporting_transition_ids']:
                row = evidence[reference]
                if (row['previous'],row['action'],row['outcome'],row['completion']) != (
                    rule['preconditions'],rule['action'],rule['predicted_effect'],rule['completion']):
                    raise ValueError('supporting evidence does not support rule')
        if parent is not None:
            self.get(actor,parent)
        body = {'schema_version':1,'scope':scope,'parent_model_id':parent,
                'rules':rules,'program':program,'rulebook_hash':digest(rules),
                'executable_hash':digest(program),'compiler_revision':'exact-v1',
                'provider_model_id':'scripted-offline','prompt_hash':digest('scripted-offline-v1'),
                'environment_revision':REVISION,'observation_contract_revision':REVISION,
                'evidence_manifest_hash':digest(episodes),'dependency_manifest_hash':digest('stdlib-only-v1'),
                'sandbox_profile':'trusted-declarative-process-v1','evaluation_policy_hash':digest(policy.to_dict())}
        model_id = digest(body)
        with self.ledger.db() as db:
            db.execute('INSERT OR IGNORE INTO wm_artifacts VALUES(?,?,?,?)', (scope,model_id,canonical(body),'candidate'))
        return model_id

    def get(self, actor, model_id):
        scope = self.ledger.scope(actor,'trainer','evaluator','auditor','runtime','operator')
        with self.ledger.db() as db:
            row = db.execute('SELECT * FROM wm_artifacts WHERE scope=? AND id=?',(scope,model_id)).fetchone()
            if row is None:
                raise LookupError('model not in authorized scope')
            body = json.loads(row['body'])
            if digest(body) != model_id or digest(body['rules']) != body['rulebook_hash'] or digest(body['program']) != body['executable_hash']:
                raise IntegrityError('artifact content mismatch')
            return {**body,'model_id':model_id,'state':row['state']}

    def freeze(self, actor, model_id):
        scope = self.ledger.scope(actor,'evaluator')
        model = self.get(actor,model_id)
        if assess(model['rules'],model['program'])['status'] != 'pass':
            raise IntegrityError('fidelity disagreement')
        with self.ledger.db() as db:
            from ..uncertainty.world_model_adapter import guard
            guard(self.ledger, actor, model['rules'], con=db)
            db.execute("UPDATE wm_artifacts SET state='frozen' WHERE scope=? AND id=? AND state='candidate'",(scope,model_id))
        return model_id

    def invalidate(self, actor, model_id):
        scope = self.ledger.scope(actor,'operator')
        self.get(actor,model_id)
        with self.ledger.db() as db:
            db.execute("UPDATE wm_artifacts SET state='revoked' WHERE scope=? AND id=?",(scope,model_id))
