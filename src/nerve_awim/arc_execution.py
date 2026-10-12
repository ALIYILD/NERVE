"""Opt-in ARC checks on GovernedLearning's actual dispatcher and existing SQLite store.

Trusted host registers argument validators and deterministic verifiers. This is
not remote identity, a security sandbox, or an autonomous clinical policy.
"""
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import time
import uuid
from .arc_contracts import EvidenceRef, DecisionRecord, OutcomeRecord, SCHEMA
from .agent_learning_v12 import AgentTask
from .governed_learning_v20 import _json, _id


def digest(value): return sha256(_json(value).encode()).hexdigest()

def task_hook(runtime, con, actor, task, method, *args, **kwargs):
    # Optional adaptation must not break base ARC when its module is absent.
    # If explicitly attached, import/hook failures still propagate fail-closed.
    if getattr(runtime, 'adaptation', None) is None:
        # A missing optional module is valid only for tasks that never opted in.
        # Restarting without the coordinator must not remove a persisted guard.
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='adaptation_tasks' AND type='table'").fetchone():
            if con.execute('SELECT 1 FROM adaptation_tasks WHERE id=? AND tenant=? AND agent=?',
                           (task, actor.tenant, actor.agent)).fetchone():
                raise PermissionError('persisted adaptation requires coordinator')
        return
    from .adaptation import task_hook as adaptation_hook
    return adaptation_hook(runtime, con, actor, task, method, *args, **kwargs)

@dataclass(frozen=True)
class ToolSpec:
    context: str
    validate_arguments: object
    verify: object
    risk: str = 'read'
    required_sources: tuple = ()
    evidence_bindings: object = None

class ArcRuntime:
    def __init__(self, engine, *, tools, clock=time.time, mode='off', sleeper=time.sleep):
        if mode not in {'off','shadow','enforce'}: raise ValueError('unknown ARC mode')
        self.engine, self.tools, self.clock, self.mode = engine, dict(tools), clock, mode
        for name, spec in self.tools.items():
            if (spec.context,name) not in engine._registry: raise ValueError('unknown registered tool')
            if spec.risk not in {'read','write'} or not callable(spec.validate_arguments) or not callable(spec.verify): raise ValueError('invalid tool contract')
        if not callable(sleeper): raise ValueError('bounded retry sleeper required')
        self.sleeper = sleeper
        self._permits = {}
        with engine._db() as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS arc_modes(tenant TEXT, agent TEXT, context TEXT, mode TEXT, PRIMARY KEY(tenant,agent,context));
            CREATE TABLE IF NOT EXISTS arc_evidence(tenant TEXT, agent TEXT, source TEXT, version TEXT, ref TEXT, PRIMARY KEY(tenant,agent,source,version));
            CREATE TABLE IF NOT EXISTS arc_current(tenant TEXT, agent TEXT, source TEXT, version TEXT, PRIMARY KEY(tenant,agent,source));
            CREATE TABLE IF NOT EXISTS arc_decisions(id TEXT PRIMARY KEY, tenant TEXT, agent TEXT, task TEXT, domain TEXT, record TEXT, arguments TEXT, status TEXT, version INTEGER, approval TEXT, outcome TEXT, UNIQUE(tenant,agent,task,id));
            CREATE TABLE IF NOT EXISTS arc_memory(decision TEXT PRIMARY KEY, tenant TEXT, agent TEXT, domain TEXT, label TEXT, expires REAL, retracted INTEGER DEFAULT 0, provenance TEXT);
            CREATE TRIGGER IF NOT EXISTS arc_evidence_immutable BEFORE UPDATE ON arc_evidence BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
            ''')
        if getattr(engine, '_arc_guard', None) is not None: raise ValueError('ARC runtime already attached')
        engine._arc_guard = self._dispatch_guard
        engine._arc_contexts = frozenset(s.context for s in tools.values())

    def set_mode(self, actor, context, mode):
        scope=self._scope(actor,'operator')
        if mode not in {'off','shadow','enforce'} or context not in self.engine._arc_contexts: raise ValueError('registered context and valid mode required')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('INSERT OR REPLACE INTO arc_modes VALUES(?,?,?,?)',(*scope,context,mode))
            if mode != 'enforce':
                rows=con.execute("SELECT id,record FROM arc_decisions WHERE tenant=? AND agent=? AND status IN ('executing','awaiting_verification')",scope).fetchall()
                for row in rows:
                    tool=json.loads(row['record'])['action']['registered_tool']
                    if self.tools[tool].context==context: con.execute("UPDATE arc_decisions SET status='uncertain',version=version+1 WHERE id=?",(row['id'],))
            self.engine._event(con,scope,'arc_mode_changed',{'context':context,'mode':mode})
        return mode

    def _mode(self,con,actor,context):
        row=con.execute('SELECT mode FROM arc_modes WHERE tenant=? AND agent=? AND context=?',(actor.tenant,actor.agent,context)).fetchone()
        return row['mode'] if row else self.mode

    def _scope(self, actor, *roles): return self.engine._scope(actor, *(roles or ('runtime','operator','auditor')))
    def _row(self, con, actor, decision_id):
        scope = self._scope(actor)
        row = con.execute('SELECT * FROM arc_decisions WHERE id=? AND tenant=? AND agent=?',(decision_id,*scope)).fetchone()
        if row is None: raise PermissionError('decision not available in actor scope')
        return row

    def snapshot(self, actor, source_id, content, *, source_type='local', valid_for=3600, provenance='host-observation'):
        scope = self._scope(actor)
        if not isinstance(source_id,str) or not source_id or valid_for <= 0: raise ValueError('source ID and positive freshness required')
        now = self.clock()
        # Payload is intentionally not persisted: the protected host owns it.
        content_hash = digest(content)
        version = digest({'content_hash':content_hash,'captured_at':now})
        with self.engine._db() as con:
            old = con.execute('SELECT ref FROM arc_evidence WHERE tenant=? AND agent=? AND source=? AND version=?',(*scope,source_id,version)).fetchone()
            ref = EvidenceRef.from_json(old['ref']) if old else EvidenceRef(source_id,version,now,now+valid_for,scope[0],source_type,provenance,scope[1],'sha256:'+content_hash)
            con.execute('INSERT OR IGNORE INTO arc_evidence VALUES(?,?,?,?,?)',(*scope,source_id,version,ref.to_json()))
            con.execute('INSERT OR REPLACE INTO arc_current VALUES(?,?,?,?)',(*scope,source_id,version))
        return ref

    def _evidence(self, con, actor, refs):
        scope = self._scope(actor)
        ids=[]
        for raw in refs:
            ref = raw if isinstance(raw,EvidenceRef) else EvidenceRef(**raw)
            if (ref.tenant_scope,ref.access_scope) != scope: raise PermissionError('cross-scope evidence denied')
            row=con.execute('SELECT ref FROM arc_evidence WHERE tenant=? AND agent=? AND source=? AND version=?',(*scope,ref.source_id,ref.source_version_or_hash)).fetchone()
            current=con.execute('SELECT version FROM arc_current WHERE tenant=? AND agent=? AND source=?',(*scope,ref.source_id)).fetchone()
            if row is None or json.loads(row['ref']) != ref.to_dict(): raise ValueError('unknown or tampered evidence reference')
            if current is None or current['version'] != ref.source_version_or_hash: raise ValueError('source changed; refresh decision and approval')
            if ref.valid_until_if_known is not None and self.clock() >= ref.valid_until_if_known: raise ValueError('stale evidence; refresh observation')
            ids.append(ref.source_id)
        return ids

    def propose(self, actor, task_id, tool, arguments, evidence_refs, goal, completion_criteria, *, parent_decision_id=None, approval_required=False, domain='nonclinical', unknowns=None, expires_in=300, concise_rationale='Host-authored evidence-linked decision summary', model_version='deterministic-v1', prompt_version='arc-v1'):
        scope=self._scope(actor,'runtime')
        if tool not in self.tools: raise ValueError('unknown registered tool')
        spec=self.tools[tool]
        arguments=json.loads(_json(arguments))
        if spec.validate_arguments(arguments) is False: raise ValueError('invalid tool arguments')
        if not isinstance(completion_criteria,list) or not completion_criteria or any(not isinstance(x,str) or not x for x in completion_criteria): raise ValueError('named completion criteria required')
        if not 0 < expires_in <= 3600: raise ValueError('bounded decision expiry required')
        refs=[r.to_dict() if isinstance(r,EvidenceRef) else r for r in evidence_refs]
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('INSERT OR IGNORE INTO arc_modes VALUES(?,?,?,?)',(*scope,spec.context,self.mode))
            ids=self._evidence(con,actor,refs)
            if spec.evidence_bindings and spec.evidence_bindings(arguments,refs) is not True: raise ValueError('arguments do not match immutable evidence')
            if not set(spec.required_sources).issubset(ids): raise ValueError('missing required evidence sources')
            rows=con.execute('SELECT * FROM arc_decisions WHERE tenant=? AND agent=? AND task=?',(*scope,task_id)).fetchall()
            if len(rows)>=5: raise RuntimeError('decision budget exhausted: maximum 5 per task')
            fingerprint=digest({'tool':tool,'arguments':arguments,'evidence':refs})
            for previous in rows:
                if json.loads(previous['record'])['observation_version']==fingerprint:
                    if parent_decision_id: raise RuntimeError('repeated no-progress decision; refresh evidence or change action')
                    return replace(DecisionRecord.from_json(previous['record']),status=previous['status'])
            if any(r['status'] in {'executing','uncertain','awaiting_verification'} for r in rows): raise RuntimeError('unresolved execution requires reconciliation')
            if parent_decision_id:
                parent=self._row(con,actor,parent_decision_id)
                if parent['task'] != task_id: raise ValueError('parent belongs to a different task')
                if parent['status'] in {'executing','uncertain'}: raise RuntimeError('uncertain execution requires reconciliation before replanning')
            task_hook(self,con,actor,task_id,'before_plan',parent=parent_decision_id)
            now=self.clock(); did=uuid.uuid4().hex
            required=bool(approval_required or spec.risk=='write')
            record=DecisionRecord(did,task_id,did,scope[0],actor._nonce,scope[1],task_id,now,now+expires_in,fingerprint,goal,[],list(unknowns or []),refs,concise_rationale,'Completion is checked after execution',goal,{'registered_tool':tool,'validated_arguments_ref':digest(arguments),'idempotency_key':did},['cross-scope access','unapproved external submission'],completion_criteria,'registered-deterministic-verifier',{'reason':'No calibrated confidence available','confidence_if_calibrated':None},required,None,self.engine.contract,model_version,prompt_version,'awaiting_approval' if required else 'ready',parent_decision_id)
            con.execute('INSERT INTO arc_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,*scope,task_id,domain,record.to_json(),_json(arguments),record.status,0,None,None))
            task_hook(self,con,actor,task_id,'planned',did,parent_decision_id)
            self.engine._event(con,scope,'arc_proposed',{'decision':did,'correlation':task_id})
        return record

    def generate(self, actor, *, provider, task_id, evidence_refs, domain='nonclinical'):
        if getattr(self, 'adaptation', None) is not None:
            raise PermissionError('adaptation provider budget is zero USD')
        """Existing configured provider adapter supplied by host; max one repair.

        Provider must own timeout and usage accounting. Only redacted references
        go to it; retrieved text cannot select tools beyond the host registry.
        """
        with self.engine._db() as con: self._evidence(con,actor,[r.to_dict() if isinstance(r,EvidenceRef) else r for r in evidence_refs])
        request={'schema_version':SCHEMA,'tools':sorted(self.tools),'evidence_refs':[r.to_dict() if isinstance(r,EvidenceRef) else r for r in evidence_refs], 'repair':False}
        last=None
        for attempt in range(2):
            try:
                raw=provider(request)
                data=json.loads(raw) if isinstance(raw,str) else raw
                if type(data) is not dict or set(data)-{'tool','arguments','goal','completion_criteria','evidence_ids','unknowns','rationale'}: raise ValueError('invalid generated decision fields')
                known={r['source_id']:r for r in request['evidence_refs']}
                selected=[known[k] for k in data['evidence_ids']]
                return self.propose(actor,task_id,data['tool'],data['arguments'],selected,data['goal'],data['completion_criteria'],domain=domain,unknowns=data.get('unknowns'),concise_rationale=data.get('rationale','Provider decision summary'),model_version='configured-provider')
            except (ValueError,KeyError,TypeError) as exc:
                last=exc; request={**request,'repair':True,'error':'Invalid schema or unavailable evidence/tool'}
            except Exception:
                raise RuntimeError('provider unavailable; no decision dispatched') from None
        raise ValueError('decision invalid after one repair; no dispatch') from last

    def approve(self, actor, decision_id, *, valid_for=300):
        self._scope(actor,'operator')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row=self._row(con,actor,decision_id); record=DecisionRecord.from_json(row['record'])
            if actor._nonce==record.actor_id: raise PermissionError('proposer cannot approve itself')
            if row['status'] != 'awaiting_approval': raise ValueError('decision is not awaiting approval')
            self._validate(con,actor,row,require_approval=False)
            approval={'id':uuid.uuid4().hex,'decision_hash':digest(json.loads(row['record'])),'arguments_hash':digest(json.loads(row['arguments'])),'approver':actor._nonce,'expires':min(record.expires_at,self.clock()+valid_for)}
            con.execute("UPDATE arc_decisions SET approval=?,status='ready',version=version+1 WHERE id=?",(_json(approval),decision_id))
        return approval['id']

    def _validate(self,con,actor,row,require_approval=True):
        record=DecisionRecord.from_json(row['record'])
        if self.clock()>=record.expires_at: raise ValueError('decision expired')
        self._evidence(con,actor,record.evidence_refs)
        arguments=json.loads(row['arguments']); tool=record.action['registered_tool']
        if tool not in self.tools or digest(arguments)!=record.action['validated_arguments_ref']: raise ValueError('unknown tool or tampered arguments')
        if self.tools[tool].validate_arguments(arguments) is False: raise ValueError('invalid tool arguments')
        binding=self.tools[tool].evidence_bindings
        if binding and binding(arguments,record.evidence_refs) is not True: raise ValueError('arguments do not match immutable evidence')
        if require_approval and record.approval_requirement:
            approval=json.loads(row['approval']) if row['approval'] else {}
            if (approval.get('decision_hash')!=digest(json.loads(row['record'])) or approval.get('arguments_hash')!=digest(arguments) or approval.get('expires',0)<=self.clock() or approval.get('approver')==record.actor_id): raise PermissionError('missing, expired or incorrectly bound approval')
            if approval['approver'] not in self.engine.authority._issued: raise PermissionError('approval revoked')
        return record,arguments

    def _dispatch_guard(self, con, actor, task, permit):
        mode=self._mode(con,actor,task.context)
        if mode=='off':
            if permit is not None: raise PermissionError('ARC disabled after dispatch intent')
            return
        if mode=='shadow': raise PermissionError('shadow context cannot dispatch effects')
        entry=self._permits.pop(permit,None)
        if entry is None or entry != (actor._nonce,task.task_id,digest(task.payload)): raise PermissionError('ARC decision required at dispatcher boundary')
        row=self._row(con,actor,task.task_id)
        if row['status']!='executing': raise PermissionError('dispatch cancelled or already consumed')
        record,args=self._validate(con,actor,row)
        task_hook(self,con,actor,row['task'],'before_execute',row['id'])
        state=self.engine._state(con,(actor.tenant,actor.agent)); routes=self.engine._release(con,(actor.tenant,actor.agent),state['active'])
        if routes[task.context]!=record.action['registered_tool']: raise PermissionError('approved route changed; obtain new decision')
        from .arc_operations import release_dispatch_guard
        release_dispatch_guard(con,actor,task)

    def execute(self, actor, decision_id):
        scope=self._scope(actor,'runtime'); start=self.clock()
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row=self._row(con,actor,decision_id)
            if row['outcome']: return OutcomeRecord.from_json(row['outcome'])
            if row['status'] in {'executing','awaiting_verification','uncertain'}: raise RuntimeError('execution uncertain or in progress; reconcile, never replay')
            if row['status']!='ready': raise PermissionError('decision not ready: '+row['status'])
            record,args=self._validate(con,actor,row)
            mode=self._mode(con,actor,self.tools[record.action['registered_tool']].context)
            if mode=='shadow': return {'status':'shadow','decision_id':decision_id,'effects':False}
            if mode!='enforce': raise PermissionError('ARC execution is disabled')
            task_hook(self,con,actor,row['task'],'before_execute',decision_id)
            con.execute("UPDATE arc_decisions SET status='executing',version=version+1 WHERE id=? AND version=?",(decision_id,row['version']))
            self.engine._event(con,scope,'arc_dispatch_intent',{'decision':decision_id,'correlation':record.correlation_id})
        spec=self.tools[record.action['registered_tool']]; permit=object(); task=AgentTask(decision_id,spec.context,args)
        self._permits[permit]=(actor._nonce,decision_id,digest(args))
        transport='success'; result=None
        try:
            result=self.engine.execute(actor,task,arc_permit=permit)['value']
        except Exception:
            transport='error'
        finally: self._permits.pop(permit,None)
        criteria={}; semantic='unverifiable'; lifecycle='uncertain' if spec.risk=='write' else 'failed'
        if transport=='success':
            with self.engine._db() as con: con.execute("UPDATE arc_decisions SET status='awaiting_verification',version=version+1 WHERE id=? AND status='executing'",(decision_id,))
            # Only transient readback is retried; the effect itself is never replayed.
            for attempt in range(3):
                # Deadline checks bound admission, not a running host callback.
                if self.clock() >= record.expires_at: break
                with self.engine._db() as con:
                    current=self._row(con,actor,decision_id)
                    if current['status'] != 'awaiting_verification': break
                try:
                    checked=spec.verify(result,args)
                    if self.clock() >= record.expires_at: break
                    criteria={name: checked.get(name) is True for name in record.completion_criteria}
                    semantic='verified' if all(criteria.values()) else ('partial' if any(criteria.values()) else 'failed')
                    lifecycle='succeeded' if semantic=='verified' else 'failed'
                    break
                except (TimeoutError,ConnectionError):
                    if attempt==2: break
                    remaining=record.expires_at-self.clock()
                    if remaining <= 0: break
                    self.sleeper(min(.01 * (2 ** attempt), remaining))
                except Exception: break
        outcome=OutcomeRecord(uuid.uuid4().hex,decision_id,decision_id,self.clock(),transport,semantic,criteria,'Registered verifier observed '+semantic,record.evidence_refs if semantic=='verified' else [],'' if semantic=='verified' else 'Intended completion not independently established','reconcile_required' if lifecycle=='uncertain' else 'no_automatic_retry','unreviewed',max(0,self.clock()-start))
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            current=self._row(con,actor,decision_id)
            if current['status'] in {'uncertain','cancelled'}:
                lifecycle='uncertain'
                outcome=replace(outcome,semantic_status='unverifiable',discrepancy='Cancellation or rollback during execution requires reconciliation',retry_classification='reconcile_required')
            con.execute('UPDATE arc_decisions SET outcome=?,status=?,version=version+1 WHERE id=?',(outcome.to_json(),lifecycle,decision_id))
            task_hook(self,con,actor,current['task'],'record_outcome',decision_id,outcome)
            self.engine._event(con,scope,'arc_outcome',{'decision':decision_id,'semantic_status':outcome.semantic_status,'transport_status':outcome.transport_status,'correlation':record.correlation_id})
        return outcome

    def inspect(self, actor, decision_id):
        with self.engine._db() as con:
            row=self._row(con,actor,decision_id)
            return {'decision':{**json.loads(row['record']),'status':row['status'],'approval_ref':json.loads(row['approval'])['id'] if row['approval'] else None},'version':row['version'],'outcome':json.loads(row['outcome']) if row['outcome'] else None}

    def cancel(self, actor, decision_id):
        self._scope(actor,'operator','runtime')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row=self._row(con,actor,decision_id)
            if row['status'] in {'succeeded','failed','cancelled','expired'}: raise ValueError('terminal decision cannot be cancelled')
            status='uncertain' if row['status'] in {'executing','awaiting_verification'} else 'cancelled'
            con.execute('UPDATE arc_decisions SET status=?,approval=NULL,version=version+1 WHERE id=?',(status,decision_id))
        return status

    def reconcile(self, actor, decision_id, *, observed_status, review_ref):
        self._scope(actor,'operator')
        _id(review_ref)
        if observed_status not in {'succeeded','failed','cancelled'} or not review_ref: raise ValueError('explicit reviewed external status required')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row=self._row(con,actor,decision_id)
            if row['status'] not in {'executing','awaiting_verification','uncertain'}: raise ValueError('execution does not require reconciliation')
            con.execute('UPDATE arc_decisions SET status=?,version=version+1 WHERE id=?',(observed_status,decision_id))
            self.engine._event(con,(actor.tenant,actor.agent),'arc_reconciled',{'decision':decision_id,'status':observed_status,'review':review_ref})
        return observed_status

    def review(self, actor, decision_id, *, label, expires_in=86400, provenance='human-review'):
        scope=self._scope(actor,'operator')
        _id(provenance)
        if label not in {'accepted','rejected'} or not 0<expires_in<=2592000: raise ValueError('review label and bounded expiry required')
        with self.engine._db() as con:
            row=self._row(con,actor,decision_id); record=json.loads(row['record'])
            if record['actor_id']==actor._nonce: raise PermissionError('independent review required')
            if not row['outcome']: raise ValueError('observed outcome required')
            if label=='accepted' and json.loads(row['outcome'])['semantic_status']!='verified': raise ValueError('unverified outcomes cannot become trusted guidance')
            con.execute('INSERT OR REPLACE INTO arc_memory VALUES(?,?,?,?,?,?,0,?)',(decision_id,*scope,row['domain'],label,self.clock()+expires_in,provenance))
        return label

    def memories(self, actor, *, domain):
        scope=self._scope(actor)
        with self.engine._db() as con:
            rows=con.execute("SELECT decision,provenance FROM arc_memory WHERE tenant=? AND agent=? AND domain=? AND label='accepted' AND expires>? AND retracted=0",(*scope,domain,self.clock())).fetchall()
            return [dict(r) for r in rows]

    def retract(self, actor, decision_id):
        self._scope(actor,'operator')
        with self.engine._db() as con:
            self._row(con,actor,decision_id)
            con.execute('UPDATE arc_memory SET retracted=1 WHERE decision=?',(decision_id,))

    def delete_memory(self, actor, decision_id):
        """Purge reusable guidance; minimal execution audit retained separately."""
        self._scope(actor,'operator')
        with self.engine._db() as con:
            self._row(con,actor,decision_id)
            con.execute('DELETE FROM arc_memory WHERE decision=?',(decision_id,))

# Rejections are visible without persisting arguments, document prose or secrets.
def _observed(method):
    from functools import wraps
    @wraps(method)
    def wrapped(self,actor,*args,**kwargs):
        try: return method(self,actor,*args,**kwargs)
        except Exception as exc:
            try:
                scope=self._scope(actor)
                text=str(exc).lower()
                category=('stale_evidence' if 'stale' in text or 'source changed' in text else
                          'budget_exhaustion' if 'budget' in text else
                          'approval_wait' if 'approval' in text or 'not ready' in text else
                          'uncertain_effect' if 'uncertain' in text or 'reconcile' in text else 'validation_rejection')
                with self.engine._db() as con:self.engine._event(con,scope,'arc_'+category,{'operation':method.__name__,'error_type':type(exc).__name__})
            except Exception: pass
            raise
    return wrapped
for _method in ('propose','execute','generate','approve'):
    setattr(ArcRuntime,_method,_observed(getattr(ArcRuntime,_method)))
