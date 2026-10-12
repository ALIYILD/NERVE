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

    def _reserve_work(self, run_id, owner, fence, units):
        # Maximum total simulator/evaluation transition attempts; retries count again.
        limit = self.policy.max_generations*self.policy.max_candidates_per_generation*100
        with self.ledger.db() as db:
            updated = db.execute('UPDATE wm_runs SET budget=budget+?,lease_until=? WHERE scope=? AND id=? '
                'AND owner=? AND fence=? AND lease_until>? AND budget+?<=?',
                (units,time.time()+30,self.scope,run_id,owner,fence,time.time(),units,limit)).rowcount
            if not updated:
                row = db.execute('SELECT owner,fence,lease_until FROM wm_runs WHERE scope=? AND id=?',(self.scope,run_id)).fetchone()
                if not row or row['owner'] != owner or row['fence'] != fence or row['lease_until'] <= time.time():
                    raise StaleWorker('work claim stale')
                raise BudgetExhausted('durable simulator/evaluator budget exhausted')

    def resume(self, run_id, *, stop_after=None):
        current = self.status(run_id)
        if current['body']['policy'] != self.policy.to_dict():
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
                self._reserve_work(run_id,owner,fence,1)
                if phase == 'capture':
                    self.review.reserve_final(self.evaluator,run_id)
                elif phase == 'reflect':
                    proposal = reflect(self.ledger.episodes(self.trainer))
                    body['proposal'] = proposal
                    if proposal['decision'] == 'retain':
                        body['stop_reason'] = proposal['failure_class']
                        self.checkpoint(run_id,owner,fence,'stopped',body)
                        break
                elif phase == 'compile':
                    rules = body['proposal']['rules']
                    body['model_id'] = self.registry.put(self.trainer,rules,compile_rules(rules),self.policy)
                elif phase == 'verify':
                    model = self.registry.get(self.evaluator,body['model_id'])
                    episodes = self.ledger.episodes(self.trainer)
                    self._reserve_work(run_id,owner,fence,sum(len(e['transitions']) for e in episodes))
                    body['reports']['replay'] = replay(model['program'],episodes)
                    body['reports']['fidelity'] = assess(model['rules'],model['program'])
                    if not body['reports']['replay']['replay_pass'] or body['reports']['fidelity']['status'] != 'pass':
                        body['stop_reason'] = 'verification_failed'
                        self.checkpoint(run_id,owner,fence,'stopped',body)
                        break
                elif phase == 'selection':
                    for split in ('selection','regression'):
                        episodes = self.ledger.episodes(self.evaluator,split)
                        self._reserve_work(run_id,owner,fence,101*len(episodes))
                        body['reports'][split] = self.review.evaluate(self.evaluator,body['model_id'],split)
                    if not all(body['reports'][s]['replay_pass'] for s in ('selection','regression')):
                        body['stop_reason'] = 'selection_or_regression_failed'
                        self.checkpoint(run_id,owner,fence,'stopped',body)
                        break
                elif phase == 'freeze':
                    self.registry.freeze(self.evaluator,body['model_id'])
                elif phase == 'final':
                    episodes = self.ledger.episodes(self.evaluator,'final')
                    self._reserve_work(run_id,owner,fence,101*len(episodes))
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
