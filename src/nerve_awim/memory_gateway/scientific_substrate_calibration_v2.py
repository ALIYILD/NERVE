"""Exactly ten supported DEV tasks, three interfaces, one seed; calibration only."""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

from . import scientific_substrate_calibration_transport_v2 as transport
from . import scientific_candidate_transport_smoke as smoke
from . import scientific_substrate_calibration as predecessor
from . import scientific_task_bank as bank_module
from .scientific_structured_tasks import parse,parse_shape,_object,_nonfinite
from ..memory_v18 import MemoryAuthority
from .contracts import MemoryScope,MemoryRequest
from .research_supervisor import _exclusive

pilot=smoke.pilot
canonical,_hash=pilot._json,pilot._hash
metadata,preload,runtime_version=smoke.metadata,smoke.preload,smoke.runtime_version
VERSION='scientific-substrate-calibration-v2'
SEED=20261015
MAX_SECONDS=3600
ARMS=transport.ARMS


def _preload_valid(value):
    return (type(value) is dict and 'wall_seconds' in value
        and set(value)<={'wall_seconds','load_duration_nanoseconds','total_duration_nanoseconds'}
        and type(value['wall_seconds']) in (int,float) and math.isfinite(value['wall_seconds']) and value['wall_seconds']>=0
        and all(type(v) is int and v>=0 for k,v in value.items() if k!='wall_seconds'))


def sources():
    pins=predecessor.sources();pins.update(bank_module.sources())
    for relative in ('src/nerve_awim/memory_gateway/scientific_compact_dev_transport.py',
        'src/nerve_awim/memory_gateway/scientific_substrate_calibration_transport_v2.py',
        'src/nerve_awim/memory_gateway/scientific_substrate_calibration_v2.py',
        'scripts/run_scientific_substrate_calibration_v2.py'):
        pins[relative]=sha256((pilot.ROOT/relative).read_bytes()).hexdigest()
    for name in ('docs/galahad/evidence/scientific-candidate-format-study-v1.json','docs/galahad/evidence/scientific-candidate-transport-smoke-v1.json'):
        pins[name]=sha256((pilot.ROOT/name).read_bytes()).hexdigest()
    return pins


def selected(bank_directory,manifest):
    authority=MemoryAuthority();actor=authority.issue('synthetic-science','substrate-calibration',permissions=('read',))
    bank=bank_module.ScientificTaskBank(bank_directory,authority,expected_manifest_hash=manifest,
        tenant_id='synthetic-science',generator_agent_id='substrate-calibration')
    rows=[r for r in bank.development(actor) if r['stratum']=='supported-measurement']
    rows.sort(key=lambda r:(sha256(f'substrate:{SEED}:{r["task_id"]}'.encode()).hexdigest(),r['task_id']))
    if len(rows)<10:raise ValueError('ten_supported_development_tasks_required')
    return rows[:10]


def schedule(tasks):
    return [[task['task_id'],arm] for arm in ('compact','forced_answer','original') for task in tasks]


def score(raw,arm,task):
    declared=raw.strip()=='ABSTAIN'
    if not declared:
        try:
            shape=json.loads(raw,object_pairs_hook=_object,parse_constant=_nonfinite)
            declared=type(shape) is dict and shape.get('status')=='abstain'
        except (ValueError,TypeError,RecursionError):pass
    try:
        decoded=parse(raw) if arm=='original' else transport.compact.decode(raw,transport.compact.prepare(task['query'],task['evidence']))
        valid=True
    except ValueError:decoded=None;valid=False
    return dict(format_valid=valid,valid_parsed_answer=valid and decoded['status']=='answer',
        declared_abstention=declared,malformed=not valid,strict_correct=decoded==task['expected'])


def summary(rows):
    arms=[]
    for arm in ARMS:
        group=[r for r in rows if r['arm']==arm];n=len(group)
        counts={k:sum(r['score'][k] for r in group) for k in ('valid_parsed_answer','declared_abstention','malformed','strict_correct')}
        arms.append(dict(arm=arm,count=n,length_terminated=sum(r['response']['finish_reason']=='length' for r in group),**counts,valid_parsed_answer_rate=counts['valid_parsed_answer']/n if n else None,
            accuracy=counts['strict_correct']/n if n else None,prompt_tokens=[r['response']['usage']['prompt_tokens'] for r in group]))
    original=next(a for a in arms if a['arm']=='original')
    ceiling=original['count']==10 and original['declared_abstention']>=9
    return dict(arms=arms,verdict='1.5B model is the ceiling' if ceiling else 'calibration_complete_requires_review',
        operational_blocker=ceiling,scope='Operational label for this registered local model/interface calibration only; not a universal capability claim.',
        limitation='Original JSON vs compact triplet bundles prompt and serialization changes; forced vs compact changes only abstention instruction.',
        holdout_next_action='stop_no_holdout',promotion_authorized=False)


def partial_summary(rows):
    return dict(arms=[a for a in summary(rows[:20])['arms'] if a['arm']!='original'],
        status='partial_calibration',infrastructure_finding='original prompt infeasible on this substrate',
        scope='Observed socket timeout on this local substrate and registered original interface only.',
        completed_conditions=['compact','forced_answer'],original_completed=sum(r['arm']=='original' for r in rows),
        promotion_authorized=False,efficacy_established=False,holdout_next_action='stop_no_holdout')


def _paths(directory,journal,bank_directory):
    root,ledger,bank=[Path(p).resolve() for p in (directory,journal,bank_directory)]
    if len({root,ledger,bank})!=3 or root in bank.parents or bank in root.parents or root in ledger.parents or bank in ledger.parents:
        raise ValueError('separate_external_calibration_paths_required')
    return root,ledger,bank


def _protocol(root,journal,bank,manifest,digest,predecessor_directory,predecessor_journal):
    if any(type(v) is not str or not re.fullmatch('[0-9a-f]{64}',v) for v in (manifest,digest)):raise ValueError('full_identity_pins_required')
    oldpaths=[Path(predecessor_directory).resolve(),Path(predecessor_journal).resolve()]
    if any(a==b or a in b.parents or b in a.parents for a in (root,journal) for b in oldpaths):raise ValueError('predecessor_paths_must_be_separate')
    previous=predecessor.validate_receipt(predecessor_directory,digest,predecessor_journal,bank_directory=bank,bank_manifest_sha256=manifest)
    if previous['status']!='failed_consumed':raise ValueError('failed_v1_calibration_required')
    tasks=previous['protocol']['tasks']
    if len(tasks)!=10 or previous['protocol']['seed']!=SEED:raise ValueError('same_v1_tasks_seed_required')
    prompts=[dict(task_id=t['task_id'],arm=a,prepared=transport.prepare(a,t['query'],t['evidence'])) for t in tasks for a in ARMS]
    protocol=dict(version=VERSION,directory=str(root),journal=str(journal),bank_directory=str(bank),manifest_sha256=manifest,
        expected_digest=digest,model=pilot.MODEL,origin=pilot.ORIGIN,source_sha256=sources(),tasks=tasks,
        development_sha256=sha256(bank_module._read(bank/'dev.json',8000000)).hexdigest(),
        roster_sha256=_hash(tasks),schedule=schedule(tasks),prompts=prompts,seed=SEED,max_model_calls=30,
        max_wall_seconds=MAX_SECONDS,max_output_tokens=128,requested_model_seed=SEED,
        development_reuse_allowed=True,holdout_accessed=False,
        original_prompt='Exact existing candidate execution system plus candidate transport evidence JSON; actual tokens measured, not guaranteed 490.',
        scoring='Strict original six-field JSON or compact triplet; raw declared abstain counted independently of validity; no repairs.',
        stop_rule='Original declared abstention >=9 of10 labels operational 1.5B ceiling. Only an original socket timeout with full240-second allowance after20 completed calls permits partial completed-condition reporting; all other failures have no verdict. Stop without holdout.',
        predecessor_directory=str(Path(predecessor_directory).resolve()),predecessor_journal=str(Path(predecessor_journal).resolve()),
        predecessor_receipt_sha256=_hash(previous),socket_timeout_seconds=240,condition_order=['compact','forced_answer','original'],
        justification={'user_report':'User reports original calls taking 35–70 seconds the prior night.',
            'recorded_prior_seconds':[71.44543347001309,43.651547938003205],'recorded_source':'docs/galahad/evidence/scientific-candidate-format-study-v1.json',
            'v1_failure':previous.get('failure'),'v1_timeout_seconds':90,
            'budget_reason':'Thirty 70-second calls already require 2100 seconds; 3600 seconds permits overhead, 240 seconds gives per-call headroom without guaranteeing completion.'})
    if canonical(prompts)!=canonical(previous['protocol']['prompts']):raise ValueError('v1_prompts_changed')
    return protocol


def _external(journal,protocol,allowed):
    smoke._private(journal)
    with sqlite3.connect(journal.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT protocol,status FROM substrate_claims WHERE version=?',(VERSION,)).fetchone()
    if row is None or row[0]!=canonical(protocol) or row[1] not in allowed:raise ValueError('shared_calibration_claim_changed')


def _save(db,report):
    raw=canonical(report);db.execute('UPDATE calibration SET report=?,digest=? WHERE id=1',(raw,sha256(raw.encode()).hexdigest()));db.commit()


def register(directory,expected_digest,journal,*,bank_directory,bank_manifest_sha256,predecessor_directory,predecessor_journal):
    root,ledger,bank=_paths(directory,journal,bank_directory)
    protocol=_protocol(root,ledger,bank,bank_manifest_sha256,expected_digest,predecessor_directory,predecessor_journal)
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_calibration_required')
    with _exclusive(root):
        path=root/'claim.sqlite'
        if not path.exists():
            if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('missing_calibration_claim_consumed')
            if not ledger.exists():
                fd=os.open(ledger,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
                with sqlite3.connect(ledger) as db:db.execute('CREATE TABLE substrate_claims(version TEXT PRIMARY KEY,protocol TEXT,status TEXT)')
            smoke._private(ledger)
            with sqlite3.connect(ledger) as db:db.execute('INSERT INTO substrate_claims VALUES(?,?,?)',(VERSION,canonical(protocol),'registered'))
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE calibration(id INTEGER PRIMARY KEY CHECK(id=1),protocol TEXT,status TEXT,report TEXT,digest TEXT)')
                db.execute('CREATE TABLE calls(ordinal INTEGER PRIMARY KEY,task TEXT,arm TEXT,status TEXT)')
                db.execute('INSERT INTO calibration VALUES(1,?,?,NULL,NULL)',(canonical(protocol),'registered'))
        smoke._private(path);_external(ledger,protocol,('registered','consumed'))
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('calibration_claim_corrupt')
            rows=db.execute('SELECT protocol FROM calibration').fetchall()
        if rows!=[(canonical(protocol),)]:raise ValueError('frozen_calibration_protocol_changed')
        smoke._save_exact(root/'preregistration.json',protocol)
    return protocol


def _validate(db,report,protocol):
    if (canonical(report['protocol'])!=canonical(protocol) or report['status'] not in ('complete','failed_consumed')
            or any(type(report[k]) is not int or not 0<=report[k]<=v for k,v in [('model_attempts',30),('metadata_attempts',2),('version_attempts',2),('preload_attempts',1)])
            or any(report[k] is not False for k in ('holdout_accessed','promotion_authorized','efficacy_established','model_weights_trained'))):raise ValueError('invalid_calibration_receipt')
    tasks={t['task_id']:t for t in protocol['tasks']};order=protocol['schedule'];rows=report['rows']
    if type(rows) is not list or not len(rows)<=report['model_attempts']<=len(rows)+1:raise ValueError('calibration_attempt_count_changed')
    for i,row in enumerate(rows):
        tid,arm=order[i];response=row['response'];usage=response['usage'];prepared=transport.prepare(arm,tasks[tid]['query'],tasks[tid]['evidence'])
        if (row['task_id']!=tid or row['arm']!=arm or canonical(row['score'])!=canonical(score(response['raw_output'],arm,tasks[tid]))
                or type(response['raw_output']) is not str or not 1<=len(response['raw_output'])<=16384
                or response['model']!=pilot.MODEL or response['origin']!=pilot.ORIGIN or response['input_sha256']!=prepared['input_sha256']
                or type(response['model_calls']) is not int or response['model_calls']!=1
                or type(response['model_sampling_seed']) is not int or response['model_sampling_seed']!=SEED
                or response['review_required'] is not True or response['synthetic_only'] is not True
                or response['finish_reason'] not in ('stop','length') or type(usage) is not dict
                or set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
                or any(type(v) is not int or not 0<=v<=10000000 for v in usage.values())
                or usage['completion_tokens']>128 or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']
                or type(row['elapsed_seconds']) not in (int,float) or not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds']<0):raise ValueError('calibration_row_changed')
    expected=[(i,*order[i],'complete' if i<len(rows) else 'claimed') for i in range(report['model_attempts'])]
    if db.execute('SELECT ordinal,task,arm,status FROM calls ORDER BY ordinal').fetchall()!=expected:raise ValueError('calibration_call_claims_changed')
    if report['model_attempts'] and (report.get('metadata_before')!={'model':pilot.MODEL,'digest':protocol['expected_digest']}
            or report['metadata_attempts']<1 or report['version_attempts']<1 or report['preload_attempts']!=1
            or type(report.get('version_before')) is not str or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before'])
            or not _preload_valid(report.get('preload'))):raise ValueError('predispatch_provenance_changed')
    if report['status']=='complete':
        identity={'model':pilot.MODEL,'digest':protocol['expected_digest']}
        if (len(rows)!=30 or (report['model_attempts'],report['metadata_attempts'],report['version_attempts'],report['preload_attempts'])!=(30,2,2,1)
                or report['metadata_before']!=identity or report['metadata_after']!=identity
                or report['version_after']!=report['version_before'] or type(report['version_before']) is not str
                or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before'])
                or canonical(report['summary'])!=canonical(summary(rows))
                or type(report['wall_seconds']) not in (int,float) or not 0<=report['wall_seconds']<=3600):raise ValueError('incomplete_calibration_receipt')
    elif ('summary' in report or type(report.get('failure')) is not str or not re.fullmatch('[A-Za-z0-9_]{1,80}',report['failure'])):
        raise ValueError('failed_calibration_receipt_invalid')
    if 'unscored_raw_response' in report:
        raw=report['unscored_raw_response']
        if (report['status']!='failed_consumed' or 'partial_calibration' in report or report['model_attempts']!=len(rows)+1
                or type(raw) is not dict or set(raw)!={'raw_output','finish_reason','usage','reason'}
                or raw['reason']!='post_response_authorization_failed' or type(raw['raw_output']) is not str or not 1<=len(raw['raw_output'])<=16384
                or raw['finish_reason'] not in ('stop','length') or type(raw['usage']) is not dict
                or set(raw['usage'])!={'prompt_tokens','completion_tokens','total_tokens'}
                or any(type(v) is not int or not 0<=v<=10000000 for v in raw['usage'].values())
                or raw['usage']['completion_tokens']>128 or raw['usage']['total_tokens']!=raw['usage']['prompt_tokens']+raw['usage']['completion_tokens']):raise ValueError('invalid_unscored_response')
    if 'partial_calibration' in report:
        identity={'model':pilot.MODEL,'digest':protocol['expected_digest']}
        if (report['status']!='failed_consumed' or report.get('failure')!='TransportTimeout'
                or not 20<=len(rows)<30 or report['model_attempts']!=len(rows)+1
                or report.get('timed_out_arm')!='original' or type(report.get('request_timeout_seconds')) is not int or report['request_timeout_seconds']!=240
                or report.get('metadata_after')!=identity or report.get('version_after')!=report.get('version_before')
                or report['metadata_attempts']!=2 or report['version_attempts']!=2
                or canonical(report['partial_calibration'])!=canonical(partial_summary(rows))):raise ValueError('invalid_partial_calibration')
    elif 'timed_out_arm' in report or 'request_timeout_seconds' in report:raise ValueError('unexpected_timeout_finding')
    _external(Path(protocol['journal']),protocol,('consumed',))


def validate_receipt(directory,expected_digest,journal,*,bank_directory,bank_manifest_sha256,predecessor_directory,predecessor_journal):
    root,ledger,bank=_paths(directory,journal,bank_directory)
    path=root/'claim.sqlite';smoke._private(path)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_calibration_required')
    protocol=_protocol(root,ledger,bank,bank_manifest_sha256,expected_digest,predecessor_directory,predecessor_journal)
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('calibration_claim_corrupt')
        old=db.execute('SELECT protocol,status,report,digest FROM calibration WHERE id=1').fetchone()
        if old is None or old[0]!=canonical(protocol) or old[1] not in ('complete','failed_consumed') or old[2] is None or sha256(old[2].encode()).hexdigest()!=old[3]:raise ValueError('existing_terminal_calibration_required')
        report=json.loads(old[2])
        if report['status']!=old[1]:raise ValueError('terminal_status_changed')
        _validate(db,report,protocol)
    for name,value in (('preregistration.json',protocol),('report.json',report)):
        target=root/name;smoke._private(target)
        with target.open('rb') as stream:raw=stream.read(4000001)
        if raw!=(canonical(value)+'\n').encode():raise ValueError('published_calibration_changed')
    if canonical(_protocol(root,ledger,bank,bank_manifest_sha256,expected_digest,predecessor_directory,predecessor_journal))!=canonical(protocol):raise ValueError('calibration_inputs_changed')
    _external(ledger,protocol,('consumed',))
    return report


def run(directory,expected_digest,journal,*,bank_directory,bank_manifest_sha256,predecessor_directory,predecessor_journal):
    protocol=register(directory,expected_digest,journal,bank_directory=bank_directory,bank_manifest_sha256=bank_manifest_sha256,predecessor_directory=predecessor_directory,predecessor_journal=predecessor_journal)
    root=Path(protocol['directory']);ledger=Path(protocol['journal']);path=root/'claim.sqlite'
    with _exclusive(root),sqlite3.connect(path) as db:
        old=db.execute('SELECT status,report,digest FROM calibration WHERE id=1').fetchone()
        if old[0]!='registered':
            if old[1] is None or sha256(old[1].encode()).hexdigest()!=old[2]:raise ValueError('interrupted_or_corrupt_calibration_consumed')
            report=json.loads(old[1])
            if report['status']=='running':report['status']='failed_consumed';report['failure']='interrupted_consumed'
            _validate(db,report,protocol)
            if old[0]=='running':db.execute("UPDATE calibration SET status='failed_consumed'");_save(db,report)
            smoke._save_exact(root/'report.json',report);return report
        with sqlite3.connect(ledger) as external:
            external.execute('BEGIN IMMEDIATE');_external(ledger,protocol,('registered',))
            external.execute("UPDATE substrate_claims SET status='consumed' WHERE version=?",(VERSION,))
        db.execute("UPDATE calibration SET status='running' WHERE id=1");db.commit()
        report=dict(protocol=protocol,status='running',rows=[],model_attempts=0,metadata_attempts=0,version_attempts=0,preload_attempts=0,
                    holdout_accessed=False,promotion_authorized=False,efficacy_established=False,model_weights_trained=False)
        _save(db,report);started=time.monotonic();deadline=started+MAX_SECONDS;interrupt=None;arm=None;remaining=0
        try:
            gateway,_,proposer,reviewer,reader=pilot._state(root/'authority.sqlite');tasks={t['task_id']:t for t in protocol['tasks']};snapshots={};scopes={}
            for index,task in enumerate(protocol['tasks']):
                scope=MemoryScope('synthetic-science','model-research','substrate-'+str(index));scopes[task['task_id']]=scope
                for fact in task['evidence']:
                    mid=gateway.propose(proposer,scope=scope,content=fact['content'],source_id=fact['source_id']);gateway.decide(reviewer,mid,scope=scope,approve=True,evaluator_id=VERSION)
                snapshots[task['task_id']]=gateway.retrieve(reader,MemoryRequest(scope,task['query'],limit=20))
            def authorize(task):
                current=gateway.retrieve(reader,MemoryRequest(scopes[task['task_id']],task['query'],limit=20));initial=snapshots[task['task_id']]
                if current.records!=initial.records or current.source_digest!=initial.source_digest or sorted((r.source_id,r.content) for r in current.records)!=sorted((r['source_id'],r['content']) for r in task['evidence']):raise PermissionError('calibration_evidence_changed')
                if (sources()!=protocol['source_sha256'] or sha256(bank_module._read(Path(bank_directory)/'dev.json',8000000)).hexdigest()!=protocol['development_sha256']
                        or sha256(bank_module._read(Path(bank_directory)/'manifest.json',100000)).hexdigest()!=bank_manifest_sha256):raise ValueError('calibration_sources_changed')
                if time.monotonic()>=deadline:raise TimeoutError('calibration_wall_budget')
            report['metadata_attempts']=1;_save(db,report);report['metadata_before']=metadata()
            if report['metadata_before']!={'model':pilot.MODEL,'digest':expected_digest}:raise ValueError('model_digest_mismatch')
            report['version_attempts']=1;_save(db,report);report['version_before']=runtime_version()
            if type(report['version_before']) is not str or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before']):raise ValueError('runtime_version_required')
            report['preload_attempts']=1;_save(db,report);report['preload']=preload()
            if not _preload_valid(report['preload']):raise ValueError('valid_preload_required')
            for index,(task_id,arm) in enumerate(protocol['schedule']):
                task=tasks[task_id];authorize(task)
                remaining=deadline-time.monotonic()
                if remaining<1:raise TimeoutError('calibration_wall_budget')
                db.execute('INSERT INTO calls VALUES(?,?,?,?)',(index,task_id,arm,'claimed'));report['model_attempts']+=1;_save(db,report)
                prepared=transport.prepare(arm,task['query'],task['evidence']);start=time.perf_counter()
                response=transport.run(prepared,authorize=lambda:authorize(task),timeout_seconds=min(240,remaining))
                row=dict(task_id=task_id,arm=arm,response=response,elapsed_seconds=time.perf_counter()-start,score=score(response['raw_output'],arm,task))
                report['rows'].append(row);db.execute("UPDATE calls SET status='complete' WHERE ordinal=?",(index,));_save(db,report)
            report['metadata_attempts']=2;_save(db,report);report['metadata_after']=metadata()
            report['version_attempts']=2;_save(db,report);report['version_after']=runtime_version()
            if canonical(selected(bank_directory,bank_manifest_sha256))!=canonical(protocol['tasks']):raise ValueError('development_changed')
            for task in tasks.values():authorize(task)
            report['wall_seconds']=time.monotonic()-started;report['summary']=summary(report['rows']);report['status']='complete';_validate(db,report,protocol)
        except BaseException as error:
            report['status']='failed_consumed';report['failure']=type(error).__name__;report.pop('summary',None);report['wall_seconds']=time.monotonic()-started
            if hasattr(error,'unscored_raw_response'):report['unscored_raw_response']=error.unscored_raw_response
            if isinstance(error,transport.TransportTimeout) and arm=='original' and 20<=len(report['rows'])<30 and remaining>=240:
                try:
                    report['metadata_attempts']=2;_save(db,report);report['metadata_after']=metadata()
                    report['version_attempts']=2;_save(db,report);report['version_after']=runtime_version()
                    if report['metadata_after']!={'model':pilot.MODEL,'digest':expected_digest} or report['version_after']!=report['version_before']:raise ValueError('post_timeout_identity_mismatch')
                    report['partial_calibration']=partial_summary(report['rows']);report['timed_out_arm']='original';report['request_timeout_seconds']=240
                except Exception as check_error:report['post_timeout_check_failure']=type(check_error).__name__
            if not isinstance(error,Exception):interrupt=error
        _validate(db,report,protocol);db.execute('UPDATE calibration SET status=? WHERE id=1',(report['status'],));_save(db,report)
        if canonical(_protocol(root,ledger,Path(protocol['bank_directory']),bank_manifest_sha256,expected_digest,predecessor_directory,predecessor_journal))!=canonical(protocol):raise ValueError('calibration_inputs_changed')
        smoke._save_exact(root/'report.json',report)
        if interrupt is not None:raise interrupt
        return report
