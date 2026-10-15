"""Four durably claimed calls on two fresh tasks: format capability only."""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

from . import scientific_candidate_transport_smoke as smoke
from . import scientific_candidate_transport as transport
from . import scientific_candidate_execution as execution
from . import scientific_candidates as candidates
from .scientific_structured_tasks import parse,parse_shape
from .contracts import MemoryRequest,MemoryScope
from .research_supervisor import _exclusive

pilot=smoke.pilot
metadata,preload,runtime_version=smoke.metadata,smoke.preload,smoke.runtime_version
canonical,_hash=pilot._json,pilot._hash
VERSION='scientific-candidate-format-study-v1'
PAIRS=(('supported',True),('supported',False),('unit_mismatch',False),('unit_mismatch',True))


def tasks():
    def evidence(entity,value,unit,source):
        row=dict(content=f'Sample {entity} has mass {value} {unit}.',source_id=source,
                 version=1,current=True,timestamp='2026-01-01T00:00:00Z')
        return dict(row,content_sha256=_hash(row))
    return {'supported':dict(query="What is sample N2233445566778899's mass in mg?",evidence=[
        evidence('N2233445566778899','41.7','mg','format-probe-a'),evidence('N9988776655443322','43.2','mg','format-probe-b')],
        expected=dict(status='answer',entity='N2233445566778899',measurement='mass',value='41.7',unit='mg',source_id='format-probe-a')),
        'unit_mismatch':dict(query="What is sample N33445566778899aa's mass in mg?",evidence=[
        evidence('N33445566778899aa','1.8','g','format-probe-c')],expected=dict(execution.ABSTAIN))}


def sources():
    pins=smoke.sources()
    for path in ('src/nerve_awim/memory_gateway/scientific_candidate_format_study.py','scripts/run_scientific_candidate_format_study.py'):
        pins[path]=sha256((pilot.ROOT/path).read_bytes()).hexdigest()
    return pins


def score(raw,task_id):
    expected=tasks()[task_id]['expected']
    try:parse_shape(raw);schema=True
    except ValueError:schema=False
    try:parsed=parse(raw);formatted=True
    except ValueError:parsed=None;formatted=False
    return dict(schema_valid=schema,format_valid=formatted,strict_correct=parsed==expected)


def _summary(rows):
    return {'arms':[dict(constrained=flag,calls=sum(r['constrained'] is flag for r in rows),
        **{metric:sum(r['score'][metric] for r in rows if r['constrained'] is flag) for metric in ('schema_valid','format_valid','strict_correct')})
        for flag in (False,True)],'interpretation':'Two paired tasks; format capability probe only, not powered efficacy.'}


def _scope(task_id):return MemoryScope('synthetic-science','model-research','candidate-format-'+task_id)


def _save(db,report,claim=None,complete=None):
    encoded=canonical(report)
    if claim is not None:
        task,constrained=PAIRS[claim]
        db.execute('INSERT INTO calls VALUES(?,?,?,?)',(claim,task,int(constrained),'claimed'))
    if complete is not None:db.execute("UPDATE calls SET status='complete' WHERE ordinal=? AND status='claimed'",(complete,))
    db.execute('UPDATE study SET report=?,digest=? WHERE id=1',(encoded,sha256(encoded.encode()).hexdigest()));db.commit()


def _external(journal,protocol):
    smoke._private(journal)
    with sqlite3.connect(journal.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('external_claim_corrupt')
        row=db.execute('SELECT protocol,status FROM format_claims WHERE dataset=?',(protocol['dataset_sha256'],)).fetchone()
        if row!=(canonical(protocol),'consumed'):raise ValueError('external_claim_changed')


def _claim(journal,protocol,root):
    if not journal.exists():
        if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('external_claim_missing')
        fd=os.open(journal,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        with sqlite3.connect(journal) as db:
            db.execute('CREATE TABLE format_claims(dataset TEXT PRIMARY KEY,version TEXT UNIQUE,protocol TEXT,status TEXT)')
    smoke._private(journal)
    with sqlite3.connect(journal) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO format_claims VALUES(?,?,?,?)',(protocol['dataset_sha256'],VERSION,canonical(protocol),'consumed'))


def _check_row(row,protocol,index):
    task_id,flag=PAIRS[index];task=tasks()[task_id]
    if (row['task_id']!=task_id or row['constrained'] is not flag
            or row['arm_config_sha256']!=protocol['arm_config_sha256'][str(flag)]):raise ValueError('paired_row_order_changed')
    response=row['response'];usage=response['usage'];prepared=execution.prepare(protocol['config'],task['query'],task['evidence'])
    if (response['route']!='model' or type(response['model_calls']) is not int or response['model_calls']!=1
            or response['model']!=pilot.MODEL or response['origin']!=pilot.ORIGIN or response['constrained'] is not flag
            or response['review_required'] is not True or response['synthetic_only'] is not True or response['model_weights_trained'] is not False
            or any(canonical(response[key])!=canonical(prepared[key]) for key in ('config_sha256','input_sha256','evidence_ids','scanned_current_ids'))
            or type(response['raw_output']) is not str or not 1<=len(response['raw_output'])<=16384
            or canonical(row['score'])!=canonical(score(response['raw_output'],task_id))
            or type(usage) is not dict or set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
            or any(type(v) is not int or not 0<=v<=10000000 for v in usage.values())
            or usage['completion_tokens']>128 or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']
            or type(row['elapsed_seconds']) not in (int,float) or not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds']<0):
        raise ValueError('invalid_measured_format_row')


def _validate(db,report,protocol):
    if (canonical(report['protocol'])!=canonical(protocol) or report['status'] not in ('complete','failed_consumed')
            or type(report['rows']) is not list or len(report['rows'])>4
            or any(type(report[k]) is not int or not 0<=report[k]<=bound for k,bound in
                [('model_attempts',4),('metadata_attempts',2),('version_attempts',2),('preload_attempts',1)])
            or any(report[k] is not False for k in ('promotion_authorized','model_weights_trained','efficacy_established'))
            or type(report['rejection_receipts_created']) is not int or report['rejection_receipts_created']!=0
            or not len(report['rows'])<=report['model_attempts']<=len(report['rows'])+1):raise ValueError('invalid_terminal_format_receipt')
    if report['status']=='failed_consumed' and (type(report.get('failure')) is not str or not re.fullmatch('[A-Za-z0-9_]{1,80}',report['failure'])):
        raise ValueError('failure_evidence_required')
    if 'failure_reason' in report or 'failure_detail' in report:
        transport.InferenceUnavailable(report['failure_reason'],report['failure_detail'])
    if report['model_attempts']:
        if (report['metadata_attempts']<1 or report['version_attempts']<1 or report['preload_attempts']!=1
                or report.get('metadata_before')!={'model':pilot.MODEL,'digest':protocol['expected_digest']}
                or type(report.get('version_before')) is not str or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before'])):
            raise ValueError('predispatch_identity_evidence_changed')
    claims=db.execute('SELECT ordinal,task,constrained,status FROM calls ORDER BY ordinal').fetchall()
    expected=[(i,*PAIRS[i][0:1],int(PAIRS[i][1]),'complete' if i<len(report['rows']) else 'claimed') for i in range(report['model_attempts'])]
    if claims!=expected:raise ValueError('attempt_claims_changed')
    for i,row in enumerate(report['rows']):_check_row(row,protocol,i)
    if report['status']=='complete':
        identity={'model':pilot.MODEL,'digest':protocol['expected_digest']}
        if ((report['model_attempts'],report['metadata_attempts'],report['version_attempts'],report['preload_attempts'])!=(4,2,2,1)
                or len(report['rows'])!=4 or report['metadata_before']!=identity or report['metadata_after']!=identity
                or type(report['version_before']) is not str or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before'])
                or report['version_after']!=report['version_before'] or canonical(report['summary'])!=canonical(_summary(report['rows']))):
            raise ValueError('invalid_complete_format_receipt')
    _external(Path(protocol['journal']),protocol)


def _run(directory,expected_digest,journal,resume_only):
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}',expected_digest):raise ValueError('full_model_digest_required')
    root=Path(directory).resolve();journal=Path(journal).resolve()
    if resume_only and not (root/'claim.sqlite').is_file():raise ValueError('existing_terminal_receipt_required')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_study_directory_required')
    if journal==root or root in journal.parents:raise ValueError('external_journal_required')
    pins=sources();bank=tasks();config=dict(candidates.SPACE['conflict_check'])
    protocol=dict(version=VERSION,directory=str(root),journal=str(journal),model=pilot.MODEL,origin=pilot.ORIGIN,
        expected_digest=expected_digest,source_sha256=pins,config=config,tasks=bank,pairs=PAIRS,dataset_sha256=_hash(bank),
        arm_config_sha256={str(flag):_hash({'base_candidate_config':config,'constrained':flag,'model_digest':expected_digest}) for flag in (False,True)},
        max_model_calls=4,max_metadata_calls=2,max_version_calls=2,max_preload_calls=1,max_output_tokens=128,socket_timeout_seconds=90)
    path=root/'claim.sqlite'
    with _exclusive(root):
        created=not path.exists()
        if created:
            if resume_only:raise ValueError('existing_terminal_receipt_required')
            if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('missing_claim_consumed')
            _claim(journal,protocol,root)
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE study(id INTEGER PRIMARY KEY CHECK(id=1),protocol TEXT,report TEXT,digest TEXT)')
                db.execute('CREATE TABLE calls(ordinal INTEGER PRIMARY KEY,task TEXT,constrained INTEGER,status TEXT)')
                db.execute('INSERT INTO study VALUES(1,?,NULL,NULL)',(canonical(protocol),))
        smoke._private(path);_external(journal,protocol)
        with sqlite3.connect(path) as db:
            if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('local_claim_corrupt')
            old=db.execute('SELECT protocol,report,digest FROM study WHERE id=1').fetchone()
            if old is None or old[0]!=canonical(protocol):raise ValueError('claim_protocol_changed')
            if not created:
                if old[1] is None:raise ValueError('incomplete_claim_consumed')
                if sha256(old[1].encode()).hexdigest()!=old[2]:raise ValueError('receipt_hash_changed')
                report=json.loads(old[1])
                if report['status']=='running':
                    report['status']='failed_consumed';report['failure']='interrupted_consumed';_validate(db,report,protocol);_save(db,report)
                _validate(db,report,protocol)
                if sources()!=pins:raise ValueError('source_code_changed')
                smoke._save_exact(root/'report.json',report)
                return report
            report=dict(protocol=protocol,status='running',rows=[],model_attempts=0,metadata_attempts=0,version_attempts=0,
                preload_attempts=0,promotion_authorized=False,model_weights_trained=False,efficacy_established=False,rejection_receipts_created=0)
            _save(db,report);interrupt=None
            try:
                gateway,_,proposer,reviewer,reader=pilot._state(root/'authority.sqlite')
                for task_id,task in bank.items():
                    for fact in task['evidence']:
                        mid=gateway.propose(proposer,scope=_scope(task_id),content=fact['content'],source_id=fact['source_id'])
                        gateway.decide(reviewer,mid,scope=_scope(task_id),approve=True,evaluator_id=VERSION)
                snapshots={task:gateway.retrieve(reader,MemoryRequest(_scope(task),bank[task]['query'],limit=20)) for task in bank}
                def authorize(task_id):
                    current=gateway.retrieve(reader,MemoryRequest(_scope(task_id),bank[task_id]['query'],limit=20))
                    if (current.records!=snapshots[task_id].records or current.source_digest!=snapshots[task_id].source_digest
                            or sorted((r.content,r.source_id) for r in current.records)!=sorted((r['content'],r['source_id']) for r in bank[task_id]['evidence'])):
                        raise PermissionError('approved_evidence_changed')
                    if sources()!=pins:raise ValueError('source_code_changed')
                report['metadata_attempts']=1;_save(db,report);report['metadata_before']=metadata()
                if report['metadata_before']!={'model':pilot.MODEL,'digest':expected_digest}:raise ValueError('model_digest_mismatch')
                report['version_attempts']=1;_save(db,report);report['version_before']=runtime_version()
                if type(report['version_before']) is not str or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before']):raise ValueError('runtime_version_required')
                report['preload_attempts']=1;_save(db,report);report['preload']=preload()
                for index,(task_id,flag) in enumerate(PAIRS):
                    authorize(task_id);task=bank[task_id]
                    if execution.prepare(config,task['query'],task['evidence'])['route']!='model':raise ValueError('model_route_required')
                    report['model_attempts']+=1;_save(db,report,claim=index);start=time.perf_counter()
                    response=transport.run(config,task['query'],task['evidence'],authorize=lambda:authorize(task_id),constrained=flag)
                    row=dict(task_id=task_id,constrained=flag,arm_config_sha256=protocol['arm_config_sha256'][str(flag)],response=response,score=score(response['raw_output'],task_id),elapsed_seconds=time.perf_counter()-start)
                    _check_row(row,protocol,index);authorize(task_id)
                    report['rows'].append(row);_save(db,report,complete=index)
                report['metadata_attempts']=2;_save(db,report);report['metadata_after']=metadata()
                report['version_attempts']=2;_save(db,report);report['version_after']=runtime_version()
                for task in bank:authorize(task)
                report['summary']=_summary(report['rows']);report['status']='complete';_validate(db,report,protocol)
            except BaseException as error:
                report['status']='failed_consumed';report['failure']=type(error).__name__
                if isinstance(error,transport.InferenceUnavailable):
                    report['failure_reason']=error.reason;report['failure_detail']=error.detail
                if not isinstance(error,Exception):interrupt=error
            _validate(db,report,protocol);_save(db,report);smoke._save_exact(root/'report.json',report)
            if interrupt is not None:raise interrupt
            return report


def run(directory,expected_digest,journal):return _run(directory,expected_digest,journal,False)
def validate_receipt(directory,expected_digest,journal):return _run(directory,expected_digest,journal,True)
