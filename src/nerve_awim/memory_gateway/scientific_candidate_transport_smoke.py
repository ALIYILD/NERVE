"""One durably consumed local transport probe; never an efficacy experiment."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import math
import sqlite3
import stat
import time

from . import scientific_structured_preflight as previous
from . import scientific_candidate_transport as transport
from . import scientific_candidate_execution as execution
from . import scientific_candidates as candidates
from .scientific_episode_import import _save_exact, canonical
from .scientific_structured_tasks import parse_shape, parse
from .contracts import MemoryScope, MemoryRequest
from .research_supervisor import _exclusive

pilot=previous.pilot
metadata,preload,runtime_version=pilot.metadata,pilot.preload,previous.runtime_version
VERSION='scientific-candidate-transport-smoke-v1'
QUERY="What is sample N1122334455667788's mass in mg?"
EXPECTED=dict(status='answer',entity='N1122334455667788',measurement='mass',value='32.6',unit='mg',source_id='smoke-candidate-a')
SCOPE=MemoryScope('synthetic-science','model-research','candidate-transport-smoke')


def evidence():
    rows=[]
    for entity,value,source in [('N1122334455667788','32.6','smoke-candidate-a'),('N8877665544332211','34.8','smoke-candidate-b')]:
        row=dict(content=f'Sample {entity} has mass {value} mg.',source_id=source,version=1,current=True,timestamp='2026-01-01T00:00:00Z')
        rows.append(dict(row,content_sha256=pilot._hash(row)))
    return rows


def sources():
    pins=previous.sources()
    for name in ('scientific_candidates.py','scientific_candidate_execution.py','scientific_candidate_transport.py',
                 'scientific_candidate_transport_smoke.py','scientific_episode_import.py','experience_store.py'):
        path='src/nerve_awim/memory_gateway/'+name;pins[path]=sha256((pilot.ROOT/path).read_bytes()).hexdigest()
    path='scripts/smoke_scientific_candidate_transport.py';pins[path]=sha256((pilot.ROOT/path).read_bytes()).hexdigest()
    return pins


def score(raw):
    try:parse_shape(raw);schema=True
    except ValueError:schema=False
    try:parsed=parse(raw);formatted=True
    except ValueError:parsed=None;formatted=False
    return dict(schema_valid=schema,format_valid=formatted,strict_correct=parsed==EXPECTED,
                interpretation='One synthetic transport probe only; no efficacy estimate.')


def _save(db, report):
    encoded=canonical(report)
    db.execute('UPDATE attempt SET report=?,digest=? WHERE id=1',(encoded,sha256(encoded.encode()).hexdigest()))
    db.commit()


def _private(path):
    mode=path.lstat()
    if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode)!=0o600:
        raise ValueError('private_regular_claim_required')


def _validate_common(report,protocol):
    if (canonical(report['protocol'])!=canonical(protocol)
            or report['status'] not in ('complete','failed_consumed')
            or any(type(report[k]) is not int or not 0<=report[k]<=bound for k,bound in
                [('model_attempts',1),('metadata_attempts',2),('version_attempts',2),('preload_attempts',1)])
            or any(report[k] is not False for k in ('promotion_authorized','model_weights_trained','efficacy_established'))
            or type(report['rejection_receipts_created']) is not int or report['rejection_receipts_created']!=0):
        raise ValueError('invalid_terminal_smoke_receipt')


def _verify_external(journal,protocol):
    _private(journal)
    with sqlite3.connect(journal.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('external_claim_corrupt')
        row=db.execute('SELECT protocol,status FROM smoke_claims WHERE version=?',(VERSION,)).fetchone()
        if row!=(canonical(protocol),'consumed'):raise ValueError('external_claim_changed')


def _validate_complete(report,protocol):
    response=report['response'];usage=response['usage']
    prepared=execution.prepare(protocol['config'],protocol['query'],protocol['evidence'])
    expected_metadata={'model':pilot.MODEL,'digest':protocol['expected_digest']}
    if (report['status']!='complete' or canonical(report['protocol'])!=canonical(protocol)
            or any(type(report[k]) is not int or report[k]!=v for k,v in
                [('model_attempts',1),('metadata_attempts',2),('version_attempts',2),('preload_attempts',1)])
            or report['metadata_before']!=expected_metadata or report['metadata_after']!=expected_metadata
            or type(report['version_before']) is not str or not re.fullmatch(r'[A-Za-z0-9._+-]{1,80}',report['version_before'])
            or report['version_after']!=report['version_before']
            or any(report[k] is not False for k in ('promotion_authorized','model_weights_trained','efficacy_established'))
            or type(report['rejection_receipts_created']) is not int or report['rejection_receipts_created']!=0
            or response['route']!='model' or type(response['model_calls']) is not int or response['model_calls']!=1
            or response['model']!=pilot.MODEL or response['origin']!=pilot.ORIGIN
            or response['constrained'] is not False or response['review_required'] is not True
            or response['synthetic_only'] is not True or response['model_weights_trained'] is not False
            or any(canonical(response[k])!=canonical(prepared[k]) for k in ('config_sha256','input_sha256','evidence_ids','scanned_current_ids'))
            or type(usage) is not dict or set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
            or any(type(v) is not int or not 0<=v<=10000000 for v in usage.values())
            or usage['completion_tokens']>128 or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']
            or type(response['raw_output']) is not str or not 1<=len(response['raw_output'])<=16384
            or canonical(report['score'])!=canonical(score(response['raw_output']))
            or type(report['elapsed_seconds']) not in (int,float) or not math.isfinite(report['elapsed_seconds']) or report['elapsed_seconds']<0):
        raise ValueError('invalid_complete_smoke_receipt')


def _external_claim(journal,protocol,root):
    if not journal.exists():
        if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('external_claim_missing')
        fd=os.open(journal,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        with sqlite3.connect(journal) as db:
            db.execute('CREATE TABLE smoke_claims(version TEXT PRIMARY KEY,protocol TEXT,status TEXT)')
    _private(journal)
    with sqlite3.connect(journal) as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT protocol,status FROM smoke_claims WHERE version=?',(VERSION,)).fetchone()
        if old is None:
            if (root/'claim.sqlite').exists():raise ValueError('external_claim_missing')
            db.execute('INSERT INTO smoke_claims VALUES(?,?,?)',(VERSION,canonical(protocol),'consumed'))
            return True
        if old!=(canonical(protocol),'consumed'):raise ValueError('external_smoke_already_consumed')
        return False


def run(directory,expected_digest,journal):
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}',expected_digest):
        raise ValueError('full_model_digest_required')
    root=Path(directory).resolve();root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_smoke_directory_required')
    journal=Path(journal).resolve()
    if journal==root or root in journal.parents:raise ValueError('external_journal_required')
    pins=sources();config=dict(candidates.SPACE['conflict_check']);facts=evidence()
    protocol=dict(version=VERSION,directory=str(root),journal=str(journal),model=pilot.MODEL,origin=pilot.ORIGIN,
        expected_digest=expected_digest,source_sha256=pins,config=config,query=QUERY,evidence=facts,
        max_model_calls=1,max_metadata_calls=2,max_preload_calls=1,max_version_calls=2,
        timeout_seconds=90,max_output_tokens=128,constrained=False)
    with _exclusive(root):
        fresh_external=_external_claim(journal,protocol,root)
        path=root/'claim.sqlite';identity=root/'identity.json'
        created = not path.exists()
        if created:
            if not fresh_external:raise ValueError('missing_claim_consumed')
            if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('missing_claim_consumed')
            _save_exact(identity,protocol)
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE attempt(id INTEGER PRIMARY KEY CHECK(id=1),protocol TEXT,report TEXT,digest TEXT)')
                db.execute('INSERT INTO attempt VALUES(1,?,NULL,NULL)',(canonical(protocol),))
                db.commit()
        else:
            _private(path)
            if not identity.exists():raise ValueError('claim_identity_missing')
            _save_exact(identity,protocol)
        with sqlite3.connect(path) as db:
            if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('claim_corrupt')
            rows=db.execute('SELECT protocol,report,digest FROM attempt').fetchall()
            if len(rows)!=1 or rows[0][0]!=canonical(protocol):raise ValueError('claim_protocol_changed')
            old=rows[0]
            if old[1] is not None:
                if sha256(old[1].encode()).hexdigest()!=old[2]:raise ValueError('claim_report_corrupt')
                report=json.loads(old[1])
                if report['status']=='running':
                    report['status']='failed_consumed';report['failure']='interrupted_consumed';_save(db,report)
                if report['status'] not in ('complete','failed_consumed'):raise ValueError('claim_state_corrupt')
                if report['protocol']!=protocol:raise ValueError('claim_report_protocol_changed')
                _validate_common(report,protocol)
                if report['status']=='complete':_validate_complete(report,protocol)
                _verify_external(journal,protocol)
                _save_exact(root/'report.json',report)
                return report
            report=dict(protocol=protocol,status='running',model_attempts=0,metadata_attempts=0,
                preload_attempts=0,version_attempts=0,promotion_authorized=False,
                model_weights_trained=False,efficacy_established=False,rejection_receipts_created=0)
            if not created:
                report['status']='failed_consumed';report['failure']='interrupted_consumed'
                _validate_common(report,protocol);_save(db,report)
                _verify_external(journal,protocol);_save_exact(root/'report.json',report)
                return report
            _save(db,report)
            interrupt=None
            try:
                gateway,_,proposer,reviewer,reader=pilot._state(root/'authority.sqlite')
                for row in facts:
                    mid=gateway.propose(proposer,scope=SCOPE,content=row['content'],source_id=row['source_id'])
                    gateway.decide(reviewer,mid,scope=SCOPE,approve=True,evaluator_id=VERSION)
                request=MemoryRequest(SCOPE,QUERY,limit=20)
                initial=gateway.retrieve(reader,request)
                def authorize():
                    current=gateway.retrieve(reader,request)
                    if current.records!=initial.records or current.source_digest!=initial.source_digest or sorted((r.content,r.source_id) for r in current.records)!=sorted((r['content'],r['source_id']) for r in facts):
                        raise PermissionError('approved_evidence_changed')
                    if sources()!=pins:raise ValueError('source_code_changed')
                authorize()
                report['metadata_attempts']=1;_save(db,report);report['metadata_before']=metadata()
                if report['metadata_before']!={'model':pilot.MODEL,'digest':expected_digest}:raise ValueError('model_digest_mismatch')
                report['version_attempts']=1;_save(db,report);report['version_before']=runtime_version()
                report['preload_attempts']=1;_save(db,report);report['preload']=preload()
                if execution.prepare(config,QUERY,facts)['route']!='model':raise ValueError('supported_model_route_required')
                report['model_attempts']=1;_save(db,report);start=time.perf_counter()
                response=transport.run(config,QUERY,facts,authorize=authorize,constrained=False)
                report['elapsed_seconds']=time.perf_counter()-start;report['response']=response
                if response['route']!='model' or response['model_calls']!=1 or response['model']!=pilot.MODEL or response['origin']!=pilot.ORIGIN:
                    raise ValueError('real_transport_contract_changed')
                usage=response.get('usage')
                if (type(usage) is not dict or set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
                        or any(type(v) is not int or not 0<=v<=10000000 for v in usage.values())
                        or usage['completion_tokens']>128 or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']
                        or response.get('constrained') is not False or response.get('review_required') is not True
                        or response.get('synthetic_only') is not True or response.get('model_weights_trained') is not False):
                    raise ValueError('complete_actual_usage_and_safety_required')
                report['score']=score(response['raw_output'])
                report['metadata_attempts']=2;_save(db,report);report['metadata_after']=metadata()
                report['version_attempts']=2;_save(db,report);report['version_after']=runtime_version()
                if report['metadata_after']!=report['metadata_before'] or report['version_after']!=report['version_before']:raise ValueError('runtime_identity_changed')
                authorize();report['status']='complete';_validate_complete(report,protocol)
            except BaseException as error:
                report['status']='failed_consumed';report['failure']=type(error).__name__
                if isinstance(error,previous.InferenceUnavailable):
                    report['failure_reason']=error.reason
                    report['failure_detail']=error.detail
                if not isinstance(error,Exception):interrupt=error
            _validate_common(report,protocol);_save(db,report)
            _verify_external(journal,protocol);_save_exact(root/'report.json',report)
            if interrupt is not None:raise interrupt
            return report
