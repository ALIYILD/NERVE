"""Persistent zero-cost read verification reservations; no arbitrary network tools.

The caller has a wall-clock response deadline and bounded read-worker slots.
A timed-out trusted callback may still finish in its daemon worker; its late
result cannot update the ledger, and its request remains uncertain, never retried.
"""
from dataclasses import dataclass,replace
import json
import uuid
from queue import Queue, Empty
from threading import Thread, BoundedSemaphore

_READ_WORKERS = BoundedSemaphore(4)

class ReadTimeout(TimeoutError):
    pass

def bounded_read(handler, request, seconds):
    """Bound host response latency, not a sandbox for arbitrary Python handlers."""
    if not _READ_WORKERS.acquire(blocking=False):
        raise ConnectionError("verification workers busy")
    receipt = Queue(maxsize=1)
    def run():
        try:
            receipt.put((True, handler(request)))
        except BaseException as error:
            receipt.put((False, error))
        finally:
            _READ_WORKERS.release()
    Thread(target=run, daemon=True, name="nerve-verification-read").start()
    try:
        ok, result = receipt.get(timeout=seconds)
    except Empty:
        raise ReadTimeout("read completion unknown; reconciliation required") from None
    if not ok:
        if isinstance(result, Exception):
            raise result
        raise RuntimeError("read worker unavailable")
    return result
from .contracts import VerificationAttempt,OPEN,bounded
from .ledger import digest
from ..governed_learning_v20 import _id

@dataclass(frozen=True)
class ToolSpec:
    handler:object
    validate_request:object
    kinds:tuple
    roles:tuple=('runtime','operator')
    revision:str='offline-v1'
    cost:float=0
    def __post_init__(self):
        if not callable(self.handler) or not callable(self.validate_request) or self.cost!=0:raise ValueError('host bounded read handler and known zero pricing required')
        _id(self.revision)

CHECKS={'source_disagreement':'read_primary_record','prior_vs_evidence':'read_primary_record','missing_required_evidence':'request_observation','stale_evidence':'inspect_revision','ambiguous_identity':'request_identity','measurement_uncertainty':'normalize_units','tool_status_unknown':'inspect_status'}
class Verifier:
    def __init__(self,ledger,*,tools,call_seconds=30,task_seconds=180,max_conflict=3,max_task=12):
        if not 0<call_seconds<=30 or not 0<task_seconds<=180 or not 1<=max_conflict<=3 or not 1<=max_task<=12:raise ValueError('budgets may only be stricter than offline defaults')
        self.ledger,self.tools=ledger,dict(tools)
        self.call_seconds,self.task_seconds,self.max_conflict,self.max_task=call_seconds,task_seconds,max_conflict,max_task
    def plan(self,actor,conflict_id):
        c=self.ledger.get_conflict(actor,conflict_id)
        return {'conflict_id':conflict_id,'check':CHECKS[c.kind],'reason':'Obtain independent evidence that discriminates the registered claims','allowed_tools':[name for name,spec in self.tools.items() if c.kind in spec.kinds]}
    def check(self,actor,conflict_id,tool_id,request,*,retry_reason=None):
        ledger=self.ledger
        if tool_id not in self.tools:raise PermissionError('unregistered verification tool')
        spec=self.tools[tool_id];ledger.scope(actor,roles=spec.roles);bounded(request)
        if spec.validate_request(request) is not True:raise PermissionError('verification request violates host argument/destination policy')
        if retry_reason not in {None,'transient_transport_failure','changed_version','expired_cache'}:raise ValueError('bounded explicit retry reason required')
        request_hash=digest({'tool':tool_id,'revision':spec.revision,'request':request})
        with ledger.engine._db() as con:
            con.execute('BEGIN IMMEDIATE');c=ledger.get_conflict(actor,conflict_id,con=con);scope=ledger.scope(actor,c.scope['task_id'])
            if c.status not in OPEN:return {'boundary':'resolved','attempt':None}
            if c.kind not in spec.kinds:raise PermissionError('tool cannot verify this conflict kind')
            rows=con.execute('SELECT * FROM uc_attempts WHERE tenant=? AND agent=? AND task=? AND conflict=?',(*scope,conflict_id)).fetchall()
            duplicates=[VerificationAttempt.from_json(r['record']) for r in rows if r['request_hash']==request_hash]
            if duplicates:
                previous=duplicates[-1]
                if previous.status in {'reserved','uncertain'}:return {'boundary':'verifier_unavailable','attempt':previous.to_dict(),'reason':'unknown completion requires reconciliation'}
                if retry_reason is None:return {'boundary':'unresolved_disagreement','attempt':previous.to_dict(),'deduplicated':True}
                if retry_reason=='transient_transport_failure' and previous.outcome!='failed':raise ValueError('retry requires observed transient failure')
                if retry_reason in {'changed_version','expired_cache'}:raise ValueError('refresh request version/cache identity instead of repeating identical evidence')
            now=ledger.clock();budget=con.execute('SELECT * FROM uc_budgets WHERE tenant=? AND agent=? AND task=?',scope).fetchone()
            if budget is None:
                con.execute('INSERT INTO uc_budgets VALUES(?,?,?,?,0,0)',(*scope,now));budget={'started':now,'reserved_seconds':0,'checks':0}
            if len(rows)>=self.max_conflict or budget['checks']>=self.max_task or now-budget['started']>=self.task_seconds or budget['reserved_seconds']+self.call_seconds>self.task_seconds:
                return {'boundary':'unresolved_budget','attempt':None}
            attempt=VerificationAttempt(uuid.uuid4().hex,conflict_id,tool_id,request_hash,started_at=now,retry_reason=retry_reason,provider_revision=spec.revision)
            con.execute('INSERT INTO uc_attempts VALUES(?,?,?,?,?,?,?)',(attempt.attempt_id,*scope,conflict_id,request_hash,attempt.to_json()))
            con.execute('UPDATE uc_budgets SET checks=checks+1,reserved_seconds=reserved_seconds+? WHERE tenant=? AND agent=? AND task=?',(self.call_seconds,*scope))
            ledger._event(con,scope,'verification_reserved',{'attempt_id':attempt.attempt_id,'conflict_id':conflict_id})
        try:
            result=bounded_read(spec.handler,json.loads(json.dumps(request)),min(self.call_seconds,max(.001,self.task_seconds-(ledger.clock()-budget['started']))))
            if ledger.clock()-now>self.call_seconds:raise TimeoutError('readback deadline exceeded')
            if type(result) is not dict or result.get('outcome') not in {'supports','refutes','inconclusive'}:raise ValueError('invalid verification result')
            refs=result.get('evidence_refs',[])
            sources=[ledger.source(actor,r['source_ref'],r['source_revision']) for r in refs]
            outcome=result['outcome'] if refs else 'inconclusive'
            attempt=replace(attempt,status='completed',finished_at=ledger.clock(),evidence_refs=refs,source_lineage=sorted(set(s['lineage'] for s in sources)),outcome=outcome)
            boundary='unresolved_disagreement' if refs else 'unresolved_no_source'
        except ReadTimeout:
            attempt=replace(attempt,status='uncertain',finished_at=ledger.clock(),outcome='failed');boundary='verifier_unavailable'
        except Exception:
            attempt=replace(attempt,status='failed',finished_at=ledger.clock(),outcome='failed');boundary='verifier_unavailable'
        with ledger.engine._db() as con:
            con.execute('BEGIN IMMEDIATE');con.execute('UPDATE uc_attempts SET record=? WHERE id=?',(attempt.to_json(),attempt.attempt_id))
            c=ledger.get_conflict(actor,conflict_id,con=con)
            c=replace(c,checks=c.checks+[attempt.attempt_id],revision=c.revision+1,updated_at=ledger.clock())
            key=con.execute('SELECT family FROM uc_conflicts WHERE id=?',(conflict_id,)).fetchone()['family']
            ledger._write_conflict(con,scope,c,key,'verification_recorded')
        return {'boundary':boundary,'attempt':attempt.to_dict()}
    def resume(self,actor,attempt_id):
        with self.ledger.engine._db() as con:
            row=con.execute('SELECT record FROM uc_attempts WHERE id=? AND tenant=? AND agent=?',(attempt_id,*self.ledger.scope(actor))).fetchone()
            if row is None:raise PermissionError('attempt unavailable in scope')
            attempt=VerificationAttempt.from_json(row['record'])
            return {'boundary':'verifier_unavailable' if attempt.status in {'reserved','uncertain'} else 'unresolved_disagreement','attempt':attempt.to_dict(),'dispatch_repeated':False}
