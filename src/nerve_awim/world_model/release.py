"""Atomic local simulated release bundles. Never routes external actions.

Uses existing NERVE operator capabilities and PromotionMonitor budget validation.
Actual canary/promotion is unavailable until independently established eligibility
and an authenticated deployment host are supplied. This models rollback only.
"""
import json
from .contracts import canonical, digest, IntegrityError, StaleWorker
from .registry import Registry
from ..promotion_monitor_v24 import PromotionMonitor


class SimulatedRelease:
    def __init__(self, ledger):
        self.ledger, self.registry = ledger,Registry(ledger)

    def status(self, actor):
        scope=self.ledger.scope(actor,'operator','runtime','auditor')
        with self.ledger.db() as db:
            row=db.execute('SELECT * FROM wm_releases WHERE scope=?',(scope,)).fetchone()
            return dict(row) if row else {'generation':0,'active':None,'previous':None,'body':'{}'}

    def authorize(self, actor, model_id, *, expected_generation, planner_config, reason, latency_ms=5000):
        scope=self.ledger.scope(actor,'operator')
        if type(expected_generation) is not int or expected_generation < 0 or type(reason) is not str or not 1 <= len(reason) <= 512:
            raise ValueError('reviewed reason and current generation required')
        if planner_config != {'max_depth':5,'max_nodes':100}:
            raise ValueError('reviewed fixed simulation planner configuration required')
        PromotionMonitor.validate_budget(latency_ms)
        model=self.registry.get(actor,model_id)
        if model['state'] not in ('frozen','eligible'):
            raise IntegrityError('frozen compatible model required')
        bundle={'model_id':model_id,'rulebook_hash':model['rulebook_hash'],
                'executable_hash':model['executable_hash'],'planner_config':planner_config,
                'retrieval_pointer':model['rulebook_hash'],'revision':model['environment_revision'],
                'latency_ms':latency_ms,'simulation_only':True,'deployment_authorized':False}
        with self.ledger.db() as db:
            from ..uncertainty.world_model_adapter import guard
            guard(self.ledger, actor, model['rules'], con=db)
            current=db.execute('SELECT * FROM wm_releases WHERE scope=?',(scope,)).fetchone()
            generation=current['generation'] if current else 0
            if generation != expected_generation:
                raise StaleWorker('stale release authorization')
            previous=json.loads(current['body'])['active_bundle'] if current else None
            body={'active_bundle':bundle,'previous_bundle':previous,'reason':reason,'plan_cache_generation':generation+1}
            db.execute('INSERT OR REPLACE INTO wm_releases VALUES(?,?,?,?,?)',
                       (scope,generation+1,model_id,previous['model_id'] if previous else None,canonical(body)))
        return self.status(actor)

    def monitor(self, actor, *, expected_generation, observed_ok, elapsed_ms):
        scope=self.ledger.scope(actor,'runtime')
        if type(observed_ok) is not bool or type(elapsed_ms) not in (int,float) or elapsed_ms < 0:
            raise ValueError('host-observed result required')
        canonical(elapsed_ms)
        with self.ledger.db() as db:
            current=db.execute('SELECT * FROM wm_releases WHERE scope=?',(scope,)).fetchone()
            if not current or current['generation'] != expected_generation:
                raise StaleWorker('stale monitor cannot overwrite a newer release')
            body=json.loads(current['body'])
            bundle=body['active_bundle']
            if bundle is None:
                return {'status':'unavailable','deployment_authorized':False}
            # Check integrity inside the same transaction without a nested connection.
            artifact=db.execute('SELECT body,state FROM wm_artifacts WHERE scope=? AND id=?',(scope,bundle['model_id'])).fetchone()
            integrity=bool(artifact and digest(json.loads(artifact['body'])) == bundle['model_id'] and artifact['state'] != 'revoked')
            if integrity:
                from ..uncertainty.world_model_adapter import guard
                try:
                    guard(self.ledger, actor, json.loads(artifact['body'])['rules'], con=db)
                except PermissionError:
                    integrity=False
            if observed_ok and elapsed_ms <= bundle['latency_ms'] and integrity:
                return {'status':'simulated_pass','deployment_authorized':False}
            previous=body['previous_bundle']
            if previous:
                artifact=db.execute('SELECT body,state FROM wm_artifacts WHERE scope=? AND id=?',(scope,previous['model_id'])).fetchone()
                if not artifact or digest(json.loads(artifact['body'])) != previous['model_id'] or artifact['state'] == 'revoked':
                    previous=None
                else:
                    from ..uncertainty.world_model_adapter import guard
                    try:
                        guard(self.ledger, actor, json.loads(artifact['body'])['rules'], con=db)
                    except PermissionError:
                        previous=None
            body.update(active_bundle=previous,previous_bundle=None,reason='simulated_regression_or_integrity',
                        plan_cache_generation=current['generation']+1)
            db.execute('UPDATE wm_releases SET generation=generation+1,active=?,previous=NULL,body=? WHERE scope=?',
                       (previous['model_id'] if previous else None,canonical(body),scope))
        return {'status':'simulated_rollback' if previous else 'unavailable',
                'reconstruct_from_initial_observation':True,'deployment_authorized':False}
