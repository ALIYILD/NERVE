"""Paired monitoring of accepted simulated audit advice; never live activation.

Caller holds the bridge host lock. Two calls are prepaid and never refunded.
Interrupted episodes revoke the candidate and consume their evidence forever.
Source kinds are host-owned fixture assumptions, not authenticated live facts.
Shadow monitoring is stricter than label-only reporting: a supported claim with
invalid citations is an unsupported positive, even when its label matches truth.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re
import sqlite3
import time
import uuid

from nerve_awim import agentos_audit_evidence as oracle
from nerve_awim import agentos_audit_cohort as cohort
from nerve_awim.agentos_audit_fixtures import development_cases

_spec=importlib.util.spec_from_file_location('_audit_shadow_study',Path(__file__).with_name('agentos_audit_study.py'))
studies=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(studies)
BUDGET=studies.BUDGET
LIFETIME=30*86400
LIMITATION='Simulated host-owned evidence only; shadow monitoring never authorizes operational activation.'


def database(host):
    path=host.directory/'audit-shadow.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,state TEXT NOT NULL,reason TEXT,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY,candidate TEXT NOT NULL,identity TEXT UNIQUE NOT NULL,family TEXT UNIQUE NOT NULL,state TEXT NOT NULL,task TEXT NOT NULL,result TEXT,created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS slots(episode TEXT NOT NULL,number INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(episode,number));
        CREATE TABLE IF NOT EXISTS requests(episode TEXT NOT NULL,number INTEGER NOT NULL,arm TEXT NOT NULL,prompt TEXT NOT NULL,prompt_hash TEXT NOT NULL,PRIMARY KEY(episode,number));
        CREATE TABLE IF NOT EXISTS receipts(episode TEXT NOT NULL,number INTEGER NOT NULL,arm TEXT NOT NULL,prompt TEXT NOT NULL,prompt_hash TEXT NOT NULL,response TEXT NOT NULL,response_hash TEXT NOT NULL,PRIMARY KEY(episode,number));
        CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON episodes BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        CREATE TRIGGER IF NOT EXISTS evidence_no_rewrite BEFORE UPDATE OF identity,family,task,candidate ON episodes BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        CREATE TRIGGER IF NOT EXISTS requests_no_update BEFORE UPDATE ON requests BEGIN SELECT RAISE(ABORT,'immutable request'); END;
        CREATE TRIGGER IF NOT EXISTS requests_no_delete BEFORE DELETE ON requests BEGIN SELECT RAISE(ABORT,'immutable request'); END;
        CREATE TRIGGER IF NOT EXISTS receipts_no_update BEFORE UPDATE ON receipts BEGIN SELECT RAISE(ABORT,'immutable receipt'); END;
        CREATE TRIGGER IF NOT EXISTS receipts_no_delete BEFORE DELETE ON receipts BEGIN SELECT RAISE(ABORT,'immutable receipt'); END;
        ''')
    return path


def _candidate(host,study_id=None):
    path=host.directory/'audit-study.sqlite3'
    if not path.exists():
        return None
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        if study_id is None:
            row=db.execute("SELECT * FROM studies WHERE status='shadow_accepted' ORDER BY created DESC,rowid DESC LIMIT 1").fetchone()
        else:
            row=db.execute('SELECT * FROM studies WHERE id=?',(study_id,)).fetchone()
    if not row or row['status']!='shadow_accepted':
        return None
    row=dict(row)
    try:
        if re.fullmatch(r'audit-[a-f0-9]{32}',row['id']) is None:
            return None
        result=json.loads(row['result'])
        revision=studies.digest(dict(oracle=oracle.evaluator_revision(),cohort=cohort.revision(),runner=hashlib.sha256(Path(studies.__file__).read_bytes()).hexdigest()))
        if (result.get('status')!='shadow_accepted' or result.get('activation_authorized') is not False
                or result.get('scope')!=cohort.SCOPE or row['revision']!=revision
                or type(row['lesson']) is not str or not 1<=len(row['lesson'])<=2048
                or type(row['profile']) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',row['profile']) is None
                or type(row['model']) is not str or not row['model'].endswith(':free')
                or type(row['created']) is not int or not 0<=row['created']<=int(time.time())):
            return None
        with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            receipts=db.execute('SELECT * FROM receipts WHERE study=? ORDER BY number',(row['id'],)).fetchall()
            slots=db.execute('SELECT number,used FROM slots WHERE study=? ORDER BY number',(row['id'],)).fetchall()
        if len(receipts)!=8 or [(r['number'],r['used']) for r in slots]!=[(i,1) for i in range(8)]:
            return None
        proposals=[]
        layout=[]
        for receipt in receipts:
            raw=json.loads(receipt['receipt'])
            if studies.digest(raw)!=receipt['output_hash'] or studies.digest(receipt['prompt'])!=receipt['prompt_hash']:
                return None
            if (type(raw) is not dict or raw.get('ok') is not True or raw.get('requested_model')!=row['model']
                    or type(raw.get('tools')) is not int or raw['tools']!=0
                    or any(type(raw.get(k)) is not int or raw[k]!=v for k,v in BUDGET.items())):
                return None
            layout.append((receipt['phase'],receipt['arm']))
            if receipt['phase']=='proposal':
                proposals.append(raw.get('value'))
        if (layout[:2]!=[('train','baseline'),('proposal','lesson')]
                or any(set(layout[start:start+2])!={(phase,'baseline'),(phase,'lesson')} for phase,start in (('selection',2),('retention',4),('final',6)))):
            return None
        if proposals!=[{'lesson':row['lesson']}]:
            return None
        phases=result.get('phases')
        if type(phases) is not dict or set(phases)!={'selection','retention','final'}:
            return None
        for phase,count in (('selection',4),('retention',4),('final',6)):
            scores=phases[phase]
            if type(scores) is not dict or any(type(scores.get(k)) is not int or not 0<=scores[k]<=count for k in ('tasks','baseline_hits','lesson_hits','wins','losses','unsupported_positives')):
                return None
            if (scores['tasks']!=count or scores['losses']!=0 or scores['unsupported_positives']!=0
                    or scores['lesson_hits']!=scores['baseline_hits']+scores['wins']
                    or (phase!='retention' and scores['wins']<1)):
                return None
        frozen=host.directory/'audit-study-snapshots'/row['id']
        data=json.loads((frozen/'cohort.json').read_text())
        scope=json.loads((frozen/'scope.json').read_text())
        if (studies.digest(data)!=row['manifest'] or row['manifest']!=studies.digest(cohort.cohort())
                or result.get('manifest_sha256')!=row['manifest']
                or scope.get('revision')!=revision or scope.get('profile')!=row['profile']
                or scope.get('manifest_sha256')!=row['manifest'] or studies.digest(scope.get('budget'))!=studies.digest(BUDGET)):
            return None
        for name,path in (('oracle.py',Path(oracle.__file__)),('cohort.py',Path(cohort.__file__)),('runner.py',Path(studies.__file__))):
            if (frozen/name).read_bytes()!=path.read_bytes():
                return None
        return row
    except (ValueError,TypeError,KeyError,OSError,AttributeError):
        return None


def status(host):
    """Sanitized state only; does not resume calls or expose advice/source bundles."""
    path=database(host)
    with sqlite3.connect(path) as db:
        rows=db.execute('SELECT id,state,reason,expires FROM candidates ORDER BY rowid DESC').fetchall()
        count=db.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]
    states=[]
    for ident,state,reason,expires in rows:
        if state=='active':
            state='expired' if expires<=int(time.time()) else 'active' if _candidate(host,ident) is not None else 'ineligible'
        states.append(dict(study_id=ident,state=state,reason=reason,expires_at=expires))
    eligible=_candidate(host)
    if eligible and eligible['id'] not in {r['study_id'] for r in states}:
        state='expired' if eligible['created']+LIFETIME<=int(time.time()) else 'eligible_unmonitored'
        states.insert(0,dict(study_id=eligible['id'],state=state,reason=None,expires_at=eligible['created']+LIFETIME))
    return dict(status=states[0]['state'] if states else 'no_candidate',candidates=states,episodes=count,activation_authorized=False,limitation=LIMITATION)


class PrepaidHost:
    def __init__(self,host,path,episode):
        self.path=host.path
        self.directory=host.directory
        self._db=path
        self._episode=episode
        self.current=None
        self.consumed=False

    def reserve_calls(self,provider,count,*,daily_limit=12):
        if provider!='hermes-free' or type(count) is not int or count!=1 or daily_limit!=20 or self.current is None or self.consumed:
            raise RuntimeError('invalid shadow prepaid reservation')
        with sqlite3.connect(self._db) as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT state FROM episodes WHERE id=?',(self._episode,)).fetchone()[0]!='running':
                raise RuntimeError('episode not active')
            changed=db.execute('UPDATE slots SET used=1 WHERE episode=? AND number=? AND used=0',(self._episode,self.current)).rowcount
            if changed!=1:
                raise RuntimeError('shadow prepaid slot exhausted')
        self.consumed=True


def monitor(host,native,task,study_id=None):
    """Compare one fresh simulated task with/without exact scoped accepted advice."""
    path=database(host)
    with sqlite3.connect(path) as db:
        interrupted=[r[0] for r in db.execute("SELECT candidate FROM episodes WHERE state='running'")]
        db.execute("UPDATE episodes SET state='failed',result=? WHERE state='running'",(studies.encode(dict(reason='interrupted_no_replay')),))
        for candidate in interrupted:
            db.execute("UPDATE candidates SET state='revoked',reason='interrupted_episode' WHERE id=?",(candidate,))
    candidate=_candidate(host,study_id)
    if candidate is None:
        return dict(status='no_candidate',reason='no_exact_accepted_candidate',activation_authorized=False)
    sid=candidate['id']; expires=candidate['created']+LIFETIME
    with sqlite3.connect(path) as db:
        db.execute("INSERT OR IGNORE INTO candidates VALUES(?,'active',NULL,?)",(sid,expires))
        if expires<=int(time.time()):
            db.execute("UPDATE candidates SET state='expired',reason='thirty_day_expiry' WHERE id=? AND state='active'",(sid,))
        state=db.execute('SELECT state FROM candidates WHERE id=?',(sid,)).fetchone()[0]
    if state!='active':
        return dict(status=state,study_id=sid,activation_authorized=False)
    if type(task) is not dict or set(task)!={'id','family','bundle'}:
        raise ValueError('exact task id,family,bundle required')
    for key in ('id','family'):
        if type(task[key]) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}',task[key]) is None:
            raise ValueError('invalid task '+key)
    oracle.validate_bundle(task['bundle'])
    identity=cohort.canonical_identity(task)
    registry_path=host.directory/'cohort-registry.sqlite3'
    if registry_path.exists():
        with sqlite3.connect(f'file:{registry_path}?mode=ro',uri=True) as db:
            if db.execute('SELECT 1 FROM evidence WHERE identity=? OR family=?',(identity,task['family'])).fetchone():
                return dict(status='reused_evidence',study_id=sid,activation_authorized=False)
    reserved=[r for group in cohort.cohort()['splits'].values() for r in group]+development_cases()
    if identity in {cohort.canonical_identity(r) for r in reserved} or task['family'] in {r['family'] for r in reserved}:
        return dict(status='reused_evidence',study_id=sid,activation_authorized=False)
    with sqlite3.connect(path) as db:
        if db.execute('SELECT 1 FROM episodes WHERE identity=? OR family=?',(identity,task['family'])).fetchone():
            return dict(status='reused_evidence',study_id=sid,activation_authorized=False)
    if studies.remaining(host)<2:
        return dict(status='deferred_daily_budget',required_sessions=2,remaining_sessions=studies.remaining(host),activation_authorized=False)
    day=time.strftime('%Y-%m-%d',time.gmtime())
    host.reserve_calls('hermes-free',2,daily_limit=20)
    episode='shadow-'+uuid.uuid4().hex
    with sqlite3.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?,?,?)',(episode,sid,identity,task['family'],'running',studies.encode(task),None,int(time.time())))
        db.executemany('INSERT INTO slots(episode,number) VALUES(?,?)',[(episode,0),(episode,1)])
    proxy=PrepaidHost(host,path,episode)
    answers={}; calls=0
    try:
        if time.strftime('%Y-%m-%d',time.gmtime())!=day:
            raise RuntimeError('prepaid UTC day changed')
        inspected=native(proxy,candidate['profile'],'',max_tokens=4096,inspect=True)
        if inspected.get('ok') is not True or inspected.get('requested_model')!=candidate['model']:
            raise RuntimeError('model inspection drift')
        arms=['baseline','lesson']; random.SystemRandom().shuffle(arms)
        for number,arm in enumerate(arms):
            if time.strftime('%Y-%m-%d',time.gmtime())!=day:
                raise RuntimeError('prepaid UTC day changed')
            prompt=('Audit this simulated host-owned evidence. Return exactly {"decision":"supported|contradicted|unknown","citations":[{"source_id":"...","fields":["..."]}]}. '
                    'Cite all matching fresh independent root sources, including conflicting roots. Fields: model,provider,observed_at plus every fields.KEY. '
                    'Match model/provider/request and inclusive at-max_age..at. Derived/assertion sources are not independent proof. No applicable evidence means unknown with no citations.\n'
                    +studies.encode(dict(task=dict(id=task['id'],bundle=task['bundle']),advice=candidate['lesson'] if arm=='lesson' else None)))
            proxy.current=number; proxy.consumed=False; calls+=1
            with sqlite3.connect(path) as db:
                db.execute('INSERT INTO requests VALUES(?,?,?,?,?)',(episode,number,arm,prompt,studies.digest(prompt)))
            receipt=native(proxy,candidate['profile'],prompt,max_tokens=4096)
            with sqlite3.connect(path) as db:
                db.execute('INSERT INTO receipts VALUES(?,?,?,?,?,?,?)',(episode,number,arm,prompt,studies.digest(prompt),studies.encode(receipt),studies.digest(receipt)))
            if (not proxy.consumed or receipt.get('ok') is not True or receipt.get('requested_model')!=candidate['model']
                    or type(receipt.get('tools')) is not int or receipt['tools']!=0
                    or any(type(receipt.get(k)) is not int or receipt[k]!=v for k,v in BUDGET.items())):
                raise RuntimeError('native metadata drift')
            judged=oracle.judge_decision(task['bundle'],receipt.get('value'))
            if judged['category']=='invalid_output':
                raise ValueError('malformed audit output')
            answers[arm]=(receipt['value'],judged)
        loss=answers['baseline'][1]['passed'] and not answers['lesson'][1]['passed']
        unsupported=answers['lesson'][0]['decision']=='supported' and not answers['lesson'][1]['passed']
        revoked=bool(loss or unsupported)
        result=dict(status='revoked' if revoked else 'active',paired_loss=bool(loss),unsupported_positive=unsupported,
                    baseline_passed=answers['baseline'][1]['passed'],lesson_passed=answers['lesson'][1]['passed'],native_sessions=calls)
        reason='paired_regression' if loss else 'unsupported_positive' if unsupported else None
        episode_state='completed'
    except Exception as error:
        result=dict(status='revoked',reason=type(error).__name__,native_sessions=calls)
        revoked=True; reason='failed_episode'; episode_state='failed'
    result.update(episode_id=episode,study_id=sid,activation_authorized=False,limitation=LIMITATION)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE episodes SET state=?,result=? WHERE id=?',(episode_state,studies.encode(result),episode))
        if revoked:
            db.execute("UPDATE candidates SET state='revoked',reason=? WHERE id=?",(reason,sid))
    return result
