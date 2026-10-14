"""Frozen sixteen-call validation; no feedback or automatic promotion.

The predecessor runner is registry-specific and source-pinned. This version
reuses its durable checkpoint, authority and transport primitives while binding
a separate fixed validation registry and strict decision screen.
"""
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sqlite3
import time

from . import scientific_model_learning as pilot
from . import scientific_interface_validation_tasks as tasks
from . import scientific_interface_study as predecessor
from .scientific_task_interface import _SAFETY, _PARENT_SYSTEM, _object, _canonical
from urllib.request import Request
from .contracts import MemoryRequest, MemoryScope
from .research_supervisor import _exclusive

MODEL, ORIGIN = pilot.MODEL, pilot.ORIGIN
metadata, preload, _state = pilot.metadata, pilot.preload, pilot._state
_json, _hash = pilot._json, pilot._hash
REVISION = 'scientific-interface-validation-v1'


def sources():
    pins=predecessor.sources()
    for name in ('src/nerve_awim/memory_gateway/scientific_interface_tasks.py',
                 'src/nerve_awim/memory_gateway/scientific_task_interface.py',
                 'src/nerve_awim/memory_gateway/scientific_interface_study.py',
                 'scripts/run_scientific_interface_study.py',
                 'src/nerve_awim/memory_gateway/scientific_interface_validation_tasks.py',
                 'src/nerve_awim/memory_gateway/scientific_interface_validation.py',
                 'scripts/run_scientific_interface_validation.py'):
        pins[name]=sha256((pilot.ROOT/name).read_bytes()).hexdigest()
    return pins


def pairs():
    return [(task,arm) for i,task in enumerate(tasks.TASKS)
            for arm in (tasks.ARMS if i%2==0 else tuple(reversed(tasks.ARMS)))]


def _request(task):
    return MemoryRequest(MemoryScope(pilot.SCOPE.tenant_id,pilot.SCOPE.agent_id,'interface-validation-'+task),
                         tasks._task(task)['query'],limit=20)


def _evidence(gateway,reader,task):
    selected=gateway.retrieve(reader,_request(task))
    if sorted((r.source_id,r.content) for r in selected.records)!=sorted(
            (f['source_id'],f['content']) for f in tasks._task(task)['evidence']):
        raise ValueError('registered_evidence_changed')
    return dict(ids=[r.memory_id for r in selected.records],digest=selected.source_digest,
                context_sha256=sha256(selected.context_text.encode()).hexdigest())


_save = predecessor._save


def _summary(rows):
    return {'arms':[dict(arm=arm,calls=sum(r['arm']==arm for r in rows),
        strict_correct=sum(r['score']['strict_correct'] for r in rows if r['arm']==arm),
        supported_correct=sum(r['score']['strict_correct'] and tasks.TASKS[r['task_id']]['expected']!='ABSTAIN' for r in rows if r['arm']==arm),
        abstention_correct=sum(r['score']['strict_correct'] and tasks.TASKS[r['task_id']]['expected']=='ABSTAIN' for r in rows if r['arm']==arm),
        format_failures=sum(r['score']['format_failure'] for r in rows if r['arm']==arm),
        non_abstaining_contract_failures=sum(r['score']['non_abstaining_contract_failure'] for r in rows if r['arm']==arm)) for arm in tasks.ARMS],
        'always_abstain_correct_per_eight_tasks':4,'always_abstain_model_calls':0,
        'interpretation':'Eight fresh matched synthetic validation tasks; no broad generalization or promotion.'}


def _check_row(row):
    usage=row['usage']
    if (type(row['raw_output']) is not str or not 1<=len(row['raw_output'])<=16384
            or _json(row['score'])!=_json(tasks.judge(row['raw_output'],row['task_id']))
            or row['model']!=MODEL or row['response_status']!='generated_requires_review'
            or type(usage) is not dict or set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
            or any(type(v) is not int or not 0<=v<=10000000 for v in usage.values())
            or usage['completion_tokens']>128 or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']
            or type(row['elapsed_seconds']) not in (int,float) or not math.isfinite(row['elapsed_seconds'])
            or row['elapsed_seconds']<0):raise ValueError('invalid_measured_row')


def _check_claim(protocol):
    with sqlite3.connect(protocol['journal']) as db:
        claim=db.execute('SELECT dataset,protocol,status FROM local_model_studies WHERE run_id=?',(REVISION,)).fetchone()
    if claim!=(_hash(tasks.TASKS),json.dumps(protocol,sort_keys=True),'consumed'):
        raise ValueError('external_claim_changed')


def _validate(path,gateway,reader,report,protocol):
    _check_claim(protocol)
    if (_json(report['protocol'])!=_json(protocol) or report['status']!='complete'
            or _json([(r['task_id'],r['arm']) for r in report['rows']])!=_json(pairs())
            or (report['inference_attempts'],report['metadata_attempts'],report['preload_attempts'])!=(16,2,1)
            or report['metadata_before']!={'model':MODEL,'digest':protocol['expected_digest']}
            or report['metadata_after']!=report['metadata_before']
            or _json(report['summary'])!=_json(_summary(report['rows']))
            or _json(report['screen'])!=_json(screen(report['rows']))
            or report['promotion_authorized'] is not False or report['feedback_learning'] is not False
            or report['model_weights_trained'] is not False or report['validation_only'] is not True
            or any(type(report[k]) is not int for k in ('inference_attempts','metadata_attempts','preload_attempts'))):raise ValueError('invalid_complete_receipt')
    with sqlite3.connect(path) as db:
        claims=db.execute('SELECT ordinal,task,arm,status FROM scientific_interface_attempts ORDER BY ordinal').fetchall()
    if claims!=[(i,t,a,'complete') for i,(t,a) in enumerate(pairs())]:raise ValueError('attempt_claims_changed')
    if set(report['evidence'])!=set(tasks.TASKS):raise ValueError('evidence_roster_changed')
    for row in report['rows']:
        _check_row(row)
        expected=_evidence(gateway,reader,row['task_id'])
        if _json(expected)!=_json(report['evidence'][row['task_id']]) or _json(row['evidence'])!=_json(expected):
            raise ValueError('paired_evidence_changed')


def run(directory,expected_digest,journal,*,_resume_only=False):
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}',expected_digest):
        raise ValueError('full_operator_pinned_model_digest_required')
    for task in tasks.TASKS:tasks.trusted_task(task)
    if sum(t['expected']=='ABSTAIN' for t in tasks.TASKS.values())!=4:raise ValueError('fixed_strata_required')
    if len(tasks.TASKS)!=8 or tasks.ARMS!=('baseline_json','trusted_task'):raise ValueError('fixed_roster_required')
    root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=True);path=root/'memory.sqlite'
    journal=Path(journal).resolve()
    if journal==root or root in journal.parents:raise ValueError('external_claim_journal_required')
    with _exclusive(root):
        protocol=dict(version=REVISION,directory=str(root),journal=str(journal),model=MODEL,origin=ORIGIN,expected_digest=expected_digest,
            dataset_sha256=_hash(tasks.TASKS),direct_prefix=tasks.DIRECT_PREFIX,pairs=pairs(),source_sha256=sources(),
            max_inference_calls=16,max_output_tokens=128,socket_timeout_seconds=90,
            max_preload_calls=1,max_metadata_calls=2,validation_only=True)
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS scientific_interface_runs(id INTEGER PRIMARY KEY,protocol TEXT,report TEXT,digest TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS scientific_interface_attempts(ordinal INTEGER PRIMARY KEY,task TEXT,arm TEXT,status TEXT)')
            old=db.execute('SELECT protocol,report,digest FROM scientific_interface_runs WHERE id=1').fetchone()
            if old is None:
                if _resume_only:raise ValueError('completed_validation_required')
                pilot._helper('benchmark_local_memory')._claim(journal,REVISION,protocol)
                db.execute('INSERT INTO scientific_interface_runs VALUES(1,?,NULL,NULL)',(_json(protocol),))
            elif old[0]!=_json(protocol):raise ValueError('frozen_interface_protocol_changed')
        _check_claim(protocol)
        gateway,unused_learning,proposer,reviewer,reader=_state(path)
        if old is not None:
            if old[1] is None or sha256(old[1].encode()).hexdigest()!=old[2]:raise ValueError('corrupt_or_interrupted_consumed')
            report=json.loads(old[1])
            if report['status']!='complete':raise ValueError('failed_or_interrupted_consumed')
            _validate(path,gateway,reader,report,protocol)
            if sources()!=protocol['source_sha256']:raise ValueError('source_code_changed')
            return report
        report=dict(protocol=protocol,status='running',rows=[],evidence={},inference_attempts=0,
            preload_attempts=0,metadata_attempts=0,feedback_learning=False,model_weights_trained=False,
            promotion_authorized=False,validation_only=True)
        _save(path,report);before=None;interrupt=None
        try:
            report['metadata_attempts']=1;_save(path,report)
            before=metadata();report['metadata_before']=before
            if before!={'model':MODEL,'digest':expected_digest}:raise ValueError('model_digest_mismatch')
            report['preload_attempts']=1;_save(path,report);report['preload']=preload()
            for task_id,task in tasks.TASKS.items():
                for fact in task['evidence']:
                    mid=gateway.propose(proposer,scope=_request(task_id).scope,content=fact['content'],source_id=fact['source_id'])
                    gateway.decide(reviewer,mid,scope=_request(task_id).scope,approve=True,evaluator_id=REVISION)
                report['evidence'][task_id]=_evidence(gateway,reader,task_id)
            for index,(task_id,arm) in enumerate(pairs()):
                if sources()!=protocol['source_sha256']:raise ValueError('source_code_changed')
                if _evidence(gateway,reader,task_id)!=report['evidence'][task_id]:raise ValueError('evidence_changed')
                report['inference_attempts']+=1;_save(path,report,claim=index)
                adapter=pilot.StrategyInference('direct') if arm=='baseline_json' else TrustedScientificTaskAdapter(task_id)
                start=time.perf_counter();response=adapter.respond(gateway,reader,_request(task_id))
                evidence=report['evidence'][task_id]
                if (response['source_digest']!=evidence['digest'] or [r['memory_id'] for r in response['records']]!=evidence['ids']
                        or response['review_required'] is not True or response['synthetic_only'] is not True
                        or response['persistent_kv_restored'] is not False):raise ValueError('response_evidence_changed')
                row=dict(task_id=task_id,arm=arm,raw_output=response['output'],usage=response['usage'],
                    score=tasks.judge(response['output'],task_id),model=response['model'],response_status=response['status'],
                    evidence=evidence,elapsed_seconds=time.perf_counter()-start)
                _check_row(row);report['rows'].append(row);_save(path,report,finish=index)
            report['summary']=_summary(report['rows']);report['screen']=screen(report['rows']);report['status']='awaiting_identity_check'
        except BaseException as error:
            report['status']='failed_consumed';report['failure']=type(error).__name__
            if not isinstance(error,Exception):interrupt=error
        finally:
            try:
                if before is not None:
                    report['metadata_attempts']+=1;_save(path,report)
                    report['metadata_after']=metadata()
                    if report['metadata_after']!=before:raise ValueError('model_identity_changed')
                if sources()!=protocol['source_sha256']:raise ValueError('source_code_changed')
                if report['status']=='awaiting_identity_check':
                    report['status']='complete';_validate(path,gateway,reader,report,protocol)
            except BaseException as error:
                report['status']='failed_consumed';report['failure']=type(error).__name__
                if not isinstance(error,Exception):interrupt=error
            _save(path,report)
        if interrupt is not None:raise interrupt
        return report


class _TaskOpener:
    """One local request rewrite, followed by the original no-proxy opener."""
    def __init__(self, delegate, task_id):
        self.delegate, self.task_id = delegate, task_id

    def open(self, request, *, timeout):
        trusted = tasks.trusted_task(self.task_id)
        if (type(request) is not Request or request.full_url != ORIGIN+'/v1/chat/completions'
                or request.get_method() != 'POST' or type(timeout) is not float or timeout != 90.0
                or dict(request.header_items()) != {'Content-type':'application/json','Accept':'application/json'}
                or request.unredirected_hdrs or type(request.data) is not bytes
                or len(request.data) > 1048576):
            raise ValueError('parent_request_contract_changed')
        payload = json.loads(request.data, object_pairs_hook=_object)
        try:
            user = json.loads(payload['messages'][1]['content'], object_pairs_hook=_object)
            if (type(user) is not dict or set(user) != {'query','evidence_jsonl'}
                    or user['query'] != trusted or type(user['evidence_jsonl']) is not str):
                raise ValueError('unregistered_parent_query')
            expected = {'model':MODEL, 'temperature':0, 'stream':False, 'max_tokens':128,
                'messages':[{'role':'system','content':_PARENT_SYSTEM},
                    {'role':'user','content':json.dumps(user,ensure_ascii=True)}]}
            if _canonical(payload) != _canonical(expected):
                raise ValueError('parent_payload_contract_changed')
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError('parent_payload_contract_changed') from error
        payload['messages'][0]['content'] = _SAFETY + trusted
        rewritten = Request(request.full_url, data=json.dumps(payload).encode(),
                            headers=dict(request.header_items()), method=request.get_method())
        return self.delegate.open(rewritten, timeout=timeout)


class TrustedScientificTaskAdapter(pilot.StrategyInference):
    """Host selects one registered task; caller text cannot become instructions."""
    def __init__(self, task_id):
        tasks.trusted_task(task_id)
        self.task_id = task_id
        super().__init__('direct')
        self._opener = _TaskOpener(self._opener, task_id)

    def _model_response(self, query, context):
        if type(query) is not str or query != tasks._task(self.task_id)['query']:
            raise ValueError('registered_task_query_required')
        return super()._model_response(query, context)


def screen(rows):
    summary=_summary(rows)['arms']
    baseline,candidate=summary
    strata={name:{arm:sum(row['score']['strict_correct'] for row in rows
                          if row['arm']==arm and tasks.STRATA[row['task_id']]==name)
                  for arm in tasks.ARMS} for name in sorted(set(tasks.STRATA.values()))}
    no_stratum_regression=all(value['trusted_task']>=value['baseline_json'] for value in strata.values())
    passed=(candidate['strict_correct']>baseline['strict_correct']
            and candidate['supported_correct']>=baseline['supported_correct']
            and candidate['abstention_correct']>=baseline['abstention_correct']
            and candidate['supported_correct']==4 and candidate['abstention_correct']==4
            and no_stratum_regression)
    return dict(passed=passed,next_action='candidate_requires_review' if passed else 'retain_baseline',
        strictly_better_overall=candidate['strict_correct']>baseline['strict_correct'],
        strata_correct=strata,no_stratum_regression=no_stratum_regression,
        no_supported_regression=candidate['supported_correct']>=baseline['supported_correct'],
        no_abstention_regression=candidate['abstention_correct']>=baseline['abstention_correct'],
        all_supported_correct=candidate['supported_correct']==4,
        all_abstentions_correct=candidate['abstention_correct']==4,
        promotion_authorized=False)


def validate_receipt(directory,expected_digest,journal):
    """Require an existing complete receipt; never initiate new model work."""
    path=Path(directory).resolve()/'memory.sqlite'
    if not path.is_file():raise ValueError('completed_validation_required')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT report,digest FROM scientific_interface_runs WHERE id=1').fetchone()
    if (row is None or row[0] is None or sha256(row[0].encode()).hexdigest()!=row[1]
            or json.loads(row[0]).get('status')!='complete'):
        raise ValueError('completed_validation_required')
    return run(directory,expected_digest,journal,_resume_only=True)
