"""Four consumed local probes: output structure is distinct from grounded truth."""
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from urllib.request import build_opener, ProxyHandler

from . import scientific_interface_validation as previous
from . import scientific_structured_tasks as tasks
from .scientific_structured_inference import StructuredScientificInference
from .inference import _NoRedirect, InferenceUnavailable
from .contracts import MemoryRequest, MemoryScope
from .research_supervisor import _exclusive

pilot=previous.pilot
MODEL,ORIGIN=pilot.MODEL,pilot.ORIGIN
_json,_hash=pilot._json,pilot._hash
metadata,preload=pilot.metadata,pilot.preload
_save=previous._save
REVISION='scientific-structured-preflight-v1'


def sources():
    pins=previous.sources()
    for name in ('scientific_structured_tasks.py','scientific_structured_inference.py','scientific_structured_preflight.py'):
        path='src/nerve_awim/memory_gateway/'+name
        pins[path]=sha256((pilot.ROOT/path).read_bytes()).hexdigest()
    path='scripts/run_scientific_structured_preflight.py'
    pins[path]=sha256((pilot.ROOT/path).read_bytes()).hexdigest()
    return pins


def runtime_version():
    opener=build_opener(ProxyHandler({}),_NoRedirect())
    with opener.open(ORIGIN+'/api/version',timeout=5) as response:
        raw=response.read(4097)
    if len(raw)>4096:raise ValueError('oversized_runtime_version')
    value=json.loads(raw)
    if type(value) is not dict or type(value.get('version')) is not str or not re.fullmatch(r'[A-Za-z0-9._+-]{1,80}',value['version']):
        raise ValueError('invalid_runtime_version')
    return value['version']


def pairs():
    return [[task,arm] for index,task in enumerate(tasks.TASKS)
            for arm in (tasks.ARMS if index%2==0 else tuple(reversed(tasks.ARMS)))]


def request(task):
    return MemoryRequest(MemoryScope(pilot.SCOPE.tenant_id,pilot.SCOPE.agent_id,'structured-'+task),tasks._task(task)['query'],limit=20)


def evidence(gateway,reader,task):
    selected=gateway.retrieve(reader,request(task))
    if sorted((r.source_id,r.content) for r in selected.records)!=sorted((r['source_id'],r['content']) for r in tasks._task(task)['evidence']):
        raise ValueError('registered_evidence_changed')
    return dict(ids=[r.memory_id for r in selected.records],digest=selected.source_digest,
                context_sha256=sha256(selected.context_text.encode()).hexdigest())


def summary(rows):
    return {'arms':[dict(arm=arm,calls=sum(r['arm']==arm for r in rows),
        schema_valid=sum(r['score']['schema_valid'] for r in rows if r['arm']==arm),
        format_valid=sum(r['score']['format_valid'] for r in rows if r['arm']==arm),
        strict_correct=sum(r['score']['strict_correct'] for r in rows if r['arm']==arm),
        unsupported_selection=sum(r['score']['unsupported_selection'] for r in rows if r['arm']==arm)) for arm in tasks.ARMS],
        'interpretation':'Two paired synthetic capability probes only; schema-valid output does not establish factual correctness or general enforcement.'}


def _check_row(row):
    usage=row['usage']
    if (type(row['raw_output']) is not str or not 1<=len(row['raw_output'])<=16384
            or _json(row['score'])!=_json(tasks.judge(row['raw_output'],row['task_id']))
            or row['model']!=MODEL or row['response_status']!='generated_requires_review'
            or type(usage) is not dict or set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
            or any(type(v) is not int or not 0<=v<=10000000 for v in usage.values())
            or usage['completion_tokens']>128 or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']
            or type(row['elapsed_seconds']) not in (int,float) or not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds']<0):
        raise ValueError('invalid_measured_row')


def _claim_check(protocol):
    with sqlite3.connect(protocol['journal']) as db:
        claim=db.execute('SELECT dataset,protocol,status FROM local_model_studies WHERE run_id=?',(REVISION,)).fetchone()
    if claim!=(_hash(tasks.TASKS),json.dumps(protocol,sort_keys=True),'consumed'):raise ValueError('external_claim_changed')


def _validate(path,gateway,reader,report,protocol):
    _claim_check(protocol)
    if (_json(report['protocol'])!=_json(protocol) or report['status']!='complete'
            or _json([(r['task_id'],r['arm']) for r in report['rows']])!=_json(pairs())
            or any(type(report[k]) is not int for k in ('inference_attempts','metadata_attempts','version_attempts','preload_attempts'))
            or [report[k] for k in ('inference_attempts','metadata_attempts','version_attempts','preload_attempts')]!=[4,2,2,1]
            or report['metadata_before']!={'model':MODEL,'digest':protocol['expected_digest']}
            or report['metadata_after']!=report['metadata_before'] or report['version_after']!=report['version_before']
            or type(report['version_before']) is not str or not re.fullmatch(r'[A-Za-z0-9._+-]{1,80}',report['version_before'])
            or _json(report['summary'])!=_json(summary(report['rows']))
            or any(report[k] is not False for k in ('promotion_authorized','feedback_learning','model_weights_trained','improvement_established'))):
        raise ValueError('invalid_complete_receipt')
    with sqlite3.connect(path) as db:
        claims=db.execute('SELECT ordinal,task,arm,status FROM scientific_interface_attempts ORDER BY ordinal').fetchall()
    if claims!=[(i,t,a,'complete') for i,(t,a) in enumerate(pairs())]:raise ValueError('attempt_claims_changed')
    if set(report['evidence'])!=set(tasks.TASKS):raise ValueError('evidence_roster_changed')
    for row in report['rows']:
        _check_row(row)
        actual=evidence(gateway,reader,row['task_id'])
        if _json(actual)!=_json(row['evidence']) or _json(actual)!=_json(report['evidence'][row['task_id']]):
            raise ValueError('evidence_changed')


def run(directory,expected_digest,journal):
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}',expected_digest):raise ValueError('full_model_digest_required')
    if len(tasks.TASKS)!=2 or tasks.ARMS!=('unrestricted_json','schema_json'):raise ValueError('fixed_probe_roster_required')
    for task in tasks.TASKS:tasks.trusted_task(task)
    root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=True);path=root/'memory.sqlite'
    journal=Path(journal).resolve()
    if journal==root or root in journal.parents:raise ValueError('external_journal_required')
    with _exclusive(root):
        protocol=dict(version=REVISION,directory=str(root),journal=str(journal),model=MODEL,origin=ORIGIN,
            expected_digest=expected_digest,dataset_sha256=_hash(tasks.TASKS),schema=tasks.SCHEMA,
            pairs=pairs(),source_sha256=sources(),max_inference_calls=4,max_output_tokens=128,
            socket_timeout_seconds=90,max_preload_calls=1,max_metadata_calls=2,max_version_calls=2,preflight_only=True)
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS scientific_interface_runs(id INTEGER PRIMARY KEY,protocol TEXT,report TEXT,digest TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS scientific_interface_attempts(ordinal INTEGER PRIMARY KEY,task TEXT,arm TEXT,status TEXT)')
            old=db.execute('SELECT protocol,report,digest FROM scientific_interface_runs WHERE id=1').fetchone()
            if old is None:
                pilot._helper('benchmark_local_memory')._claim(journal,REVISION,protocol)
                db.execute('INSERT INTO scientific_interface_runs VALUES(1,?,NULL,NULL)',(_json(protocol),))
            elif old[0]!=_json(protocol):raise ValueError('frozen_probe_protocol_changed')
        _claim_check(protocol)
        gateway,_,proposer,reviewer,reader=pilot._state(path)
        if old is not None:
            if old[1] is None or sha256(old[1].encode()).hexdigest()!=old[2]:raise ValueError('corrupt_or_interrupted_consumed')
            report=json.loads(old[1]);_validate(path,gateway,reader,report,protocol)
            if sources()!=protocol['source_sha256']:raise ValueError('source_code_changed')
            return report
        report=dict(protocol=protocol,status='running',rows=[],evidence={},inference_attempts=0,metadata_attempts=0,
            version_attempts=0,preload_attempts=0,promotion_authorized=False,feedback_learning=False,
            model_weights_trained=False,improvement_established=False)
        _save(path,report);before=None;version=None;interrupted=None
        try:
            report['metadata_attempts']=1;_save(path,report);before=metadata();report['metadata_before']=before
            if before!={'model':MODEL,'digest':expected_digest}:raise ValueError('model_identity_mismatch')
            report['version_attempts']=1;_save(path,report);version=runtime_version();report['version_before']=version
            report['preload_attempts']=1;_save(path,report);report['preload']=preload()
            for task_id,task in tasks.TASKS.items():
                for fact in task['evidence']:
                    mid=gateway.propose(proposer,scope=request(task_id).scope,content=fact['content'],source_id=fact['source_id'])
                    gateway.decide(reviewer,mid,scope=request(task_id).scope,approve=True,evaluator_id=REVISION)
                report['evidence'][task_id]=evidence(gateway,reader,task_id)
            for index,(task_id,arm) in enumerate(pairs()):
                if sources()!=protocol['source_sha256']:raise ValueError('source_code_changed')
                if evidence(gateway,reader,task_id)!=report['evidence'][task_id]:raise ValueError('evidence_changed')
                report['inference_attempts']+=1;_save(path,report,claim=index)
                adapter=StructuredScientificInference(task_id,constrained=arm=='schema_json')
                start=time.perf_counter();response=adapter.respond(gateway,reader,request(task_id))
                expected=report['evidence'][task_id]
                if (response['source_digest']!=expected['digest'] or [r['memory_id'] for r in response['records']]!=expected['ids']
                    or response['review_required'] is not True or response['synthetic_only'] is not True
                    or response['persistent_kv_restored'] is not False):raise ValueError('response_evidence_changed')
                row=dict(task_id=task_id,arm=arm,raw_output=response['output'],score=tasks.judge(response['output'],task_id),
                    usage=response['usage'],model=response['model'],response_status=response['status'],evidence=expected,
                    elapsed_seconds=time.perf_counter()-start)
                _check_row(row);report['rows'].append(row);_save(path,report,finish=index)
            report['summary']=summary(report['rows']);report['status']='awaiting_identity_check'
        except BaseException as error:
            report['status']='failed_consumed';report['failure']=type(error).__name__
            if isinstance(error,InferenceUnavailable):
                report['failure_reason']=error.reason
                report['failure_detail']=error.detail
            if not isinstance(error,Exception):interrupted=error
        finally:
            try:
                if before is not None:
                    report['metadata_attempts']+=1;_save(path,report);report['metadata_after']=metadata()
                    if report['metadata_after']!=before:raise ValueError('model_identity_changed')
                if version is not None:
                    report['version_attempts']+=1;_save(path,report);report['version_after']=runtime_version()
                    if report['version_after']!=version:raise ValueError('runtime_changed')
                if sources()!=protocol['source_sha256']:raise ValueError('source_code_changed')
                if report['status']=='awaiting_identity_check':
                    report['status']='complete';_validate(path,gateway,reader,report,protocol)
            except BaseException as error:
                report['status']='failed_consumed';report['failure']=type(error).__name__
                if not isinstance(error,Exception):interrupted=error
            _save(path,report)
        if interrupted is not None:raise interrupted
        return report
