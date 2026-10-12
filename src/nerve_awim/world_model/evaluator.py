"""Evaluator-only final reservations, consumed before evaluation dispatch."""
import json
from .contracts import canonical, digest, IntegrityError, Policy
from .fidelity import assess
from .planner import plan
from .registry import Registry
from .replay import replay


class Evaluator:
    def __init__(self, ledger, policy=None):
        self.ledger, self.registry = ledger, Registry(ledger)
        self.policy = policy

    def reserve_final(self, actor, run_id):
        scope = self.ledger.scope(actor,'evaluator')
        episodes = self.ledger.episodes(actor,'final')
        if not episodes:
            raise ValueError('fresh final episodes required')
        with self.ledger.db() as db:
            existing = db.execute('SELECT source,run FROM wm_final WHERE scope=?',(scope,)).fetchall()
            occupied = {r['source']:r['run'] for r in existing}
            for episode in episodes:
                if episode['source'] in occupied:
                    if occupied[episode['source']] != run_id:
                        raise IntegrityError('final source already reserved by another run')
                else:
                    db.execute('INSERT INTO wm_final VALUES(?,?,?,?,0)',(scope,episode['source'],run_id,None))
        return [e['source'] for e in episodes]

    def recover_final(self, actor, model_id, *, run_id):
        """Read a committed report without executing or reopening final evidence.

        A claim without a report is deliberately unrecoverable. Storage is trusted;
        hashes detect accidental corruption, not a malicious database administrator.
        """
        scope = self.ledger.scope(actor, 'evaluator')
        self.registry.get(actor, model_id)  # Includes runtime fingerprint validation.
        with self.ledger.db() as db:
            row = db.execute('SELECT * FROM wm_final_reports WHERE scope=? AND run=?',
                             (scope, run_id)).fetchone()
            if row is None:
                return None
            if row['model'] != model_id:
                raise IntegrityError('final report model mismatch')
            if row['report'] is None:
                raise IntegrityError('final consumed without committed report')
            report = json.loads(row['report'])
            claims = db.execute('SELECT * FROM wm_final WHERE scope=? AND run=?',
                                (scope, run_id)).fetchall()
            if (digest(report) != row['report_hash'] or report['model_id'] != model_id
                    or report['evidence_hashes'] != [row['evidence_hash']]
                    or not claims or any(not r['consumed'] or r['model'] != model_id for r in claims)):
                raise IntegrityError('final report integrity failure')
            return report

    def evaluate(self, actor, model_id, split, *, run_id=None):
        scope = self.ledger.scope(actor,'evaluator')
        if split not in ('selection','regression','final'):
            raise ValueError('invalid evaluation split')
        model = self.registry.get(actor,model_id)
        pinned = Policy.load(model['evaluation_policy']) if 'evaluation_policy' in model else (self.policy or Policy())
        if self.policy is not None and self.policy != pinned:
            raise IntegrityError('evaluator policy differs from frozen model policy')
        if model['state'] == 'revoked':
            raise IntegrityError('revoked model')
        episodes = self.ledger.episodes(actor,split)
        if not episodes:
            raise ValueError('nonempty evaluation split required')
        if split == 'final':
            if model['state'] != 'frozen' or not run_id:
                raise IntegrityError('frozen artifact and reserved run required')
            with self.ledger.db() as db:
                rows = db.execute('SELECT * FROM wm_final WHERE scope=? AND run=?',(scope,run_id)).fetchall()
                if {r['source'] for r in rows} != {e['source'] for e in episodes} or any(r['consumed'] for r in rows):
                    raise IntegrityError('final evidence missing or already consumed')
                db.execute('INSERT INTO wm_final_reports VALUES(?,?,?,?,NULL,NULL)',
                           (scope,run_id,model_id,digest(episodes)))
                db.execute('UPDATE wm_final SET model=?,consumed=1 WHERE scope=? AND run=?',(model_id,scope,run_id))
        # No final details are returned to the proposer. The trusted host receives aggregates.
        result = replay(model['program'],episodes)
        fidelity = assess(model['rules'],model['program'])
        families = {}
        for episode in episodes:
            actions = sorted({t['action'] for t in episode['transitions']})
            decision = plan(model['program'],episode['initial'],actions,
                            max_depth=pinned.max_plan_depth,
                            max_nodes=pinned.max_simulated_nodes_per_decision)
            # Independent observed action trace checks actual completion. A model's goal
            # prediction alone never counts as task success.
            observed = {tuple(t['action'] for t in episode['transitions']):
                        episode['transitions'][-1]['completion'] is True}
            success = decision['status'] == 'planned' and observed.get(tuple(decision['actions']),False)
            family = families.setdefault(episode['family'],{'tasks':0,'candidate_success':0})
            family['tasks'] += 1
            family['candidate_success'] += int(success)
            # Explicit fixed baseline: attempt the last stage directly. Host observation
            # must be supplied separately; absent baseline outcome stays unknown.
        report = {'model_id':model_id,'split':split,'replay_pass':result['replay_pass'],
                'fidelity_status':fidelity['status'],'unknown_fraction':result['unknown_fraction'],
                'metrics_by_family':families,'failures':[] if split == 'final' else result['failures'],
                'evaluator_revision':'exact-episodes-v1','evidence_hashes':[digest(episodes)],
                'holdout_status':'consumed' if split == 'final' else 'not_opened',
                'eligibility':False,'deployment_authorized':False,
                'limitation':'baseline comparison and semantic split independence not established'}

        if split == 'final':
            with self.ledger.db() as db:
                updated = db.execute('UPDATE wm_final_reports SET report=?,report_hash=? '
                    'WHERE scope=? AND run=? AND model=? AND evidence_hash=? AND report IS NULL',
                    (canonical(report),digest(report),scope,run_id,model_id,digest(episodes)))
                if updated.rowcount != 1:
                    raise IntegrityError('final report commit conflict')
        return report
