"""Prospective 60-task development comparison of a compact hybrid policy.

No holdout, promotion, weight training or negative-efficacy journal writes.
The seed fixes task/control/order selection; model temperature is zero and model
sampling seed is requested but backend reproducibility is not guaranteed. CPU
inference cost is measured in tokens/time, not USD.
"""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

from . import scientific_compact_dev_transport as transport
from . import scientific_candidate_execution as grammar
from . import scientific_candidate_screening as screening
from . import scientific_candidate_transport_smoke as smoke
from . import scientific_candidate_format_study as format_probe
from . import scientific_task_bank as bank_module
from .scientific_task_bank import ScientificTaskBank
from ..memory_v18 import MemoryAuthority
from .contracts import MemoryScope,MemoryRequest
from .research_supervisor import _exclusive

pilot=smoke.pilot
metadata,preload,runtime_version=smoke.metadata,smoke.preload,smoke.runtime_version
canonical,_hash=pilot._json,pilot._hash
VERSION='scientific-compact-development-v1'
SEED=20261015
STRATA=('conflict','supported-measurement','unit-mismatch')
ARMS=('baseline','candidate','always_abstain','random')
MAX_MODEL_CALLS=100
MAX_WALL_SECONDS=10800


def sources():
    pins=screening.sources();pins.update(format_probe.sources());pins.update(bank_module.sources())
    for relative in ('src/nerve_awim/memory_gateway/scientific_compact_dev_transport.py',
                     'src/nerve_awim/memory_gateway/scientific_compact_dev_study.py',
                     'scripts/run_scientific_compact_dev_study.py'):
        pins[relative]=sha256((pilot.ROOT/relative).read_bytes()).hexdigest()
    return pins


def _policies(proposal, expected_digest, pins):
    return {arm:_hash({'version':VERSION,'base_candidate':proposal['candidate_sha256'],
        'compact_system':transport.SYSTEM,'transport_sha256':pins['src/nerve_awim/memory_gateway/scientific_compact_dev_transport.py'],
        'decoder':'strict_alias_triplet_or_abstain_v1','model_sampling_seed':SEED,
        'max_prompt_tokens':transport.MAX_PROMPT_TOKENS,'max_output_tokens':transport.MAX_OUTPUT_TOKENS,
        'conflict_detection':arm=='candidate','arm':arm,'model_digest':expected_digest}) for arm in ARMS}


def _preload_valid(value):
    return (type(value) is dict and 'wall_seconds' in value
        and set(value)<= {'wall_seconds','load_duration_nanoseconds','total_duration_nanoseconds'}
        and type(value['wall_seconds']) in (int,float) and math.isfinite(value['wall_seconds']) and value['wall_seconds']>=0
        and all(type(v) is int and v>=0 for k,v in value.items() if k!='wall_seconds'))


def _read(path,limit=8*1024*1024):
    path=Path(path)
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(descriptor,'rb') as stream:
        mode=os.fstat(stream.fileno())
        if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode)!=0o600:raise ValueError('private_regular_input_required')
        raw=stream.read(limit+1)
    if len(raw)>limit:raise ValueError('bounded_input_required')
    return raw


def _digest(path):return sha256(_read(path)).hexdigest()
def _identity(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def _host_inputs(bank_directory,bank_manifest_sha256,screening_directory,registration_directory,history_directory):
    bank_directory=Path(bank_directory).resolve();screening_directory=Path(screening_directory).resolve()
    screen_path=screening_directory/'report.json'
    if not screen_path.is_file():raise ValueError('existing_screening_required')
    original_screen=_read(screen_path,1024*1024)
    screened=screening.run(screening_directory,registration_directory,history_directory)
    if _read(screen_path,1024*1024)!=original_screen or screened['status']!='screened':raise ValueError('screening_unavailable_or_changed')
    allowed=[p for p in screened['decision']['allowed'] if p['hypothesis']['mutation']=='conflict_check']
    if len(allowed)!=1:raise ValueError('one_screened_conflict_candidate_required')
    authority=MemoryAuthority();actor=authority.issue('synthetic-science','development-study',permissions=('read',))
    bank=ScientificTaskBank(bank_directory,authority,expected_manifest_hash=bank_manifest_sha256,
                           tenant_id='synthetic-science',generator_agent_id='development-study')
    # Never call bank.status() (it opens both files), holdout(), or read the seed.
    development=bank.development(actor)
    excluded={_hash({'query':smoke.QUERY,'evidence':smoke.evidence()})}
    excluded.update(_hash({'query':task['query'],'evidence':task['evidence']}) for task in format_probe.tasks().values())
    selected=[]
    for stratum in STRATA:
        pool=[row for row in development if row['stratum']==stratum
              and _hash({'query':row['query'],'evidence':row['evidence']}) not in excluded]
        if len(pool)<20:raise ValueError('twenty_development_items_per_stratum_required')
        pool.sort(key=lambda row:(sha256(f'{SEED}:{row["task_id"]}'.encode()).hexdigest(),row['task_id']))
        selected.extend(pool[:20])
    selected.sort(key=lambda row:(sha256(f'{SEED}:order:{row["task_id"]}'.encode()).hexdigest(),row['task_id']))
    if len({row['task_id'] for row in selected})!=60:raise ValueError('unique_fixed_roster_required')
    for row in selected:
        if row['split']!='dev':raise ValueError('development_only')
        compact=transport.prepare(row['query'],row['evidence'])
        decision=grammar.prepare(allowed[0]['candidate'],row['query'],row['evidence'])
        should_abstain=row['stratum']=='conflict'
        if (decision['route']=='deterministic_conflict_abstention')!=should_abstain:
            raise ValueError('fixed_hybrid_route_mismatch')
    binding=dict(bank_manifest_sha256=bank_manifest_sha256,development_sha256=_digest(bank_directory/'dev.json'),
        screening_sha256=sha256(original_screen).hexdigest(),hypothesis_sha256=allowed[0]['hypothesis_sha256'],
        candidate_sha256=allowed[0]['candidate_sha256'],excluded_prior_input_sha256=sorted(excluded))
    return selected,allowed[0],binding


def _random_raw(task,prepared):
    options=['ABSTAIN']+[f'{record["value"]}|{record["unit"]}|{alias}' for alias,record in sorted(prepared['aliases'].items())]
    index=int(sha256(f'{SEED}:random:{task["task_id"]}'.encode()).hexdigest(),16)%len(options)
    return options[index]


def score(raw,task,prepared):
    try:decoded=transport.decode(raw,prepared);formatted=True
    except ValueError:decoded=None;formatted=False
    return {'format_valid':formatted,'strict_correct':decoded==task['expected']}


def schedule(tasks):
    result=[]
    for index,task in enumerate(tasks):
        pair=('baseline','candidate') if index%2==0 else ('candidate','baseline')
        for arm in (*pair,'always_abstain','random'):result.append((task['task_id'],arm))
    return result


def _route(task,arm):
    if arm=='candidate':
        decision=grammar.prepare(grammar.candidates.SPACE['conflict_check'],task['query'],task['evidence'])
        if decision['route']=='deterministic_conflict_abstention':return 'candidate_conflict_rule'
    if arm in ('baseline','candidate'):return 'model'
    return arm


def _usage(usage):
    if (type(usage) is not dict or set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
            or any(type(v) is not int or not 0<=v<=10000000 for v in usage.values())
            or usage['completion_tokens']>transport.MAX_OUTPUT_TOKENS
            or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']):raise ValueError('actual_usage_required')


def _summary(rows):
    arms=[]
    for arm in ARMS:
        chosen=[r for r in rows if r['arm']==arm]
        strata={st:dict(count=sum(r['stratum']==st for r in chosen),correct=sum(r['score']['strict_correct'] for r in chosen if r['stratum']==st),
            format_valid=sum(r['score']['format_valid'] for r in chosen if r['stratum']==st)) for st in STRATA}
        for values in strata.values():values['accuracy']=values['correct']/values['count'] if values['count'] else None
        arms.append(dict(arm=arm,count=len(chosen),correct=sum(r['score']['strict_correct'] for r in chosen),
            accuracy=sum(r['score']['strict_correct'] for r in chosen)/len(chosen) if chosen else None,
            format_valid=sum(r['score']['format_valid'] for r in chosen),strata=strata))
    scores={row['arm']:row for row in arms}
    paired={}
    for task in {row['task_id'] for row in rows}:
        group={row['arm']:row for row in rows if row['task_id']==task}
        if 'baseline' in group and 'candidate' in group:
            paired[task]=int(group['candidate']['score']['strict_correct'])-int(group['baseline']['score']['strict_correct'])
    passed=(all(scores['candidate']['correct']>scores[a]['correct'] for a in ('baseline','always_abstain','random'))
        and all(scores['candidate']['strata'][st]['correct']>=scores['baseline']['strata'][st]['correct'] for st in STRATA))
    usage={key:sum(row['usage'][key] for row in rows if row['usage'] is not None) for key in ('prompt_tokens','completion_tokens','total_tokens')}
    return dict(arms=arms,paired_gains=sum(v==1 for v in paired.values()),paired_losses=sum(v==-1 for v in paired.values()),
        paired_ties=sum(v==0 for v in paired.values()),measured_tokens=usage,
        model_seconds=sum(row['elapsed_seconds'] for row in rows if row['model_calls']),
        measured_usd=None,verdict='candidate_requires_review' if passed else 'retain_baseline',
        prospective_gate_passed=passed,generalization_verdict='insufficient_power',
        interpretation='Fixed development comparison of a hybrid rule/model pipeline; no holdout or causal weight-learning claim.')


def _save(db,report,claim=None,complete=None):
    if claim is not None:
        ordinal,task,arm,row_index=claim
        db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',(ordinal,task,arm,row_index,'claimed'))
    if complete is not None:db.execute("UPDATE calls SET status='complete' WHERE ordinal=? AND status='claimed'",(complete,))
    raw=canonical(report);db.execute('UPDATE study SET report=?,digest=? WHERE id=1',(raw,sha256(raw.encode()).hexdigest()));db.commit()


def _external(journal,protocol):
    smoke._private(journal)
    with sqlite3.connect(journal.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('external_claim_corrupt')
        row=db.execute('SELECT protocol,status FROM compact_dev_claims WHERE dataset=?',(protocol['dataset_sha256'],)).fetchone()
        if row!=(canonical(protocol),'consumed'):raise ValueError('external_claim_changed')


def _claim(journal,protocol,root):
    if not journal.exists():
        if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('external_claim_missing')
        fd=os.open(journal,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        with sqlite3.connect(journal) as db:db.execute('CREATE TABLE compact_dev_claims(dataset TEXT PRIMARY KEY,version TEXT UNIQUE,protocol TEXT,status TEXT)')
    smoke._private(journal)
    with sqlite3.connect(journal) as db:
        db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO compact_dev_claims VALUES(?,?,?,?)',(protocol['dataset_sha256'],VERSION,canonical(protocol),'consumed'))


def _validate(db,report,protocol,tasks):
    if (canonical(report['protocol'])!=canonical(protocol) or report['status'] not in ('complete','failed_consumed')
            or type(report['rows']) is not list or len(report['rows'])>240
            or any(type(report[k]) is not int or not 0<=report[k]<=bound for k,bound in
                [('model_attempts',100),('metadata_attempts',2),('version_attempts',2),('preload_attempts',1)])
            or any(report[k] is not False for k in ('holdout_accessed','promotion_authorized','model_weights_trained','efficacy_established'))
            or report['rejection_receipts_created']!=0 or type(report['rejection_receipts_created']) is not int):raise ValueError('terminal_dev_receipt_invalid')
    by_id={task['task_id']:task for task in tasks};order=schedule(tasks);completed_claims=[]
    for index,row in enumerate(report['rows']):
        task_id,arm=order[index];task=by_id[task_id];prepared=transport.prepare(task['query'],task['evidence']);route=_route(task,arm)
        if (row['task_id']!=task_id or row['arm']!=arm or row['stratum']!=task['stratum'] or row['route']!=route
                or row['input_sha256']!=prepared['input_sha256'] or row['task_content_sha256']!=task['content_sha256']
                or row['policy_sha256']!=protocol['policies'][arm] or canonical(row['score'])!=canonical(score(row['raw_output'],task,prepared))
                or type(row['elapsed_seconds']) not in (int,float) or not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds']<0
                or type(row['model_calls']) is not int or row['model_calls']!=(1 if route=='model' else 0)
                or type(row['raw_output']) is not str or not 1<=len(row['raw_output'])<=16384):raise ValueError('dev_row_changed')
        if route=='model':
            if type(row['model_sampling_seed']) is not int or row['model_sampling_seed']!=SEED:raise ValueError('requested_model_seed_changed')
            _usage(row['usage'])
            if row['usage']['prompt_tokens']>150:raise ValueError('successful_row_prompt_budget_exceeded')
            completed_claims.append((len(completed_claims),task_id,arm,index,'complete'))
        else:
            raw=_random_raw(task,prepared) if arm=='random' else 'ABSTAIN'
            if row['usage'] is not None or row['model_sampling_seed'] is not None or row['raw_output']!=raw:raise ValueError('zero_call_control_changed')
    claims=db.execute('SELECT ordinal,task,arm,row_index,status FROM calls ORDER BY ordinal').fetchall()
    if not len(completed_claims)<=report['model_attempts']<=len(completed_claims)+1:raise ValueError('model_attempt_count_changed')
    expected=list(completed_claims)
    if report['model_attempts']>len(completed_claims):
        index=len(report['rows']);task_id,arm=order[index]
        if _route(by_id[task_id],arm)!='model':raise ValueError('unexpected_model_claim')
        expected.append((len(completed_claims),task_id,arm,index,'claimed'))
    if claims!=expected:raise ValueError('per_call_claims_changed')
    if report['model_attempts'] and (report.get('metadata_before')!={'model':pilot.MODEL,'digest':protocol['expected_digest']}
            or report['metadata_attempts']<1 or report['version_attempts']<1 or report['preload_attempts']!=1
            or type(report.get('version_before')) is not str or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before'])
            or not _preload_valid(report.get('preload'))):
        raise ValueError('predispatch_identity_changed')
    if 'preload' in report and not _preload_valid(report['preload']):raise ValueError('preload_measurement_invalid')
    if report['status']=='failed_consumed' and ('summary' in report or 'verdict' in report):raise ValueError('failed_summary_forbidden')
    if 'over_budget_response' in report:
        failed=report['over_budget_response'];_usage(failed['usage'])
        if (report['status']!='failed_consumed' or failed['usage']['prompt_tokens']<=150 or report['model_attempts']!=len(completed_claims)+1
                or type(failed['raw_output']) is not str or not 1<=len(failed['raw_output'])<=16384
                or 'score' in failed):raise ValueError('over_budget_failure_changed')
    if report['status']=='complete':
        if (len(report['rows'])!=240 or (report['model_attempts'],report['metadata_attempts'],report['version_attempts'],report['preload_attempts'])!=(100,2,2,1)
                or report['metadata_after']!=report['metadata_before'] or report['version_after']!=report['version_before']
                or canonical(report['summary'])!=canonical(_summary(report['rows']))):raise ValueError('complete_dev_receipt_invalid')
    elif type(report.get('failure')) is not str or not re.fullmatch('[A-Za-z0-9_]{1,80}',report['failure']):raise ValueError('failure_evidence_required')
    if 'failure_reason' in report or 'failure_detail' in report:
        transport.InferenceUnavailable(report['failure_reason'],report['failure_detail'])
    _external(Path(protocol['journal']),protocol)


def _run(directory,expected_digest,journal,*,bank_directory,bank_manifest_sha256,screening_directory,registration_directory,history_directory,resume_only):
    if not _identity(expected_digest) or not _identity(bank_manifest_sha256):raise ValueError('full_identity_pins_required')
    root=Path(directory).resolve();journal=Path(journal).resolve()
    evidence_roots=[Path(p).resolve() for p in (bank_directory,screening_directory,registration_directory,history_directory)]
    if any(root==p or root in p.parents or p in root.parents or journal==p or p in journal.parents or journal in p.parents for p in evidence_roots):
        raise ValueError('separate_study_and_evidence_paths_required')
    if resume_only and not (root/'claim.sqlite').is_file():raise ValueError('existing_terminal_receipt_required')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_study_directory_required')
    if journal==root or root in journal.parents:raise ValueError('external_claim_journal_required')
    paths=dict(bank_directory=str(Path(bank_directory).resolve()),bank_manifest_sha256=bank_manifest_sha256,
        screening_directory=str(Path(screening_directory).resolve()),registration_directory=str(Path(registration_directory).resolve()),history_directory=str(Path(history_directory).resolve()))
    tasks,proposal,inputs=_host_inputs(**paths);pins=sources()
    policies=_policies(proposal,expected_digest,pins)
    roster=[dict(task_id=t['task_id'],stratum=t['stratum'],content_sha256=t['content_sha256']) for t in tasks]
    protocol=dict(version=VERSION,directory=str(root),journal=str(journal),expected_digest=expected_digest,model=pilot.MODEL,origin=pilot.ORIGIN,
        sources=pins,paths=paths,inputs=inputs,seed=SEED,roster=roster,dataset_sha256=_hash(roster),policies=policies,
        hypothesis_sha256=proposal['hypothesis_sha256'],schedule=schedule(tasks),max_model_calls=100,max_wall_seconds=MAX_WALL_SECONDS,
        max_prompt_tokens=150,max_output_tokens=transport.MAX_OUTPUT_TOKENS,socket_timeout_seconds=90,
        model_temperature=0,model_sampling_seed=SEED,model_seed_interpretation='Requested backend seed; no bitwise reproducibility guarantee.',control_seed=SEED,selection_rule='sha256(seed:task_id), first20 within each fixed development stratum',
        acceptance='strictly beat baseline,always_abstain,random; no stratum regression against baseline; development only')
    path=root/'claim.sqlite'
    with _exclusive(root):
        created=not path.exists()
        if created:
            if resume_only:raise ValueError('existing_terminal_receipt_required')
            if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('missing_claim_consumed')
            _claim(journal,protocol,root)
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE study(id INTEGER PRIMARY KEY CHECK(id=1),protocol TEXT,report TEXT,digest TEXT)')
                db.execute('CREATE TABLE calls(ordinal INTEGER PRIMARY KEY,task TEXT,arm TEXT,row_index INTEGER,status TEXT)')
                db.execute('INSERT INTO study VALUES(1,?,NULL,NULL)',(canonical(protocol),))
        smoke._private(path);_external(journal,protocol)
        with sqlite3.connect(path) as db:
            if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('claim_corrupt')
            old=db.execute('SELECT protocol,report,digest FROM study WHERE id=1').fetchone()
            if old is None or old[0]!=canonical(protocol):raise ValueError('frozen_protocol_changed')
            if not created:
                if old[1] is None:raise ValueError('incomplete_claim_consumed')
                if sha256(old[1].encode()).hexdigest()!=old[2]:raise ValueError('report_hash_changed')
                report=json.loads(old[1])
                if resume_only and report['status'] not in ('complete','failed_consumed'):raise ValueError('existing_terminal_receipt_required')
                if report['status']=='running':report['status']='failed_consumed';report['failure']='interrupted_consumed'
                _validate(db,report,protocol,tasks)
                if json.loads(old[1])['status']=='running':_save(db,report)
                if sources()!=pins:raise ValueError('sources_changed')
                if resume_only:
                    if _read(root/'report.json')!=(canonical(report)+'\n').encode():raise ValueError('terminal_publication_changed')
                else:smoke._save_exact(root/'report.json',report)
                return report
            report=dict(protocol=protocol,status='running',rows=[],model_attempts=0,metadata_attempts=0,version_attempts=0,preload_attempts=0,
                holdout_accessed=False,promotion_authorized=False,model_weights_trained=False,efficacy_established=False,rejection_receipts_created=0)
            _save(db,report);start=time.monotonic();interrupt=None
            try:
                gateway,_,proposer,reviewer,reader=pilot._state(root/'authority.sqlite')
                by_id={task['task_id']:task for task in tasks};contexts={task['task_id']:MemoryScope('synthetic-science','model-research','compact-dev-'+str(i)) for i,task in enumerate(tasks)}
                snapshots={}
                for task in tasks:
                    scope=contexts[task['task_id']]
                    for fact in task['evidence']:
                        mid=gateway.propose(proposer,scope=scope,content=fact['content'],source_id=fact['source_id'])
                        gateway.decide(reviewer,mid,scope=scope,approve=True,evaluator_id=VERSION)
                    snapshots[task['task_id']]=gateway.retrieve(reader,MemoryRequest(scope,task['query'],limit=20))
                def authorize(task):
                    current=gateway.retrieve(reader,MemoryRequest(contexts[task['task_id']],task['query'],limit=20))
                    old=snapshots[task['task_id']]
                    if (current.records!=old.records or current.source_digest!=old.source_digest or
                        sorted((r.content,r.source_id) for r in current.records)!=sorted((r['content'],r['source_id']) for r in task['evidence'])):raise PermissionError('authorized_evidence_changed')
                    if sources()!=pins or _digest(Path(paths['bank_directory'])/'dev.json')!=inputs['development_sha256'] or _digest(Path(paths['bank_directory'])/'manifest.json')!=bank_manifest_sha256:raise ValueError('sources_or_development_changed')
                    if time.monotonic()-start>MAX_WALL_SECONDS:raise TimeoutError('study_wall_budget')
                report['metadata_attempts']=1;_save(db,report);report['metadata_before']=metadata()
                if report['metadata_before']!={'model':pilot.MODEL,'digest':expected_digest}:raise ValueError('model_identity_mismatch')
                report['version_attempts']=1;_save(db,report);report['version_before']=runtime_version()
                if type(report['version_before']) is not str or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before']):raise ValueError('runtime_version_required')
                report['preload_attempts']=1;_save(db,report);report['preload']=preload()
                if not _preload_valid(report['preload']):raise ValueError('preload_measurement_invalid')
                for row_index,(task_id,arm) in enumerate(schedule(tasks)):
                    task=by_id[task_id];authorize(task);prepared=transport.prepare(task['query'],task['evidence']);route=_route(task,arm)
                    usage=None;calls=0;call_index=None;row_start=time.perf_counter()
                    if route=='model':
                        call_index=report['model_attempts'];report['model_attempts']+=1
                        if report['model_attempts']>100:raise ValueError('model_budget_exhausted')
                        _save(db,report,claim=(call_index,task_id,arm,row_index))
                        response=transport.run(prepared,authorize=lambda:authorize(task))
                        if (response['model']!=pilot.MODEL or response['origin']!=pilot.ORIGIN or response['input_sha256']!=prepared['input_sha256']
                                or type(response['model_calls']) is not int or response['model_calls']!=1 or response['prompt_limit_verified'] is not True
                                or response['review_required'] is not True or response['synthetic_only'] is not True or response['model_weights_trained'] is not False
                                or type(response['model_sampling_seed']) is not int or response['model_sampling_seed']!=SEED
                                or type(response['max_prompt_tokens']) is not int or response['max_prompt_tokens']!=150
                                or type(response['prompt_limit_verification']) is not str or response['prompt_limit_verification']!='runtime_usage_after_call'):
                            raise ValueError('measured_transport_required')
                        raw=response['raw_output'];usage=response['usage'];_usage(usage)
                        if type(raw) is not str or not 1<=len(raw)<=16384:raise ValueError('bounded_raw_output_required')
                        if usage['prompt_tokens']>150:raise transport.PromptBudgetExceeded(raw,usage)
                        calls=1
                    else:raw=_random_raw(task,prepared) if arm=='random' else 'ABSTAIN'
                    authorize(task)
                    row=dict(task_id=task_id,stratum=task['stratum'],arm=arm,route=route,raw_output=raw,usage=usage,model_calls=calls,
                        model_sampling_seed=SEED if calls else None,
                        input_sha256=prepared['input_sha256'],task_content_sha256=task['content_sha256'],policy_sha256=policies[arm],
                        elapsed_seconds=time.perf_counter()-row_start,score=score(raw,task,prepared))
                    report['rows'].append(row);_save(db,report,complete=call_index)
                report['metadata_attempts']=2;_save(db,report);report['metadata_after']=metadata()
                report['version_attempts']=2;_save(db,report);report['version_after']=runtime_version()
                fresh_tasks,fresh_proposal,fresh_inputs=_host_inputs(**paths)
                if canonical(fresh_tasks)!=canonical(tasks) or fresh_inputs!=inputs or sources()!=pins:raise ValueError('study_inputs_changed')
                if time.monotonic()-start>MAX_WALL_SECONDS:raise TimeoutError('study_wall_budget')
                report['summary']=_summary(report['rows']);report['status']='complete';_validate(db,report,protocol,tasks)
                if time.monotonic()-start>MAX_WALL_SECONDS:raise TimeoutError('study_wall_budget')
            except BaseException as error:
                report.pop('summary',None);report.pop('verdict',None)
                report['status']='failed_consumed';report['failure']=type(error).__name__
                if isinstance(error,transport.InferenceUnavailable):
                    report['failure_reason']=error.reason;report['failure_detail']=error.detail
                if isinstance(error,transport.PromptBudgetExceeded):report['over_budget_response']={'raw_output':error.raw_output,'usage':error.usage}
                if not isinstance(error,Exception):interrupt=error
            _save(db,report)
            _validate(db,report,protocol,tasks)
            if sources()!=pins:raise ValueError('sources_changed')
            smoke._save_exact(root/'report.json',report)
            if interrupt is not None:raise interrupt
            return report


def run(directory,expected_digest,journal,**inputs):return _run(directory,expected_digest,journal,**inputs,resume_only=False)
def validate_receipt(directory,expected_digest,journal,**inputs):return _run(directory,expected_digest,journal,**inputs,resume_only=True)
