"""Task-local adaptation on ARC and GovernedLearning; host capabilities only.

Local database access is a trusted boundary, not remote authentication. Sensitive
bodies belong in host protected storage; this store accepts references only.
"""
from dataclasses import dataclass, asdict
import json
import math
import time
import uuid
from .governed_learning_v20 import _id, _json
from .arc_execution import digest

SCHEMA = 'adaptation-v1'


@dataclass(frozen=True)
class AdaptationConfig:
    enabled: bool = False
    mode: str = 'off'
    backend: str = 'structured'
    max_action_steps: int = 20
    max_replans: int = 3
    max_tool_retries: int = 2
    task_deadline_seconds: int = 120
    max_context_tokens: int = 4000
    provider_spend_limit: int = 0
    cross_subject_memory: bool = False
    automatic_global_promotion: bool = False
    require_verified_corrections: bool = True

    def __post_init__(self):
        if type(self.enabled) is not bool or self.mode not in ('off', 'shadow', 'active-development'):
            raise ValueError('invalid adaptation mode')
        if self.enabled != (self.mode != 'off'):
            raise ValueError('enabled and mode disagree')
        if self.backend != 'structured' or self.cross_subject_memory is not False or self.automatic_global_promotion is not False or self.require_verified_corrections is not True:
            raise ValueError('unsafe or unsupported adaptation configuration')
        for name, ceiling in (('max_action_steps',20),('max_replans',3),('max_tool_retries',2),('task_deadline_seconds',120),('max_context_tokens',4000)):
            value = getattr(self, name)
            if type(value) is not int or not (0 if name in ('max_replans','max_tool_retries') else 1) <= value <= ceiling:
                raise ValueError('invalid bounded configuration: '+name)
        if type(self.provider_spend_limit) is not int or self.provider_spend_limit != 0:
            raise ValueError('live provider accounting not implemented; budget must be zero USD')


class AdaptationCoordinator:
    def __init__(self, runtime, config=None, *, clock=None):
        self.runtime, self.engine = runtime, runtime.engine
        self.config = config or AdaptationConfig()
        self.clock = clock or runtime.clock
        self._configuration = asdict(self.config)
        if getattr(runtime, 'adaptation', None) is not None:
            raise ValueError('adaptation already attached')
        with self.engine._db() as con:
            con.executescript('''
              BEGIN IMMEDIATE;
              CREATE TABLE IF NOT EXISTS adaptation_schema(version TEXT PRIMARY KEY);
              CREATE TABLE IF NOT EXISTS adaptation_tasks(
                id TEXT PRIMARY KEY, tenant TEXT, agent TEXT, subject TEXT, version INTEGER,
                state TEXT, schema_version TEXT);
              CREATE TABLE IF NOT EXISTS adaptation_grants(
                task TEXT, principal TEXT, PRIMARY KEY(task,principal));
              CREATE TABLE IF NOT EXISTS adaptation_events(
                id TEXT PRIMARY KEY, task TEXT, sequence INTEGER, event_key TEXT, record TEXT,
                UNIQUE(task,sequence), UNIQUE(task,event_key));
              CREATE TABLE IF NOT EXISTS adaptation_evidence(
                task TEXT, source TEXT, version TEXT, PRIMARY KEY(task,source,version));
              CREATE TABLE IF NOT EXISTS adaptation_corrections(
                id TEXT PRIMARY KEY, task TEXT, record TEXT);
              CREATE TABLE IF NOT EXISTS adaptation_checkpoints(
                id TEXT PRIMARY KEY, task TEXT, version INTEGER, state TEXT, digest TEXT);
              CREATE TABLE IF NOT EXISTS adaptation_switch(
                tenant TEXT, agent TEXT, killed INTEGER, PRIMARY KEY(tenant,agent));
              CREATE TRIGGER IF NOT EXISTS adaptation_events_immutable
                BEFORE UPDATE ON adaptation_events BEGIN SELECT RAISE(ABORT,'immutable event'); END;
              COMMIT;
            ''')
            versions = [r[0] for r in con.execute('SELECT version FROM adaptation_schema')]
            if versions and versions != [SCHEMA]:
                raise ValueError('unsupported adaptation schema; reviewed forward migration required')
            con.execute('INSERT OR IGNORE INTO adaptation_schema VALUES(?)', (SCHEMA,))
        runtime.adaptation = self

    def _row(self, con, actor, task, *, mutable=False):
        scope = self.engine._scope(actor, 'runtime','operator','auditor')
        # Scope and task capability are checked together on every read. The
        # grant primary key makes this a single indexed lookup, not a cache.
        row = con.execute('SELECT tasks.* FROM adaptation_tasks AS tasks '
                          'JOIN adaptation_grants AS grants ON grants.task=tasks.id '
                          'WHERE tasks.id=? AND tasks.tenant=? AND tasks.agent=? AND grants.principal=?',
                          (task,*scope,actor._nonce)).fetchone()
        if row is None:
            raise PermissionError('task capability absent; cross-subject access denied')
        if row['schema_version'] != SCHEMA:
            raise ValueError('unsupported task checkpoint schema')
        state = json.loads(row['state'])
        if state['config'] != self._configuration:
            raise ValueError('task configuration changed; review migration before resume')
        if mutable and (state['status'] != 'open' or state['expiry'] <= self.clock()):
            raise RuntimeError('task closed, paused or deadline exhausted')
        return row, state

    def _save(self, con, row, state):
        changed = con.execute('UPDATE adaptation_tasks SET version=version+1,state=? WHERE id=? AND version=?',(_json(state),row['id'],row['version'])).rowcount
        if changed != 1:
            raise RuntimeError('concurrent state version conflict')

    def _event(self, con, row, state, kind, key, reference, *, provenance='host-runtime', trust='verified', occurred_at=None):
        _id(key)
        prior = con.execute('SELECT record FROM adaptation_events WHERE task=? AND event_key=?',(row['id'],key)).fetchone()
        if prior:
            previous = json.loads(prior['record'])
            if (previous['event_type'],previous['payload_reference']) != (kind,reference):
                raise ValueError('idempotency collision')
            return previous
        if state['sequence'] >= 4096: raise RuntimeError('episode event budget exhausted')
        now = self.clock()
        event = dict(event_id=uuid.uuid4().hex,schema_version=SCHEMA,tenant_id=row['tenant'],subject_scope_id=row['subject'],task_id=row['id'],episode_id=state['episode'],agent_id=row['agent'],monotonic_sequence=state['sequence']+1,occurred_at=now if occurred_at is None else occurred_at,received_at=now,event_type=kind,parent_event_id=state.get('last_event'),payload_reference=reference,payload_hash=digest(reference),provenance=provenance,trust_level=trust,policy_version=self.engine.contract,model_version='deterministic-v1',trace_id=state['episode'],idempotency_key=key)
        con.execute('INSERT INTO adaptation_events VALUES(?,?,?,?,?)',(event['event_id'],row['id'],event['monotonic_sequence'],key,_json(event)))
        state['sequence'] += 1
        state['last_event'] = event['event_id']
        # Telemetry contains categories only, never task/subject/content labels.
        self.engine._event(con,(row['tenant'],row['agent']),'adaptation_'+kind,{'mode':self.config.mode,'backend':SCHEMA})
        return event

    def begin_task(self, actor, *, task_id, subject_scope, goal_reference, constraints=()):
        scope = self.engine._scope(actor,'runtime')
        for value in (task_id,subject_scope,goal_reference,*constraints): _id(value)
        state = dict(schema_version=SCHEMA,config=asdict(self.config),episode=uuid.uuid4().hex,goal=goal_reference,constraints=list(constraints),verified_facts=[],unverified_observations=[],unresolved_questions=[],completed_steps=[],pending_steps=[],recent_failures=[],active_correction_ids=[],action_receipts={},steps=0,replans=0,sequence=0,status='open',expiry=self.clock()+self.config.task_deadline_seconds,memory_backend_version=SCHEMA,tool_failures={})
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('INSERT INTO adaptation_tasks VALUES(?,?,?,?,0,?,?)',(task_id,*scope,subject_scope,_json(state),SCHEMA))
            con.execute('INSERT INTO adaptation_grants VALUES(?,?)',(task_id,actor._nonce))
            row,_=self._row(con,actor,task_id)
            self._event(con,row,state,'begin','begin',goal_reference)
            self._save(con,row,state)
        return task_id

    def grant(self, operator, task, principal, *, subject_scope, review_reference):
        """Trusted host reauthenticates subject permission before issuing a grant.

        Operator capability alone cannot read task content. This method is the
        explicit task-level authorization boundary, including after restart.
        """
        scope=self.engine._scope(operator,'operator')
        self.engine._scope(principal,'runtime','operator','auditor')
        _id(review_reference)
        if (principal.tenant,principal.agent)!=scope: raise PermissionError('cross-scope grant')
        with self.engine._db() as con:
            row=con.execute('SELECT subject FROM adaptation_tasks WHERE id=? AND tenant=? AND agent=?',(task,*scope)).fetchone()
            if row is None or row['subject']!=subject_scope: raise PermissionError('subject grant mismatch')
            con.execute('INSERT OR IGNORE INTO adaptation_grants VALUES(?,?)',(task,principal._nonce))
            self.engine._event(con,scope,'adaptation_grant',{'review_reference':review_reference})

    def append_event(self, actor, task, *, kind, event_key, reference, expected_version, provenance, occurred_at=None):
        self.engine._scope(actor,'runtime')
        if kind not in ('observation','constraint','contradiction','delayed-outcome'):
            raise ValueError('untrusted caller cannot insert verifier events')
        _id(reference); _id(provenance)
        if occurred_at is not None and (type(occurred_at) not in (float,int) or not math.isfinite(occurred_at) or occurred_at>self.clock()):
            raise ValueError('invalid event timestamp')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row,state=self._row(con,actor,task,mutable=True)
            prior=con.execute('SELECT record FROM adaptation_events WHERE task=? AND event_key=?',(task,event_key)).fetchone()
            if prior:
                previous=json.loads(prior['record'])
                if (previous['event_type'],previous['payload_reference'],previous['provenance'])!=(kind,reference,provenance): raise ValueError('idempotency collision')
                return previous
            if row['version']!=expected_version: raise RuntimeError('concurrent state version conflict')
            event=self._event(con,row,state,kind,event_key,reference,provenance=provenance,trust='observation',occurred_at=occurred_at)
            state['unverified_observations']=(state['unverified_observations']+[event['event_id']])[-20:]
            if kind in ('constraint','contradiction','delayed-outcome'):
                # Unverified constraints cannot silently become policy or success.
                state['unresolved_questions'].append(event['event_id'])
            self._save(con,row,state)
            return event

    def inspect(self, actor, task):
        with self.engine._db() as con:
            row,state=self._row(con,actor,task)
            return dict(state,version=row['version'],task_id=task,subject_scope=row['subject'])

    def events(self, actor, task, *, after_sequence=0, limit=100):
        if type(limit) is not int or not 1<=limit<=100 or type(after_sequence) is not int or after_sequence<0:
            raise ValueError('bounded event page required')
        with self.engine._db() as con:
            self._row(con,actor,task)
            rows=con.execute('SELECT record FROM adaptation_events WHERE task=? AND sequence>? ORDER BY sequence LIMIT ?',(task,after_sequence,limit)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def metrics(self, operator):
        scope=self.engine._scope(operator,'operator','auditor')
        with self.engine._db() as con:
            rows=con.execute("SELECT event,COUNT(*) count FROM gl_events WHERE tenant=? AND agent=? AND event LIKE 'adaptation_%' GROUP BY event",scope).fetchall()
            return {'mode':self.config.mode,'backend_version':SCHEMA,'counts':{row['event']:row['count'] for row in rows},'provider_cost_usd':0}

    def read_context(self, actor, task, token_budget=None):
        budget=self.config.max_context_tokens if token_budget is None else token_budget
        if type(budget) is not int or not 1<=budget<=self.config.max_context_tokens: raise ValueError('invalid context budget')
        with self.engine._db() as con:
            row,state=self._row(con,actor,task,mutable=True)
            return self._context(con,actor,task,state,budget)

    def _context(self, con, actor, task, state, budget):
        mandatory={k:state[k] for k in ('goal','constraints','unresolved_questions','recent_failures','action_receipts')}
        corrections=[]
        killed=con.execute('SELECT killed FROM adaptation_switch WHERE tenant=? AND agent=?',(actor.tenant,actor.agent)).fetchone()
        if self.config.mode=='active-development' and not (killed and killed[0]):
            for cid in state['active_correction_ids']:
                c=json.loads(con.execute('SELECT record FROM adaptation_corrections WHERE id=? AND task=?',(cid,task)).fetchone()[0])
                if c['verification_status']=='verified' and c['expiry']>self.clock() and c['reviewer_identity'] in self.engine.authority._issued:
                    self._bound_evidence(con,actor,task,c['evidence_reference'])
                    corrections.append(c)
        mandatory['corrections']=corrections
        # UTF-8 bytes conservatively upper-bound tokens, including punctuation.
        if len(_json(mandatory).encode())>budget:
            raise RuntimeError('mandatory context exceeds budget; pause for review')
        return dict(mandatory,older_evidence='fetch-scoped-events-on-demand')
    def snapshot(self, actor, task, source, content, *, provenance='host-task-evidence'):
        """Trusted host supplies already authorized content for this task only."""
        _id(source); _id(provenance)
        with self.engine._db() as con:
            self._row(con,actor,task,mutable=True)
        ref=self.runtime.snapshot(actor,task+':'+source,content,provenance=provenance)
        with self.engine._db() as con:
            self._row(con,actor,task,mutable=True)
            con.execute('INSERT OR IGNORE INTO adaptation_evidence VALUES(?,?,?)',(task,ref.source_id,ref.source_version_or_hash))
        return ref

    def _bound_evidence(self, con, actor, task, ref):
        self.runtime._evidence(con,actor,[ref])
        if not con.execute('SELECT 1 FROM adaptation_evidence WHERE task=? AND source=? AND version=?',(task,ref['source_id'],ref['source_version_or_hash'])).fetchone():
            raise PermissionError('evidence not authorized for this task and subject')

    def propose_correction(self, actor, task, *, failed_decision, kind, proposed_change, evidence_reference, expires_in=120, training_allowed=False):
        self.engine._scope(actor,'runtime')
        if kind not in ('formatting','tool-recovery','factual','clinical-content'): raise ValueError('invalid correction kind')
        if type(training_allowed) is not bool or not 0<expires_in<=120: raise ValueError('invalid correction eligibility or expiry')
        # Only typed task-local heading/tool references, never policy instructions.
        if type(proposed_change) is not dict or set(proposed_change)!={'field','value'} or proposed_change['field'] not in ('heading','recovery_tool'):
            raise ValueError('unsupported correction target')
        _id(proposed_change['value'])
        if proposed_change['field']=='recovery_tool' and proposed_change['value'] not in self.runtime.tools:
            raise ValueError('unregistered recovery tool')
        if (kind=='formatting' and proposed_change['field']!='heading') or (kind=='tool-recovery' and proposed_change['field']!='recovery_tool'):
            raise ValueError('correction kind/field mismatch')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row,state=self._row(con,actor,task,mutable=True)
            failed=self.runtime._row(con,actor,failed_decision)
            if failed['task']!=task or failed_decision not in state['action_receipts'] or failed['status']!='failed': raise ValueError('scoped failed attempt required')
            ref=evidence_reference.to_dict() if hasattr(evidence_reference,'to_dict') else evidence_reference
            self._bound_evidence(con,actor,task,ref)
            cid=uuid.uuid4().hex
            correction=dict(correction_id=cid,failed_event_id=state['action_receipts'][failed_decision],failed_decision=failed_decision,proposed_change=proposed_change,correction_kind=kind,evidence_reference=ref,reviewer_identity=None,authority_scope=[row['tenant'],row['subject'],task],verification_status='pending',applicability_conditions={'task':task,'subject':row['subject']},exclusions=['global-policy','other-subjects'],expiry=min(state['expiry'],self.clock()+expires_in),supersedes_id=None,task_reuse_allowed=True,training_allowed=training_allowed)
            con.execute('INSERT INTO adaptation_corrections VALUES(?,?,?)',(cid,task,_json(correction)))
            self._event(con,row,state,'correction_proposed',cid,cid,trust='observation')
            self._save(con,row,state)
            return cid

    def verify_correction(self, operator, task, cid, *, supersedes_id=None, reaffirm=False):
        self.engine._scope(operator,'operator')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row,state=self._row(con,operator,task,mutable=True)
            found=con.execute('SELECT record FROM adaptation_corrections WHERE id=? AND task=?',(cid,task)).fetchone()
            if found is None: raise PermissionError('correction outside task')
            c=json.loads(found[0])
            if c['correction_kind'] not in ('formatting','tool-recovery'):
                raise PermissionError('factual/clinical reviewer authority not implemented')
            if (c['verification_status']!='pending' and not (reaffirm is True and c['verification_status']=='verified')) or c['expiry']<=self.clock(): raise ValueError('correction no longer pending')
            self._bound_evidence(con,operator,task,c['evidence_reference'])
            for oldid in state['active_correction_ids']:
                if oldid == cid: continue
                old=json.loads(con.execute('SELECT record FROM adaptation_corrections WHERE id=?',(oldid,)).fetchone()[0])
                if old['verification_status']=='verified' and old['expiry']>self.clock() and old['proposed_change']['field']==c['proposed_change']['field']:
                    if supersedes_id!=oldid: raise ValueError('conflicting correction requires explicit supersession')
                    old['verification_status']='superseded'
                    con.execute('UPDATE adaptation_corrections SET record=? WHERE id=?',(_json(old),oldid))
            c.update(verification_status='verified',reviewer_identity=operator._nonce,supersedes_id=supersedes_id)
            con.execute('UPDATE adaptation_corrections SET record=? WHERE id=?',(_json(c),cid))
            if cid not in state['active_correction_ids']: state['active_correction_ids'].append(cid)
            self._event(con,row,state,'correction_verified',uuid.uuid4().hex,cid)
            self._save(con,row,state)
            return row['version']+1

    def revoke_correction(self, operator, task, cid):
        self.engine._scope(operator,'operator')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row,state=self._row(con,operator,task)
            found=con.execute('SELECT record FROM adaptation_corrections WHERE id=? AND task=?',(cid,task)).fetchone()
            if found is None: raise PermissionError('correction outside task')
            c=json.loads(found[0]); c['verification_status']='revoked'
            con.execute('UPDATE adaptation_corrections SET record=? WHERE id=?',(_json(c),cid))
            self._event(con,row,state,'correction_revoked','revoke-'+cid,cid)
            self._save(con,row,state)

    def before_plan(self, con, actor, task, *, parent, tool, evidence_refs):
        row,state=self._row(con,actor,task,mutable=True)
        self._context(con,actor,task,state,self.config.max_context_tokens)
        for ref in evidence_refs: self._bound_evidence(con,actor,task,ref)
        if state['tool_failures'].get(tool,0):
            raise RuntimeError('tool circuit open; authoritative recovery review required')
        if state['unresolved_questions']: raise RuntimeError('unresolved contradiction or constraint requires review')
        if state['pending_steps']: raise RuntimeError('pending execution requires reconciliation')
        if state['steps']>=self.config.max_action_steps: raise RuntimeError('action budget exhausted')
        if state.get('last_outcome_status') not in (None,'verified') and parent != state.get('last_decision'):
            raise RuntimeError('failed attempt requires its explicit parent for bounded replanning')
        if parent:
            if parent not in state['action_receipts']: raise ValueError('parent is not a recorded attempt')
            if state['replans']>=self.config.max_replans: raise RuntimeError('replan budget exhausted')
        killed=con.execute('SELECT killed FROM adaptation_switch WHERE tenant=? AND agent=?',(actor.tenant,actor.agent)).fetchone()
        if killed and killed[0]: raise RuntimeError('adaptation killed; task paused for review')

    def stop_exhausted(self, actor, task):
        """Called after a rejected ARC proposal has rolled its transaction back."""
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row,state=self._row(con,actor,task)
            if state['status']!='open': return
            status=None
            if state['expiry']<=self.clock(): status='deadline-exhausted'
            elif state['steps']>=min(5,self.config.max_action_steps) or (state.get('last_outcome_status') not in (None,'verified') and state['replans']>=self.config.max_replans): status='budget-exhausted'
            if status:
                state['status']=status
                self._event(con,row,state,'terminated',uuid.uuid4().hex,status)
                self._save(con,row,state)

    def planned(self, con, actor, task, decision, parent):
        row,state=self._row(con,actor,task,mutable=True)
        state['steps']+=1; state['replans']+=bool(parent); state['pending_steps'].append(decision)
        self._event(con,row,state,'plan','plan-'+decision,decision)
        self._save(con,row,state)

    def before_execute(self, con, actor, task, decision):
        row,state=self._row(con,actor,task,mutable=True)
        if decision not in state['pending_steps']: raise PermissionError('untracked adapted decision')
        killed=con.execute('SELECT killed FROM adaptation_switch WHERE tenant=? AND agent=?',(actor.tenant,actor.agent)).fetchone()
        if killed and killed[0]: raise RuntimeError('adaptation killed; review required')
        if state['unresolved_questions']: raise RuntimeError('unresolved task constraint')
        prior=con.execute('SELECT 1 FROM adaptation_events WHERE task=? AND event_key=?',(task,'dispatch-'+decision)).fetchone()
        if not prior:
            self._event(con,row,state,'dispatch_intent','dispatch-'+decision,decision)
            self._save(con,row,state)

    def record_outcome(self, con, actor, task, decision, outcome):
        row,state=self._row(con,actor,task)
        event=self._event(con,row,state,'outcome','outcome-'+decision,outcome.outcome_id)
        state['action_receipts'][decision]=event['event_id']
        state['last_outcome_status']=outcome.semantic_status
        state['last_decision']=decision
        if decision in state['pending_steps']: state['pending_steps'].remove(decision)
        if outcome.semantic_status=='verified': state['completed_steps'].append(decision)
        else: state['recent_failures'].append(decision)
        if outcome.transport_status=='error':
            decision_row=self.runtime._row(con,actor,decision)
            tool=json.loads(decision_row['record'])['action']['registered_tool']
            state['tool_failures'][tool]=state['tool_failures'].get(tool,0)+1
        if outcome.retry_classification=='reconcile_required': state['status']='review-required'
        if state['expiry']<=self.clock(): state['status']='deadline-exhausted'
        self._save(con,row,state)

    def checkpoint(self, actor, task):
        with self.engine._db() as con:
            row,state=self._row(con,actor,task)
            ident=uuid.uuid4().hex
            envelope={'task':task,'subject':row['subject'],'version':row['version'],'state':state}
            con.execute('INSERT INTO adaptation_checkpoints VALUES(?,?,?,?,?)',(ident,task,row['version'],_json(envelope),digest(envelope)))
            return ident

    def resume(self, actor, task, reference):
        with self.engine._db() as con:
            row,state=self._row(con,actor,task,mutable=True)
            cp=con.execute('SELECT * FROM adaptation_checkpoints WHERE id=? AND task=?',(reference,task)).fetchone()
            if cp is None or digest(json.loads(cp['state']))!=cp['digest']: raise ValueError('corrupt checkpoint')
            envelope=json.loads(cp['state'])
            if envelope['state']['schema_version']!=SCHEMA or envelope['subject']!=row['subject'] or cp['version']!=row['version'] or envelope['state']!=state:
                raise ValueError('stale or incompatible checkpoint; cannot rewind receipts')
            if state['pending_steps']: raise RuntimeError('pending action must be reconciled from authoritative ARC ledger')
            return row['version']

    def reconcile(self, operator, task, *, review_reference):
        self.engine._scope(operator,'operator'); _id(review_reference)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row,state=self._row(con,operator,task)
            for decision in list(state['pending_steps']):
                authoritative=self.runtime._row(con,operator,decision)
                if authoritative['status'] not in ('succeeded','failed','cancelled'):
                    raise RuntimeError('ARC requires authoritative tool reconciliation first')
                event=self._event(con,row,state,'reconciled',uuid.uuid4().hex,review_reference)
                state['action_receipts'][decision]=event['event_id']
                state['pending_steps'].remove(decision)
                # A reviewed receipt does not supply a guessed positive training reward.
                state['recent_failures'].append(decision)
            if state['expiry']<=self.clock(): state['status']='deadline-exhausted'
            elif state['status']=='review-required': state['status']='open'
            self._save(con,row,state)
            return row['version']+1

    def reset(self, operator, task, *, reason):
        self.engine._scope(operator,'operator'); _id(reason)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row,state=self._row(con,operator,task)
            state['active_correction_ids']=[]; state['unverified_observations']=[]
            # Reset never rewinds action budgets, constraints, unresolved risks or receipts.
            self._event(con,row,state,'reset',uuid.uuid4().hex,reason)
            self._save(con,row,state)

    def close_task(self, actor, task, *, status):
        self.engine._scope(actor,'runtime','operator')
        if status not in ('completed','cancelled','review-required'): raise ValueError('invalid final outcome')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row,state=self._row(con,actor,task)
            if status=='completed' and (not state['completed_steps'] or state.get('last_outcome_status')!='verified' or state['pending_steps'] or state['unresolved_questions'] or state['status']!='open' or state['expiry']<=self.clock()): raise ValueError('task completion not independently established')
            state['status']=status; state['active_correction_ids']=[]
            for decision in state['pending_steps']:
                # Same transaction as task cancellation; no worker receives a new permit.
                con.execute("UPDATE arc_decisions SET status=CASE WHEN status IN ('executing','awaiting_verification') THEN 'uncertain' ELSE 'cancelled' END,version=version+1 WHERE id=? AND status NOT IN ('succeeded','failed')",(decision,))
            self._event(con,row,state,'close',uuid.uuid4().hex,status)
            self._save(con,row,state)
            return state['episode']

    def kill_switch(self, operator, *, reason):
        scope=self.engine._scope(operator,'operator'); _id(reason)
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('INSERT OR REPLACE INTO adaptation_switch VALUES(?,?,1)',scope)
            for row in con.execute('SELECT * FROM adaptation_tasks WHERE tenant=? AND agent=?',scope).fetchall():
                state=json.loads(row['state'])
                if state['status']=='open':
                    state['status']='review-required'
                    self._event(con,row,state,'kill',uuid.uuid4().hex,reason)
                    self._save(con,row,state)


def task_hook(runtime, con, actor, task, method, *args, **kwargs):
    """Persisted opt-in fails closed if a restarted host omits its coordinator."""
    coordinator=getattr(runtime,'adaptation',None)
    # An attached coordinator has initialized the schema already. Reopened
    # hosts without it still inspect persisted opt-in state and fail closed.
    if coordinator is None and not con.execute("SELECT 1 FROM sqlite_master WHERE name='adaptation_tasks'").fetchone(): return
    exists=con.execute('SELECT 1 FROM adaptation_tasks WHERE id=? AND tenant=? AND agent=?',(task,actor.tenant,actor.agent)).fetchone()
    if not exists: return
    if coordinator is None: raise PermissionError('persisted adaptation requires coordinator')
    # Disabling a restarted host cannot remove a persisted task's contract.
    # Validate both task capability and the exact stored configuration first.
    if coordinator.config.mode != 'active-development':
        coordinator._row(con,actor,task)
        return
    return getattr(coordinator,method)(con,actor,task,*args,**kwargs)


# Log denial categories after failed transactions have rolled back. No exception
# text, task/subject identifiers or document bodies enter metric labels.
def _observed(method):
    from functools import wraps
    @wraps(method)
    def wrapped(self,actor,*args,**kwargs):
        try:
            return method(self,actor,*args,**kwargs)
        except Exception as error:
            try:
                scope=self.engine._scope(actor,'runtime','operator','auditor')
                category='scope_denied' if isinstance(error,PermissionError) else 'rejected'
                with self.engine._db() as con:
                    self.engine._event(con,scope,'adaptation_'+category,{'operation':method.__name__,'mode':self.config.mode,'backend':SCHEMA})
            except Exception:
                pass
            raise
    return wrapped

for _name in ('append_event','inspect','read_context','events','propose_correction','verify_correction','resume','reset','close_task'):
    setattr(AdaptationCoordinator,_name,_observed(getattr(AdaptationCoordinator,_name)))
