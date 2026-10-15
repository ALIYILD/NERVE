"""ARC manifests and operator controls on the existing governed release store.

This extends a known gl_releases route with a versioned ARC mode; it cannot
install code, alter a handler, activate a learned route or approve clinical use.
The existing governed route release must remain identical through review.
"""
import json
import time
import uuid
from .arc_contracts import SCHEMA
from .governed_learning_v20 import _json


def release_dispatch_guard(con, actor, task):
    """Called by the shared ARC dispatch boundary in its existing transaction."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='arc_release_manifests'").fetchone():
        return
    row=con.execute("SELECT * FROM arc_release_manifests WHERE tenant=? AND agent=? AND context=? AND status='active'",
                    (actor.tenant,actor.agent,task.context)).fetchone()
    if row is None:
        return
    state=con.execute('SELECT active,generation,contract FROM gl_state WHERE tenant=? AND agent=?',
                      (actor.tenant,actor.agent)).fetchone()
    if (state is None or (state['active'],state['generation'])!=(row['release'],row['generation'])
            or state['contract']!=json.loads(row['versions'])['policy']):
        raise PermissionError('governed release changed after ARC review')
    if row['mode'] != 'enforce':
        raise PermissionError('staged ARC mode does not authorize dispatch')
    if row['used'] >= row['canary_limit']:
        raise PermissionError('ARC canary budget exhausted; operator review required')
    con.execute('UPDATE arc_release_manifests SET used=used+1 WHERE id=?',(row['id'],))


class ArcOperations:
    def __init__(self, runtime):
        self.runtime, self.engine = runtime, runtime.engine
        with self.engine._db() as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS arc_release_manifests(
              id TEXT PRIMARY KEY,tenant TEXT,agent TEXT,context TEXT,release TEXT,generation INTEGER,
              versions TEXT,mode TEXT,previous_mode TEXT,canary_limit INTEGER,used INTEGER,
              proposer TEXT,status TEXT,review TEXT,created REAL);
            ''')
            if 'previous_manifest' not in {r[1] for r in con.execute('PRAGMA table_info(arc_release_manifests)')}:
                con.execute('ALTER TABLE arc_release_manifests ADD COLUMN previous_manifest TEXT')

    def stage(self, actor, *, context, mode, versions, canary_limit=5):
        scope=self.engine._scope(actor,'evaluator','operator')
        if context not in self.engine._arc_contexts or mode not in {'off','shadow','enforce'}:
            raise ValueError('registered context and mode required')
        if type(canary_limit) is not int or not 1<=canary_limit<=20:
            raise ValueError('canary limit must be 1..20')
        keys={'schema','prompt','model','policy','strategy'}
        if (type(versions) is not dict or set(versions)!=keys
                or any(type(v) is not str or not 1<=len(v)<=128 for v in versions.values())
                or versions['schema']!=SCHEMA or versions['policy']!=self.engine.contract):
            raise ValueError('compatible separately versioned manifest required')
        if context=='prepare-draft' and mode=='enforce':
            raise PermissionError('clinical activation requires an external domain review process; synthetic demos only')
        ident=uuid.uuid4().hex
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); state=self.engine._state(con,scope)
            previous=self.runtime._mode(con,actor,context)
            prior=con.execute("SELECT id FROM arc_release_manifests WHERE tenant=? AND agent=? AND context=? AND status='active'",(*scope,context)).fetchone()
            con.execute('INSERT INTO arc_release_manifests(id,tenant,agent,context,release,generation,versions,mode,previous_mode,canary_limit,used,proposer,status,review,created) VALUES(?,?,?,?,?,?,?,?,?,?,0,?,?,NULL,?)',
                        (ident,*scope,context,state['active'],state['generation'],_json(versions),mode,previous,
                         canary_limit,actor._nonce,'staged',time.time()))
            if prior:
                con.execute('UPDATE arc_release_manifests SET previous_manifest=? WHERE id=?',(prior['id'],ident))
            self.engine._event(con,scope,'arc_release_staged',{'manifest':ident,'context':context,'mode':mode})
        return ident

    def _row(self,con,actor,ident):
        scope=self.engine._scope(actor,'operator','auditor','evaluator')
        row=con.execute('SELECT * FROM arc_release_manifests WHERE id=? AND tenant=? AND agent=?',(ident,*scope)).fetchone()
        if row is None: raise PermissionError('manifest outside actor scope')
        return row

    def promote(self,actor,ident,*,review):
        scope=self.engine._scope(actor,'operator')
        if type(review) is not str or not 1<=len(review)<=512: raise ValueError('bounded review reference required')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row=self._row(con,actor,ident); state=self.engine._state(con,scope)
            if row['proposer']==actor._nonce: raise PermissionError('release proposer cannot approve itself')
            if row['status']!='staged' or (row['release'],row['generation'])!=(state['active'],state['generation']):
                raise ValueError('stale manifest or governed release changed')
            if self.runtime._mode(con,actor,row['context'])!=row['previous_mode']:
                raise ValueError('mode changed since staging')
            con.execute("UPDATE arc_release_manifests SET status='superseded' WHERE tenant=? AND agent=? AND context=? AND status='active'",(*scope,row['context']))
            con.execute("UPDATE arc_release_manifests SET status='active',review=? WHERE id=?",(review,ident))
            con.execute('INSERT OR REPLACE INTO arc_modes VALUES(?,?,?,?)',(*scope,row['context'],row['mode']))
            self.engine._event(con,scope,'arc_release_promoted',{'manifest':ident,'review':review,'mode':row['mode']})
        return self.status(actor)

    def rollback(self,actor,ident,*,review):
        scope=self.engine._scope(actor,'operator')
        if type(review) is not str or not 1<=len(review)<=512: raise ValueError('review reference required')
        with self.engine._db() as con:
            con.execute('BEGIN IMMEDIATE'); row=self._row(con,actor,ident)
            if row['status']!='active': raise ValueError('only active manifests may roll back')
            state=self.engine._state(con,scope)
            if (state['active'],state['generation'])!=(row['release'],row['generation']):
                raise ValueError('governed release changed; reconcile before rollback')
            # Restore the recorded compatible mode; do not erase completed audit rows.
            con.execute('INSERT OR REPLACE INTO arc_modes VALUES(?,?,?,?)',(*scope,row['context'],row['previous_mode']))
            decisions=con.execute('SELECT id,record,status FROM arc_decisions WHERE tenant=? AND agent=?',scope).fetchall()
            for decision in decisions:
                tool=json.loads(decision['record'])['action']['registered_tool']
                if self.runtime.tools[tool].context!=row['context']: continue
                if decision['status'] in {'executing','awaiting_verification'}:
                    con.execute("UPDATE arc_decisions SET status='uncertain',approval=NULL,version=version+1 WHERE id=?",(decision['id'],))
                elif decision['status'] in {'ready','awaiting_approval','validated','proposed'}:
                    con.execute("UPDATE arc_decisions SET status='cancelled',approval=NULL,version=version+1 WHERE id=?",(decision['id'],))
            con.execute("UPDATE arc_release_manifests SET status='rolled_back',review=? WHERE id=?",(review,ident))
            if row['previous_manifest']:
                previous=self._row(con,actor,row['previous_manifest'])
                if previous['status']!='superseded' or previous['context']!=row['context']:
                    raise ValueError('previous manifest is no longer compatible')
                con.execute("UPDATE arc_release_manifests SET status='active' WHERE id=?",(previous['id'],))
            self.engine._event(con,scope,'arc_rollback',{'manifest':ident,'review':review,'restored_mode':row['previous_mode']})
        return self.status(actor)

    def status(self,actor):
        scope=self.engine._scope(actor,'operator','auditor','evaluator')
        with self.engine._db() as con:
            rows=con.execute('SELECT id,context,release,generation,versions,mode,previous_mode,canary_limit,used,status FROM arc_release_manifests WHERE tenant=? AND agent=? ORDER BY created',scope).fetchall()
            modes=con.execute('SELECT context,mode FROM arc_modes WHERE tenant=? AND agent=?',scope).fetchall()
        return {'manifests':[dict(r) for r in rows],'modes':dict((r['context'],r['mode']) for r in modes),
                'default_mode':self.runtime.mode,'production_activation':False}

    def inspect(self,actor,*,task_id=None,decision_id=None):
        scope=self.engine._scope(actor,'operator','auditor','runtime')
        with self.engine._db() as con:
            rows=con.execute('SELECT id,task,status,version,record,outcome FROM arc_decisions WHERE tenant=? AND agent=? ORDER BY rowid',scope).fetchall()
        result=[]
        for row in rows:
            if task_id is not None and row['task']!=task_id: continue
            if decision_id is not None and row['id']!=decision_id: continue
            record=json.loads(row['record']); outcome=json.loads(row['outcome']) if row['outcome'] else None
            result.append({'decision_id':row['id'],'task_id':row['task'],'correlation_id':record['correlation_id'],
                'status':row['status'],'version':row['version'],'tool':record['action']['registered_tool'],
                'evidence':[{'source_id':r['source_id'],'version':r['source_version_or_hash']} for r in record['evidence_refs']],
                'transport_status':outcome['transport_status'] if outcome else None,
                'semantic_status':outcome['semantic_status'] if outcome else None,
                'criterion_results':outcome['criterion_results'] if outcome else None,
                'retry_classification':outcome['retry_classification'] if outcome else None})
        return result

    def replay(self,actor,decision_id):
        # Audit replay only: deliberately never calls any handler or provider.
        records=self.inspect(actor,decision_id=decision_id)
        if not records: raise PermissionError('decision outside actor scope')
        return {'replay':'recorded-redacted-episode','effects':False,'episode':records[0]}

    def metrics(self,actor):
        scope=self.engine._scope(actor,'operator','auditor')
        with self.engine._db() as con:
            counts=dict(con.execute('SELECT status,COUNT(*) FROM arc_decisions WHERE tenant=? AND agent=? GROUP BY status',scope).fetchall())
            events=dict(con.execute("SELECT event,COUNT(*) FROM gl_events WHERE tenant=? AND agent=? AND event LIKE 'arc_%' GROUP BY event",scope).fetchall())
        return {'decision_statuses':counts,'events':events,'labels':'No patient or source payload labels'}
