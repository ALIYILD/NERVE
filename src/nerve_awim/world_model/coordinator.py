"""Durable offline state machine with transactional claims and fencing.

Only the fixed scripted proposer is supported. The host owns all roles; do not
expose this coordinator to untrusted agents or execute provider-authored code.
"""
import json
import time
import uuid
from .compiler import compile_rules
from .contracts import Policy, canonical, digest, BudgetExhausted, StaleWorker, IntegrityError
from .evaluator import Evaluator
from .fidelity import assess
from .reflection import reflect
from .registry import Registry
from .replay import replay

PHASES = ('capture','reflect','compile','verify','selection','freeze','final','register','stopped')


class Coordinator:
    def __init__(self, ledger, *, trainer, evaluator, policy):
        ledger.authority.require(trainer,'trainer')
        ledger.authority.require(evaluator,'evaluator')
        if (trainer.tenant,trainer.agent) != (evaluator.tenant,evaluator.agent):
            raise PermissionError('coordinator roles must share scope')
        self.ledger, self.trainer, self.evaluator, self.policy = ledger,trainer,evaluator,policy
        self.scope = ledger.scope(trainer,'trainer')
        self.registry, self.review = Registry(ledger),Evaluator(ledger,policy)

    def create(self):
        if not self.policy.enabled:
            raise PermissionError('world-model feature disabled')
        run_id = uuid.uuid4().hex
        body = {'policy':self.policy.to_dict(),'started_at':time.time(),'model_id':None,
                'reports':{},'stop_reason':None,'provider_calls':0,'provider_cost':0,
                'deployment_authorized':False,'evidence_mode':'scripted offline proposer'}
        with self.ledger.db() as db:
            db.execute('INSERT INTO wm_runs VALUES(?,?,?,?,?,?,?,?)',
                       (self.scope,run_id,'capture',0,None,0,0,canonical(body)))
        # Reserve before any proposal. If interrupted here, capture retries the same reservation.
        return run_id

    def status(self, run_id):
        with self.ledger.db() as db:
            row = db.execute('SELECT * FROM wm_runs WHERE scope=? AND id=?',(self.scope,run_id)).fetchone()
            if row is None:
                raise LookupError('run outside scope')
            result = dict(row)
            result['body'] = json.loads(result['body'])
            result['checkpoint_hash'] = digest(result['body'])
            return result

    def claim(self, run_id, owner):
        with self.ledger.db() as db:
            row = db.execute('SELECT * FROM wm_runs WHERE scope=? AND id=?',(self.scope,run_id)).fetchone()
            if row is None:
                raise LookupError('run outside scope')
            if row['lease_until'] > time.time():
                raise StaleWorker('active worker owns run')
            fence = row['fence']+1
            db.execute('UPDATE wm_runs SET owner=?,fence=?,lease_until=? WHERE scope=? AND id=?',
                       (owner,fence,time.time()+30,self.scope,run_id))
        return fence

    def checkpoint(self, run_id, owner, fence, phase, body):
        with self.ledger.db() as db:
            updated = db.execute('UPDATE wm_runs SET phase=?,body=?,lease_until=? WHERE scope=? AND id=? '
                'AND owner=? AND fence=? AND lease_until>?',
                (phase,canonical(body),time.time()+30,self.scope,run_id,owner,fence,time.time())).rowcount
            if not updated:
                raise StaleWorker('expired or superseded worker cannot checkpoint')
            db.execute('INSERT INTO wm_events VALUES(NULL,?,?,?,?)',
                       (self.scope,run_id,phase,canonical({'checkpoint_hash':digest(body)})))

    def _reserve_work(self, run_id, owner, fence, units, *, body, category):
        # Maximum total simulator/evaluation transition attempts; retries count again.
        limit = self.policy.max_work_units
        usage = body.setdefault("reserved_work_by_category", {})
        previous_usage = usage.get(category, 0)
        usage[category] = previous_usage+units
        with self.ledger.db() as db:
            updated = db.execute('UPDATE wm_runs SET budget=budget+?,lease_until=?,body=? WHERE scope=? AND id=? '
                'AND owner=? AND fence=? AND lease_until>? AND budget+?<=?',
                (units,time.time()+30,canonical(body),self.scope,run_id,owner,fence,time.time(),units,limit)).rowcount
            if not updated:
                if previous_usage:
                    usage[category] = previous_usage
                else:
                    usage.pop(category, None)
                row = db.execute('SELECT owner,fence,lease_until FROM wm_runs WHERE scope=? AND id=?',(self.scope,run_id)).fetchone()
                if not row or row['owner'] != owner or row['fence'] != fence or row['lease_until'] <= time.time():
                    raise StaleWorker('work claim stale')
                raise BudgetExhausted('durable simulator/evaluator budget exhausted')

    def resume(self, run_id, *, stop_after=None):
        current = self.status(run_id)
        if Policy.load(current['body']['policy']) != self.policy:
            raise IntegrityError('run policy is immutable')
        if current['phase'] == 'stopped':
            return current
        owner = uuid.uuid4().hex
        fence = self.claim(run_id,owner)
        current = self.status(run_id)
        body = current['body']
        phase = current['phase']
        try:
            while phase != 'stopped':
                if time.time()-body['started_at'] > self.policy.max_run_seconds:
                    body['stop_reason'] = 'wall_budget'
                    self.checkpoint(run_id,owner,fence,'stopped',body)
                    break
                attempts = body.setdefault('attempts', {})
                attempts[phase] = attempts.get(phase, 0)+1
                if attempts[phase] > self.policy.max_revision_attempts_per_candidate:
                    body['stop_reason'] = 'phase_retry_budget'
                    self.checkpoint(run_id,owner,fence,'stopped',body)
                    break
                self.checkpoint(run_id,owner,fence,phase,body)
                self._reserve_work(run_id,owner,fence,1,body=body,category="phase_dispatch")
                if phase == 'capture':
                    self.review.reserve_final(self.evaluator,run_id)
                elif phase == 'reflect':
                    training = self.ledger.episodes(self.trainer)
                    proposals = []
                    if self.policy.model_backend == 'declarative-frame-v1':
                        from .generalization import infer
                        proposal = infer(training)
                        if proposal['rules']:
                            proposals.append(proposal)
                    exact_proposal = reflect(training)
                    exact_proposal['backend'] = 'declarative-exact-v1'
                    if exact_proposal['rules']:
                        proposals.append(exact_proposal)
                    proposals = proposals[:min(self.policy.max_population,self.policy.max_candidates_per_generation)]
                    if not proposals:
                        body['stop_reason'] = exact_proposal['failure_class']
                        self.checkpoint(run_id,owner,fence,'stopped',body)
                        break
                    body['proposal'] = proposals[0]
                    body['candidate_proposals'] = proposals
                    body['generation'] = 1
                elif phase == 'compile':
                    candidates = []
                    body['compilation_failures'] = []
                    for proposal in body.get('candidate_proposals',[body['proposal']]):
                        rules = proposal['rules']
                        backend = proposal.get('backend',self.policy.model_backend)
                        try:
                            model_id = self.registry.put(self.trainer,rules,compile_rules(rules,backend=backend),self.policy)
                        except ValueError as error:
                            body['compilation_failures'].append({'backend':backend,'reason':str(error)[:512]})
                            continue
                        candidates.append({'model_id':model_id,'backend':backend,'reports':{}})
                    body['candidates'] = candidates
                    if not candidates:
                        body['stop_reason'] = 'compilation_failed'
                        self.checkpoint(run_id,owner,fence,'stopped',body)
                        break
                    body['model_id'] = candidates[0]['model_id']
                elif phase == 'verify':
                    episodes = self.ledger.episodes(self.trainer)
                    candidates = body.setdefault('candidates',[{'model_id':body['model_id'],'reports':{}}])
                    for candidate in candidates:
                        model = self.registry.get(self.evaluator,candidate['model_id'])
                        self._reserve_work(run_id,owner,fence,sum(len(e['transitions']) for e in episodes),body=body,category='training_replay')
                        candidate['reports']['replay'] = replay(model['program'],episodes)
                        candidate['reports']['fidelity'] = assess(model['rules'],model['program'])
                        candidate['verified'] = candidate['reports']['replay']['replay_pass'] and candidate['reports']['fidelity']['status'] == 'pass'
                    if not any(c['verified'] for c in candidates):
                        body['stop_reason'] = 'verification_failed'
                        self.checkpoint(run_id,owner,fence,'stopped',body)
                        break
                    body['reports'].update(candidates[0]['reports'])
                elif phase == 'selection':
                    candidates = body.get('candidates',[{'model_id':body['model_id'],'verified':True,'reports':body['reports']}])
                    for candidate in candidates:
                        if not candidate['verified']:
                            continue
                        for split in ('selection','regression'):
                            episodes = self.ledger.episodes(self.evaluator,split)
                            self._reserve_work(run_id,owner,fence,101*len(episodes),body=body,category='evaluation_and_planning')
                            candidate['reports'][split] = self.review.evaluate(self.evaluator,candidate['model_id'],split)
                    survivors = [c for c in candidates if c['verified'] and all(c['reports'][s]['replay_pass'] for s in ('selection','regression'))]
                    if not survivors:
                        body['stop_reason'] = 'selection_or_regression_failed'
                        self.checkpoint(run_id,owner,fence,'stopped',body)
                        break
                    def objective(candidate):
                        report = candidate['reports']['selection']
                        return (sum(m['candidate_success'] for m in report['metrics_by_family'].values()),
                                -report['unknown_fraction'],candidate['model_id'])
                    winner = max(survivors,key=objective)
                    body['model_id'] = winner['model_id']
                    body['reports'] = dict(winner['reports'])
                    body['selection_trace'] = {'objective':'success_then_unknown_then_stable_hash',
                        'candidate_ids':[c['model_id'] for c in candidates],'winner':winner['model_id']}
                elif phase == 'freeze':
                    self.registry.freeze(self.evaluator,body['model_id'])
                elif phase == 'final':
                    episodes = self.ledger.episodes(self.evaluator,'final')
                    self._reserve_work(run_id,owner,fence,101*len(episodes),body=body,category="evaluation_and_planning")
                    try:
                        body['reports']['final'] = self.review.evaluate(self.evaluator,body['model_id'],'final',run_id=run_id)
                    except IntegrityError:
                        body['stop_reason'] = 'final_consumed_without_recoverable_report'
                        self.checkpoint(run_id,owner,fence,'stopped',body)
                        break
                elif phase == 'register':
                    # Never infer gain or eligibility from perfect memorized replay.
                    body['stop_reason'] = 'inconclusive_independent_gain_not_established'
                    body['eligibility'] = False
                next_phase = PHASES[PHASES.index(phase)+1]
                self.checkpoint(run_id,owner,fence,next_phase,body)
                completed, phase = phase,next_phase
                if stop_after == completed:
                    break
        except BudgetExhausted:
            body['stop_reason'] = 'work_budget'
            self.checkpoint(run_id,owner,fence,'stopped',body)
        finally:
            with self.ledger.db() as db:
                db.execute('UPDATE wm_runs SET owner=NULL,lease_until=0 WHERE scope=? AND id=? AND owner=? AND fence=?',
                           (self.scope,run_id,owner,fence))
        return self.status(run_id)
