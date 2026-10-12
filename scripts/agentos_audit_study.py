"""Bounded paired simulated-audit studies. Caller must hold the bridge host lock.

Eight native calls are prepaid before inference. A crash between the shared
budget reservation and the study transaction burns budget without exposing
cases. Interrupted studies are failed, never resumed; reserved evidence remains
consumed. Acceptance is shadow-only, never permission to activate live advice.
"""
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
import time
import uuid

from nerve_awim.agentos_learning import atomic_json
from nerve_awim import agentos_audit_evidence as oracle
from nerve_awim import agentos_audit_cohort as cohort

BUDGET = dict(max_tokens=4096,max_iterations=2,timeout_seconds=90)
CALLS = 8
LIMITATION = 'Public simulated cohort held out from the proposer; scoped shadow evidence only, not general improvement or live audit approval.'


def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def database(host):
    path=host.directory/'audit-study.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS studies(id TEXT PRIMARY KEY,status TEXT NOT NULL,profile TEXT NOT NULL,model TEXT,revision TEXT NOT NULL,manifest TEXT NOT NULL,result TEXT,lesson TEXT,created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence(identity TEXT PRIMARY KEY,family TEXT UNIQUE NOT NULL,study TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS slots(study TEXT NOT NULL,number INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(study,number));
        CREATE TABLE IF NOT EXISTS receipts(study TEXT NOT NULL,number INTEGER NOT NULL,phase TEXT NOT NULL,arm TEXT NOT NULL,prompt_hash TEXT NOT NULL,output_hash TEXT NOT NULL,receipt TEXT NOT NULL,prompt TEXT NOT NULL,PRIMARY KEY(study,number));
        CREATE TRIGGER IF NOT EXISTS evidence_no_update BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
        CREATE TRIGGER IF NOT EXISTS receipts_no_update BEFORE UPDATE ON receipts BEGIN SELECT RAISE(ABORT,'immutable receipt'); END;
        CREATE TRIGGER IF NOT EXISTS receipts_no_delete BEFORE DELETE ON receipts BEGIN SELECT RAISE(ABORT,'immutable receipt'); END;
        ''')
        columns={row[1] for row in db.execute('PRAGMA table_info(receipts)')}
        if 'prompt' not in columns:
            db.execute("ALTER TABLE receipts ADD COLUMN prompt TEXT NOT NULL DEFAULT ''")
    return path


def remaining(host):
    with sqlite3.connect(host.path) as db:
        used=db.execute("SELECT COUNT(*) FROM nerve_calls WHERE day=? AND provider='hermes-free'",(time.strftime('%Y-%m-%d',time.gmtime()),)).fetchone()[0]
    return max(0,20-used)


def status(host):
    """Sanitized latest result, no fixture answers, prompts or generated advice."""
    path=database(host)
    with sqlite3.connect(path) as db:
        row=db.execute('SELECT id,status,profile,model,revision,result FROM studies ORDER BY created DESC,rowid DESC LIMIT 1').fetchone()
    result=dict(status='not_run',remaining_sessions=remaining(host),required_sessions=CALLS,limitation=LIMITATION)
    if row:
        result.update(study_id=row[0],status=row[1],profile=row[2],model=row[3],revision=row[4])
        if row[5]:
            result['result']=json.loads(row[5])
    pending=host.directory/'pending-audit-study.json'
    if pending.exists():
        try:
            item=json.loads(pending.read_text())
            result['pending']={key:item.get(key) for key in ('profile','cohort','requested_day','status','required_sessions','remaining_sessions')}
        except (ValueError,OSError):
            result['pending']={'status':'invalid_queue'}
    return result


class PrepaidHost:
    """Native callback consumes one persisted prepaid slot; cannot reserve more."""
    def __init__(self,host,path,study_id):
        self.directory=host.directory
        self.path=host.path
        self._database=path
        self._study=study_id
        self.current=None
        self.consumed=False

    def reserve_calls(self,provider,count,*,daily_limit=12):
        if provider!='hermes-free' or type(count) is not int or count!=1 or daily_limit!=20 or self.current is None or self.consumed:
            raise RuntimeError('invalid prepaid native reservation')
        with sqlite3.connect(self._database) as db:
            db.execute('BEGIN IMMEDIATE')
            active=db.execute('SELECT status FROM studies WHERE id=?',(self._study,)).fetchone()
            if not active or active[0]!='running':
                raise RuntimeError('study not active')
            changed=db.execute('UPDATE slots SET used=1 WHERE study=? AND number=? AND used=0',(self._study,self.current)).rowcount
            if changed!=1:
                raise RuntimeError('prepaid slot exhausted')
        self.consumed=True


def study(host,native,profile='qa-release'):
    """Queue or execute one fresh matched study; never infer when budget is short."""
    if type(profile) is not str or re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}',profile) is None:
        raise ValueError('invalid audit profile')
    data=cohort.cohort()
    cohort.validate_cohort(data)
    groups=data['splits']
    if {p:len(t) for p,t in groups.items()} != dict(train=2,selection=4,retention=4,final=6):
        raise ValueError('unexpected fixed audit split')
    revision=digest(dict(oracle=oracle.evaluator_revision(),cohort=cohort.revision(),runner=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    manifest=digest(data)
    path=database(host)
    pending=host.directory/'pending-audit-study.json'
    if pending.exists():
        try:
            request=json.loads(pending.read_text())
            matches=(request.get('cohort')==data['id'] and request.get('revision')==revision and request.get('manifest_sha256')==manifest and request.get('profile')==profile)
        except (ValueError,AttributeError):
            matches=False
        if not matches:
            return dict(status='queued_revision_mismatch',limitation='Queued study differs from current frozen scope; explicit queue review required before inference.')
    identities=[(cohort.canonical_identity(row),row['family']) for rows in groups.values() for row in rows]
    if len(set(x[0] for x in identities))!=len(identities) or len(set(x[1] for x in identities))!=len(identities):
        raise ValueError('duplicate evidence identity or family')
    with sqlite3.connect(path) as db:
        db.execute("UPDATE studies SET status='failed',result=? WHERE status='running'",(encode(dict(status='failed',reason='interrupted_no_replay')),))
        existing=db.execute('SELECT identity,family FROM evidence').fetchall()
    if any(i in {x[0] for x in existing} or f in {x[1] for x in existing} for i,f in identities):
        if pending.exists():
            pending.unlink()
        return dict(status='no_fresh_tasks',remaining_sessions=remaining(host),limitation=LIMITATION)
    if remaining(host)<CALLS:
        request=dict(profile=profile,cohort=data['id'],requested_day=time.strftime('%Y-%m-%d',time.gmtime()),status='queued_budget',required_sessions=CALLS,remaining_sessions=remaining(host),revision=revision,manifest_sha256=manifest)
        atomic_json(pending,request)
        return request
    # Separate ledgers deliberately favor burning prepaid slots over overspending.
    reserved_day=time.strftime('%Y-%m-%d',time.gmtime())
    host.reserve_calls('hermes-free',CALLS,daily_limit=20)
    sid='audit-'+uuid.uuid4().hex
    with sqlite3.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO studies VALUES(?,?,?,?,?,?,?,?,?)',(sid,'running',profile,None,revision,manifest,None,None,int(time.time())))
        db.executemany('INSERT INTO evidence VALUES(?,?,?)',[(i,f,sid) for i,f in identities])
        db.executemany('INSERT INTO slots(study,number) VALUES(?,?)',[(sid,n) for n in range(CALLS)])
    if pending.exists():
        pending.unlink()
    proxy=PrepaidHost(host,path,sid)
    number=0
    model=None
    phase_results={}
    lesson=None
    def invoke(phase,arm,prompt):
        nonlocal number
        if time.strftime('%Y-%m-%d',time.gmtime())!=reserved_day:
            raise RuntimeError('prepaid UTC day changed')
        if number>=CALLS:
            raise RuntimeError('prepaid study bound exceeded')
        slot=number
        number+=1
        proxy.current=slot
        proxy.consumed=False
        receipt=native(proxy,profile,prompt,max_tokens=BUDGET['max_tokens'])
        # Persist returned evidence before checking contracts/drift, for diagnosis.
        with sqlite3.connect(path) as db:
            db.execute('INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)',(sid,slot,phase,arm,digest(prompt),digest(receipt),encode(receipt),prompt))
        if not proxy.consumed:
            raise RuntimeError('native callback did not consume prepaid reservation')
        if (receipt.get('ok') is not True or receipt.get('requested_model')!=model or type(receipt.get('tools')) is not int or receipt.get('tools')!=0
                or any(type(receipt.get(k)) is not int or receipt[k]!=v for k,v in BUDGET.items())):
            raise RuntimeError('native identity or budget drift')
        return receipt.get('value')
    def predict(phase,arm,advice=None):
        tasks=[dict(id=r['id'],bundle=r['bundle']) for r in groups[phase]]
        prompt=('Audit the simulated evidence only. Return JSON keyed by every task ID; each value has exactly decision and citations. '
                'decision is supported,contradicted,unknown. Cite ALL matching fresh independent root sources, including both sides of conflicts; '
                'fields must list model,provider,observed_at and all fields.KEY names for that source. No applicable evidence means unknown with empty citations. '
                'Assertions/derived records do not prove observations. Match model/provider, request for execution, inclusive at-max_age..at freshness. '
                'This is a recorded-request claim, not general availability. No prose or extra keys.\n'
                +encode(dict(tasks=tasks,advice=advice)))
        value=invoke(phase,arm,prompt)
        if type(value) is not dict or set(value)!={r['id'] for r in groups[phase]}:
            raise ValueError('malformed audit batch')
        judged={r['id']:oracle.judge_decision(r['bundle'],value[r['id']]) for r in groups[phase]}
        if any(j['category']=='invalid_output' for j in judged.values()):
            raise ValueError('malformed audit decision')
        return value,judged
    try:
        snapshots=host.directory/'audit-study-snapshots'/sid
        snapshots.mkdir(parents=True,exist_ok=False)
        atomic_json(snapshots/'cohort.json',data)
        atomic_json(snapshots/'scope.json',dict(profile=profile,revision=revision,manifest_sha256=manifest,reserved_day=reserved_day,budget=BUDGET))
        for label,source in (('oracle.py',Path(oracle.__file__)),('cohort.py',Path(cohort.__file__)),('runner.py',Path(__file__))):
            (snapshots/label).write_bytes(source.read_bytes())
        if time.strftime('%Y-%m-%d',time.gmtime())!=reserved_day:
            raise RuntimeError('prepaid UTC day changed')
        inspected=native(proxy,profile,'',max_tokens=4096,inspect=True)
        model=inspected.get('requested_model')
        if inspected.get('ok') is not True or type(model) is not str or not model.endswith(':free'):
            raise ValueError('model inspection failed')
        with sqlite3.connect(path) as db:
            db.execute('UPDATE studies SET model=? WHERE id=?',(model,sid))
        answers,checks=predict('train','baseline')
        train=[dict(task=dict(id=r['id'],bundle=r['bundle']),answer=answers[r['id']],feedback=checks[r['id']]) for r in groups['train']]
        proposal=invoke('proposal','lesson','Return JSON {"lesson":"bounded reusable procedural advice"}. Learn only from this training feedback.\n'+encode(train))
        if type(proposal) is not dict or set(proposal)!={'lesson'} or type(proposal['lesson']) is not str or not 1<=len(proposal['lesson'])<=2048:
            raise ValueError('invalid bounded lesson')
        lesson=proposal['lesson']
        with sqlite3.connect(path) as db:
            db.execute('UPDATE studies SET lesson=? WHERE id=?',(lesson,sid))
        outcome='shadow_accepted'
        for phase in ('selection','retention','final'):
            arms=['baseline','lesson']; random.SystemRandom().shuffle(arms)
            paired={}
            for arm in arms:
                values,judged=predict(phase,arm,lesson if arm=='lesson' else None)
                paired[arm]=(values,judged)
            base=paired['baseline'][1]; learned=paired['lesson'][1]
            wins=sum(learned[k]['passed'] and not base[k]['passed'] for k in base)
            losses=sum(base[k]['passed'] and not learned[k]['passed'] for k in base)
            unsupported=sum(paired['lesson'][0][r['id']]['decision']=='supported' and r['expected']['decision']!='supported' for r in groups[phase])
            phase_results[phase]=dict(tasks=len(base),baseline_hits=sum(x['passed'] for x in base.values()),lesson_hits=sum(x['passed'] for x in learned.values()),wins=wins,losses=losses,unsupported_positives=unsupported)
            if losses or unsupported or (phase!='retention' and wins==0):
                outcome='no_gain' if not losses and not unsupported else 'rejected'
                break
        result=dict(status=outcome,phases=phase_results,native_sessions=number,prepaid_sessions=CALLS,activation_authorized=False,scope=data['scope'],manifest_sha256=manifest,limitation=LIMITATION)
    except Exception as error:
        outcome='failed'
        result=dict(status='failed',reason=type(error).__name__,native_sessions=number,prepaid_sessions=CALLS,activation_authorized=False,phases=phase_results,limitation=LIMITATION)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE studies SET status=?,result=? WHERE id=?',(outcome,encode(result),sid))
    result.update(study_id=sid,profile=profile,model=model,revision=revision)
    atomic_json(host.directory/'latest-audit-study.json',result)
    return result
