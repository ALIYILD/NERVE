"""Additive uncertainty tables in the existing governed database, never a second store."""
from contextlib import nullcontext
from dataclasses import replace
from hashlib import sha256
import json
import time
import uuid
from ..governed_learning_v20 import _id, _json, ROLES
from .contracts import Claim, Conflict, OPEN, bounded
from .reconciliation import contradicts, family

def digest(value):return sha256(_json(value).encode()).hexdigest()
class StaleRevision(ValueError):pass

class Ledger:
    def __init__(self,engine,*,clock=time.time):
        self.engine,self.clock=engine,clock
        with engine._db() as con:
            if con.execute("SELECT 1 FROM sqlite_master WHERE name='uc_schema'").fetchone():
                versions={r[0] for r in con.execute('SELECT version FROM uc_schema')}
                if versions!={1}:raise ValueError('unsupported uncertainty database schema')
            con.executescript('''
            CREATE TABLE IF NOT EXISTS uc_schema(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO uc_schema VALUES(1);
            CREATE TABLE IF NOT EXISTS uc_state(tenant TEXT,agent TEXT,task TEXT,revision INTEGER,PRIMARY KEY(tenant,agent,task));
            CREATE TABLE IF NOT EXISTS uc_sources(tenant TEXT,agent TEXT,id TEXT,revision TEXT,lineage TEXT,hash TEXT,provenance TEXT,active INTEGER,PRIMARY KEY(tenant,agent,id,revision));
            CREATE TABLE IF NOT EXISTS uc_claims(id TEXT PRIMARY KEY,tenant TEXT,agent TEXT,task TEXT,record TEXT);
            CREATE TABLE IF NOT EXISTS uc_conflicts(id TEXT PRIMARY KEY,tenant TEXT,agent TEXT,task TEXT,family TEXT,record TEXT);
            CREATE TABLE IF NOT EXISTS uc_links(tenant TEXT,agent TEXT,task TEXT,decision TEXT,claims TEXT,rules TEXT,PRIMARY KEY(tenant,agent,task,decision));
            CREATE TABLE IF NOT EXISTS uc_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT,agent TEXT,task TEXT,event TEXT,details TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS uc_resolutions(id TEXT PRIMARY KEY,tenant TEXT,agent TEXT,task TEXT,record TEXT);
            CREATE TABLE IF NOT EXISTS uc_attempts(id TEXT PRIMARY KEY,tenant TEXT,agent TEXT,task TEXT,conflict TEXT,request_hash TEXT,record TEXT);
            CREATE TABLE IF NOT EXISTS uc_budgets(tenant TEXT,agent TEXT,task TEXT,started REAL,reserved_seconds REAL,checks INTEGER,PRIMARY KEY(tenant,agent,task));
            ''')
    def scope(self,actor,task_id=None,roles=ROLES):
        scope=self.engine._scope(actor,*roles)
        return (*scope,_id(task_id)) if task_id is not None else scope
    def _event(self,con,scope,event,details):
        con.execute('INSERT INTO uc_events(tenant,agent,task,event,details,created) VALUES(?,?,?,?,?,?)',(*scope,event,_json(details),self.clock()))
        con.execute('INSERT INTO uc_state VALUES(?,?,?,1) ON CONFLICT(tenant,agent,task) DO UPDATE SET revision=revision+1',scope)
    def revision(self,actor,task_id,*,con=None):
        scope=self.scope(actor,task_id)
        with (nullcontext(con) if con is not None else self.engine._db()) as db:
            row=db.execute('SELECT revision FROM uc_state WHERE tenant=? AND agent=? AND task=?',scope).fetchone()
            return row['revision'] if row else 0
    def register_source(self,actor,source_id,content,*,revision='v1',lineage=None,provenance='structured'):
        scope=self.scope(actor,roles=('runtime','operator'));_id(source_id);_id(revision);_id(provenance)
        bounded(content);h=digest(content);lineage=_id(lineage or ('content-'+h))
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE')
            copy=con.execute('SELECT lineage FROM uc_sources WHERE tenant=? AND agent=? AND hash=?',(*scope,h)).fetchone()
            if copy:lineage=copy['lineage']
            old=con.execute('SELECT * FROM uc_sources WHERE tenant=? AND agent=? AND id=? AND revision=?',(*scope,source_id,revision)).fetchone()
            if old and (old['hash'],old['lineage'],old['provenance'])!=(h,lineage,provenance):raise ValueError('source revision immutable; register changed content under new revision')
            # Copies of the same content cannot obtain independent lineage labels.
            copy=con.execute('SELECT lineage FROM uc_sources WHERE tenant=? AND agent=? AND hash=?',(*scope,h)).fetchone()
            if copy:lineage=copy['lineage']
            if old is None:
                previous=con.execute('SELECT revision FROM uc_sources WHERE tenant=? AND agent=? AND id=? AND active=1',(*scope,source_id)).fetchall()
                con.execute('UPDATE uc_sources SET active=0 WHERE tenant=? AND agent=? AND id=?',(*scope,source_id))
                if previous:
                    for row in con.execute('SELECT task,record FROM uc_claims WHERE tenant=? AND agent=?',scope).fetchall():
                        claim=Claim.from_json(row['record'])
                        if claim.source_ref==source_id:self._event(con,(*scope,row['task']),'source_revision_changed',{'source_ref':source_id,'revision':revision})
            con.execute('INSERT OR IGNORE INTO uc_sources VALUES(?,?,?,?,?,?,?,1)',(*scope,source_id,revision,lineage,h,provenance))
        return dict(source_ref=source_id,source_revision=revision,source_lineage_id=lineage,evidence_hash=h)
    def source(self,actor,source_ref,source_revision,*,con=None):
        scope=self.scope(actor)
        with (nullcontext(con) if con is not None else self.engine._db()) as db:
            row=db.execute('SELECT * FROM uc_sources WHERE tenant=? AND agent=? AND id=? AND revision=? AND active=1',(*scope,source_ref,source_revision)).fetchone()
            if row is None:raise PermissionError('source unavailable in authenticated scope')
            return dict(row)
    def add_claim(self,actor,claim):
        if type(claim) is not Claim:raise TypeError('typed Claim required')
        scope=self.scope(actor,claim.task_id,roles=('runtime','operator'))
        if claim.tenant_id!=actor.tenant:raise PermissionError('cross-tenant claim denied')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE');source=self.source(actor,claim.source_ref,claim.source_revision,con=con)
            if (source['hash'],source['lineage'])!=(claim.evidence_hash,claim.source_lineage_id):raise ValueError('claim evidence identity mismatch')
            old=con.execute('SELECT * FROM uc_claims WHERE id=?',(claim.claim_id,)).fetchone()
            if old:
                if (old['tenant'],old['agent'],old['task'])!=scope or old['record']!=claim.to_json():raise ValueError('claim ID already bound to other immutable content')
                return claim
            con.execute('INSERT INTO uc_claims VALUES(?,?,?,?,?)',(claim.claim_id,*scope,claim.to_json()))
            self._event(con,scope,'claim_registered',{'claim_id':claim.claim_id})
            # Contradicting evidence reopens a closed family in this transaction.
            rows=con.execute('SELECT * FROM uc_conflicts WHERE tenant=? AND agent=? AND task=?',scope).fetchall()
            for row in rows:
                conflict=Conflict.from_json(row['record'])
                compare_ids=conflict.claim_ids
                if conflict.status not in OPEN and conflict.resolution_ref:
                    resolution=con.execute('SELECT record FROM uc_resolutions WHERE id=?',(conflict.resolution_ref,)).fetchone()
                    if resolution:compare_ids=json.loads(resolution['record'])['accepted_claim_ids']
                originals=[self._claim(con,actor,cid) for cid in compare_ids]
                if any(contradicts(claim,old_claim) for old_claim in originals):
                    ids=list(dict.fromkeys(conflict.claim_ids+[claim.claim_id]))
                    reopened=conflict.status not in OPEN
                    conflict=replace(conflict,claim_ids=ids,status='reopened' if reopened else conflict.status,revision=conflict.revision+1,updated_at=self.clock(),resolution_ref=None if reopened else conflict.resolution_ref,reopened_from=conflict.resolution_ref if reopened else conflict.reopened_from)
                    self._write_conflict(con,scope,conflict,row['family'],'conflict_reopened' if reopened else 'conflict_evidence_added')
        return claim
    def _claim(self,con,actor,claim_id):
        scope=self.scope(actor)
        row=con.execute('SELECT record FROM uc_claims WHERE id=? AND tenant=? AND agent=?',(claim_id,*scope)).fetchone()
        if row is None:raise PermissionError('claim unavailable in authenticated scope')
        return Claim.from_json(row['record'])
    def claims(self,actor,task_id,*,con=None):
        scope=self.scope(actor,task_id)
        with (nullcontext(con) if con is not None else self.engine._db()) as db:
            return [Claim.from_json(r['record']) for r in db.execute('SELECT record FROM uc_claims WHERE tenant=? AND agent=? AND task=? ORDER BY id',scope)]
    def _write_conflict(self,con,scope,conflict,key,event):
        con.execute('INSERT INTO uc_conflicts VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record',(conflict.conflict_id,*scope,key,conflict.to_json()))
        self._event(con,scope,event,{'conflict_id':conflict.conflict_id,'revision':conflict.revision,'status':conflict.status})
    def register_conflict(self,actor,task_id,claim_ids,*,kind='source_disagreement',materiality='prerequisite',suspected=False):
        scope=self.scope(actor,task_id,roles=('runtime','operator'))
        if materiality not in {'prerequisite','low_impact','irrelevant'}:raise ValueError('host materiality category required')
        if not claim_ids and kind not in {'missing_required_evidence','tool_status_unknown'}:raise ValueError('resolvable claim references required')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE');claims=[self._claim(con,actor,cid) for cid in claim_ids]
            if any(c.task_id!=task_id for c in claims):raise PermissionError('cross-task conflict claim denied')
            key=digest([kind,sorted(set(family(c) for c in claims))])
            existing=con.execute('SELECT record FROM uc_conflicts WHERE tenant=? AND agent=? AND task=? AND family=?',(*scope,key)).fetchone()
            if existing:return Conflict.from_json(existing['record'])
            now=self.clock();cid=uuid.uuid4().hex
            decisions=[];rules=[]
            for link in con.execute('SELECT * FROM uc_links WHERE tenant=? AND agent=? AND task=?',scope):
                if set(claim_ids)&set(json.loads(link['claims'])):decisions.append(link['decision']);rules.extend(json.loads(link['rules']))
            conflict=Conflict(cid,dict(zip(('tenant_id','agent_id','task_id'),scope)),sorted(set(claim_ids)),kind,'suspected' if suspected else 'confirmed_open',decisions,sorted(set(rules)),materiality,now,now)
            self._write_conflict(con,scope,conflict,key,'conflict_registered')
            return conflict
    def detect(self,actor,task_id):
        claims=self.claims(actor,task_id);found={}
        for i,a in enumerate(claims):
            for b in claims[i+1:]:
                if contradicts(a,b):
                    c=self.register_conflict(actor,task_id,[a.claim_id,b.claim_id],kind='prior_vs_evidence' if 'prior' in (a.provenance_class,b.provenance_class) else 'source_disagreement',suspected=any(x.extraction_status!='verified' for x in (a,b)))
                    found[c.conflict_id]=c
        return list(found.values())
    def get_conflict(self,actor,conflict_id,*,con=None):
        scope=self.scope(actor)
        with (nullcontext(con) if con is not None else self.engine._db()) as db:
            row=db.execute('SELECT record FROM uc_conflicts WHERE id=? AND tenant=? AND agent=?',(conflict_id,*scope)).fetchone()
            if row is None:raise PermissionError('conflict unavailable in authenticated scope')
            return Conflict.from_json(row['record'])
    def conflicts(self,actor,task_id,open_only=False,*,con=None):
        scope=self.scope(actor,task_id)
        with (nullcontext(con) if con is not None else self.engine._db()) as db:
            records=[Conflict.from_json(r['record']) for r in db.execute('SELECT record FROM uc_conflicts WHERE tenant=? AND agent=? AND task=? ORDER BY id',scope)]
            return [c for c in records if not open_only or c.status in OPEN]
    def open_conflicts(self,actor,task_id,decision_id=None,*,con=None):
        records=self.conflicts(actor,task_id,True,con=con)
        if decision_id is None:return records
        deps=self.dependencies(actor,task_id,decision_id,con=con)
        return [c for c in records if decision_id in c.affected_decision_ids or set(c.claim_ids)&set(deps['claim_ids'])]
    def link(self,actor,task_id,decision_id,claim_ids,rule_ids=(),*,con=None):
        scope=self.scope(actor,task_id,roles=('runtime','operator'));_id(decision_id)
        for rule in rule_ids:_id(rule)
        own_transaction = con is None
        with (nullcontext(con) if con is not None else self.engine._db()) as con:
            if own_transaction: con.execute('BEGIN IMMEDIATE')
            for cid in claim_ids:
                if self._claim(con,actor,cid).task_id!=task_id:raise PermissionError('cross-task dependency denied')
            previous=con.execute('SELECT claims,rules FROM uc_links WHERE tenant=? AND agent=? AND task=? AND decision=?',(*scope,decision_id)).fetchone()
            if previous and (set(json.loads(previous['claims']))-set(claim_ids) or set(json.loads(previous['rules']))-set(rule_ids)):raise PermissionError('dependency links cannot be removed from an existing decision')
            con.execute('INSERT OR REPLACE INTO uc_links VALUES(?,?,?,?,?,?)',(*scope,decision_id,_json(list(claim_ids)),_json(list(rule_ids))))
            for row in con.execute('SELECT * FROM uc_conflicts WHERE tenant=? AND agent=? AND task=?',scope).fetchall():
                c=Conflict.from_json(row['record'])
                if set(c.claim_ids)&set(claim_ids):
                    c=replace(c,affected_decision_ids=sorted(set(c.affected_decision_ids+[decision_id])),affected_rule_ids=sorted(set(c.affected_rule_ids+list(rule_ids))),revision=c.revision+1,updated_at=self.clock())
                    self._write_conflict(con,scope,c,row['family'],'dependencies_linked')
            self._event(con,scope,'decision_linked',{'decision_id':decision_id})
    def dependencies(self,actor,task_id,decision_id,*,con=None):
        scope=self.scope(actor,task_id)
        with (nullcontext(con) if con is not None else self.engine._db()) as db:
            row=db.execute('SELECT * FROM uc_links WHERE tenant=? AND agent=? AND task=? AND decision=?',(*scope,decision_id)).fetchone()
            return {'claim_ids':json.loads(row['claims']) if row else [],'rule_ids':json.loads(row['rules']) if row else []}
    def transition(self,actor,conflict_id,status,*,expected_revision):
        self.scope(actor,roles=('runtime','operator'))
        if status not in {'investigating','unresolved_reported','confirmed_open','reopened'}:raise PermissionError('closure requires evidence-backed resolution service')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE');c=self.get_conflict(actor,conflict_id,con=con)
            if c.revision!=expected_revision:raise StaleRevision('conflict changed; reassess latest evidence')
            if c.status not in OPEN and status!='reopened':raise ValueError('closed conflict must reopen first')
            c=replace(c,status=status,revision=c.revision+1,updated_at=self.clock())
            row=con.execute('SELECT family FROM uc_conflicts WHERE id=?',(conflict_id,)).fetchone()
            self._write_conflict(con,self.scope(actor,c.scope['task_id']),c,row['family'],'conflict_transition')
            return c
    def delete_source(self,actor,source_ref,source_revision):
        self.scope(actor,roles=('operator',))
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE');self.source(actor,source_ref,source_revision,con=con)
            con.execute('UPDATE uc_sources SET active=0 WHERE tenant=? AND agent=? AND id=? AND revision=?',(*self.scope(actor),source_ref,source_revision))
            rows=con.execute('SELECT * FROM uc_claims WHERE tenant=? AND agent=?',self.scope(actor)).fetchall()
            for row in rows:
                c=Claim.from_json(row['record'])
                if (c.source_ref,c.source_revision)==(source_ref,source_revision):self._event(con,self.scope(actor,c.task_id),'source_deleted',{'source_ref':source_ref})
    def events(self,actor,task_id):
        with self.engine._db() as con:return [dict(r) for r in con.execute('SELECT seq,event,details,created FROM uc_events WHERE tenant=? AND agent=? AND task=? ORDER BY seq',self.scope(actor,task_id))]
