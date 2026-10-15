"""Fixed100-item DEV comparison of candidate v3; no holdout or promotion."""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

from . import scientific_gpu_dev_transport as transport
from . import scientific_candidate_v3 as historical_transport
from . import scientific_policy_gate_v2 as policy_gate
from decimal import Decimal
from . import scientific_candidate_transport_smoke as smoke
from . import scientific_candidate_format_study as format_probe
from . import scientific_task_bank as bank_module
from .scientific_task_bank import ScientificTaskBank
from ..memory_v18 import MemoryAuthority
from .contracts import MemoryScope,MemoryRequest
from .research_supervisor import _exclusive

pilot=smoke.pilot
metadata,preload,runtime_version=transport.metadata,transport.preload,transport.runtime_version
canonical,_hash=pilot._json,pilot._hash
VERSION='scientific-gpu-strong-baseline-development-v1'
SEED=20261015
STRATA=('conflict','supported-measurement','unit-mismatch','measurement-decoy','entity-decoy')
ARMS=('baseline','candidate','always_abstain','random')
MAX_MODEL_CALLS=160
MAX_WALL_SECONDS=7200


def sources():
    pins=policy_gate.sources();pins.update(bank_module.sources());pins.update(format_probe.sources())
    for path in ('src/nerve_awim/memory_gateway/scientific_candidate_v3_study.py','scripts/run_scientific_candidate_v3_study.py',
                 'src/nerve_awim/memory_gateway/scientific_gpu_dev_transport.py',
                 'src/nerve_awim/memory_gateway/scientific_gpu_dev_study.py',
                 'scripts/run_scientific_gpu_dev_study.py'):
        pins[path]=sha256((pilot.ROOT/path).read_bytes()).hexdigest()
    return pins


def _policies(proposal,expected_digest,pins):
    return {arm:_hash(dict(version=VERSION,arm=arm,proposal=proposal,model_digest=expected_digest,seed=SEED,
        output_tokens=128,socket_timeout_seconds=30,source_sha256=pins)) for arm in ARMS}


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


def _host_inputs(bank_directory,bank_manifest_sha256,design_directory):
    bank_directory=Path(bank_directory).resolve()
    context_path=Path(design_directory)/'study-context.json'
    context=json.loads(_read(context_path))
    if (context.get('kind')!='exploratory_gpu_development' or context.get('model')!=transport.MODEL
        or context.get('baseline')!=transport.BASELINE_VERSION or context.get('candidate')!='candidate_v3'
        or context.get('holdout_authorized') is not False or context.get('promotion_authorized') is not False
        or type(context.get('pilot_history')) is not str or not context['pilot_history']):
        raise ValueError('explicit_exploratory_design_required')
    decision=dict(status='development_only',design=context)
    proposal=dict(policy='candidate_v3',baseline=transport.BASELINE_VERSION,promotion_authorized=False)
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
    if len({row['task_id'] for row in selected})!=100:raise ValueError('unique_fixed_roster_required')
    for row in selected:
        if row['split']!='dev':raise ValueError('development_only')
        prepared=transport.prepare(row['query'],row['evidence'],arm='candidate')
        if (prepared['route']=='deterministic_abstention')!=(row['stratum'] in ('conflict','unit-mismatch')):
            raise ValueError('fixed_candidate_route_mismatch')
    binding=dict(bank_manifest_sha256=bank_manifest_sha256,development_sha256=_digest(bank_directory/'dev.json'),
        design_sha256=_digest(Path(design_directory)/'study-context.json'),adjudication=decision,proposal=proposal,
        excluded_prior_input_sha256=sorted(excluded))
    return selected,proposal,binding


def prepared_for(task,arm):
    return (transport.prepare(task['query'],task['evidence'],arm=arm) if arm in ('candidate','baseline')
            else historical_transport.prepare(task['query'],task['evidence'],arm='baseline'))


def _random_raw(task,prepared):
    options=['ABSTAIN']+[f'{record["value"]}|{record["unit"]}|{alias}' for alias,record in sorted(prepared['aliases'].items())]
    index=int(sha256(f'{SEED}:random:{task["task_id"]}'.encode()).hexdigest(),16)%len(options)
    return options[index]


def score(raw,task,prepared):
    try:decoded=transport.decode(raw,prepared);formatted=True
    except ValueError:decoded=None;formatted=False
    expected=task['expected'];abstention=expected['status']=='abstain'
    answer=formatted and decoded['status']=='answer'
    value=bool(answer and not abstention and Decimal(decoded['value'])==Decimal(expected['value']))
    unit=bool(answer and not abstention and decoded['unit']==expected['unit'])
    provenance=bool(answer and not abstention and decoded['source_id']==expected['source_id'])
    if prepared['arm']=='candidate' and prepared['route']=='model' and not abstention:
        try:
            parsed=json.loads(raw,object_pairs_hook=transport.compact._object,parse_float=Decimal,parse_int=Decimal,
                parse_constant=lambda text:(_ for _ in ()).throw(ValueError('nonfinite')))
            if type(parsed) is dict:
                number=parsed.get('value')
                value=type(number) is Decimal and number.is_finite() and number==Decimal(expected['value'])
                unit=type(parsed.get('unit')) is str and parsed['unit']==expected['unit']
                alias=parsed.get('source_id');fact=prepared['aliases'].get(alias) if type(alias) is str else None
                provenance=fact is not None and fact['source_id']==expected['source_id']
        except (ValueError,TypeError,RecursionError):pass
    strict=(formatted and decoded['status']=='abstain') if abstention else bool(formatted and value and unit and provenance and decoded['entity']==expected['entity'] and decoded['measurement']==expected['measurement'])
    return dict(answer_status=decoded['status'] if formatted else None,schema_valid=transport.schema_valid(raw,prepared),format_valid=formatted,value_correct=bool(value) if not abstention else None,
        unit_correct=bool(unit) if not abstention else None,provenance_correct=bool(provenance) if not abstention else None,
        abstention_correct=bool(strict) if abstention else None,strict_correct=bool(strict))


def schedule(tasks):
    result=[]
    for index,task in enumerate(tasks):
        pair=('baseline','candidate') if index%2==0 else ('candidate','baseline')
        for arm in (*pair,'always_abstain','random'):result.append([task['task_id'],arm])
    return result


def _route(task,arm):
    if arm=='candidate' and prepared_for(task,arm)['route']=='deterministic_abstention':return 'candidate_gate'
    return 'model' if arm in ('baseline','candidate') else arm


def _usage(usage):
    if (type(usage) is not dict or set(usage)!={'prompt_tokens','completion_tokens','total_tokens'}
            or any(type(v) is not int or not 0<=v<=10000000 for v in usage.values())
            or usage['completion_tokens']>128
            or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']):raise ValueError('actual_usage_required')


def _summary(rows):
    arms=[]
    for arm in ARMS:
        chosen=[r for r in rows if r['arm']==arm]
        strata={st:dict(count=sum(r['stratum']==st for r in chosen),correct=sum(r['score']['strict_correct'] for r in chosen if r['stratum']==st),
            format_valid=sum(r['score']['format_valid'] for r in chosen if r['stratum']==st),
            answered_incorrect=sum(r['score']['answer_status']=='answer' and not r['score']['strict_correct'] for r in chosen if r['stratum']==st),
            abstained=sum(r['score']['answer_status']=='abstain' for r in chosen if r['stratum']==st)) for st in STRATA}
        for values in strata.values():values['accuracy']=values['correct']/values['count'] if values['count'] else None
        arms.append(dict(arm=arm,count=len(chosen),correct=sum(r['score']['strict_correct'] for r in chosen),
            accuracy=sum(r['score']['strict_correct'] for r in chosen)/len(chosen) if chosen else None,
            format_valid=sum(r['score']['format_valid'] for r in chosen),
            components={k:dict(correct=sum(r['score'][k] is True for r in chosen),evaluated=sum(r['score'][k] is not None for r in chosen)) for k in ('schema_valid','value_correct','unit_correct','provenance_correct','abstention_correct')},strata=strata))
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
        row=db.execute('SELECT protocol,status FROM candidate_v3_claims WHERE dataset=?',(protocol['dataset_sha256'],)).fetchone()
        if row!=(canonical(protocol),'consumed'):raise ValueError('external_claim_changed')


def _claim(journal,protocol,root):
    if not journal.exists():
        if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('external_claim_missing')
        fd=os.open(journal,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        with sqlite3.connect(journal) as db:db.execute('CREATE TABLE candidate_v3_claims(dataset TEXT PRIMARY KEY,version TEXT UNIQUE,protocol TEXT,status TEXT)')
    smoke._private(journal)
    with sqlite3.connect(journal) as db:
        db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO candidate_v3_claims VALUES(?,?,?,?)',(protocol['dataset_sha256'],VERSION,canonical(protocol),'consumed'))


def _validate(db,report,protocol,tasks):
    if (canonical(report['protocol'])!=canonical(protocol) or report['status'] not in ('complete','failed_consumed')
            or type(report['rows']) is not list or len(report['rows'])>400
            or any(type(report[k]) is not int or not 0<=report[k]<=bound for k,bound in
                [('model_attempts',160),('metadata_attempts',2),('version_attempts',2),('preload_attempts',1)])
            or any(report[k] is not False for k in ('holdout_accessed','promotion_authorized','model_weights_trained','efficacy_established'))
            or report['rejection_receipts_created']!=0 or type(report['rejection_receipts_created']) is not int):raise ValueError('terminal_dev_receipt_invalid')
    by_id={task['task_id']:task for task in tasks};order=schedule(tasks);completed_claims=[]
    for index,row in enumerate(report['rows']):
        task_id,arm=order[index];task=by_id[task_id];prepared=prepared_for(task,arm);route=_route(task,arm)
        if (row['task_id']!=task_id or row['arm']!=arm or row['stratum']!=task['stratum'] or row['route']!=route
                or row['input_sha256']!=prepared['input_sha256'] or row['task_content_sha256']!=task['content_sha256']
                or row['policy_sha256']!=protocol['policies'][arm] or canonical(row['score'])!=canonical(score(row['raw_output'],task,prepared))
                or type(row['elapsed_seconds']) not in (int,float) or not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds']<0
                or type(row['model_calls']) is not int or row['model_calls']!=(1 if route=='model' else 0)
                or type(row['raw_output']) is not str or not 1<=len(row['raw_output'])<=16384):raise ValueError('dev_row_changed')
        if route=='model':
            if type(row['model_sampling_seed']) is not int or row['model_sampling_seed']!=SEED:raise ValueError('requested_model_seed_changed')
            _usage(row['usage'])
            if row['finish_reason'] not in ('stop','length'):raise ValueError('model_finish_reason_required')
            completed_claims.append((len(completed_claims),task_id,arm,index,'complete'))
        else:
            raw=_random_raw(task,prepared) if arm=='random' else 'ABSTAIN'
            if row['finish_reason'] is not None or row['usage'] is not None or row['model_sampling_seed'] is not None or row['raw_output']!=raw:raise ValueError('zero_call_control_changed')
    claims=db.execute('SELECT ordinal,task,arm,row_index,status FROM calls ORDER BY ordinal').fetchall()
    if not len(completed_claims)<=report['model_attempts']<=len(completed_claims)+1:raise ValueError('model_attempt_count_changed')
    expected=list(completed_claims)
    if report['model_attempts']>len(completed_claims):
        index=len(report['rows']);task_id,arm=order[index]
        if _route(by_id[task_id],arm)!='model':raise ValueError('unexpected_model_claim')
        expected.append((len(completed_claims),task_id,arm,index,'claimed'))
    if claims!=expected:raise ValueError('per_call_claims_changed')
    if report['model_attempts'] and (report.get('metadata_before')!={'model':transport.MODEL,'digest':protocol['expected_digest']}
            or report['metadata_attempts']<1 or report['version_attempts']<1 or report['preload_attempts']!=1
            or type(report.get('version_before')) is not str or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before'])
            or not _preload_valid(report.get('preload'))):
        raise ValueError('predispatch_identity_changed')
    if 'preload' in report and not _preload_valid(report['preload']):raise ValueError('preload_measurement_invalid')
    if report['status']=='failed_consumed' and ('summary' in report or 'verdict' in report):raise ValueError('failed_summary_forbidden')
    if 'unscored_raw_response' in report:
        failed=report['unscored_raw_response'];_usage(failed['usage'])
        if (report['status']!='failed_consumed' or report['model_attempts']!=len(completed_claims)+1
                or set(failed)!={'raw_output','usage','finish_reason','reason'} or failed['reason']!='post_response_authorization_failed'
                or failed['finish_reason'] not in ('stop','length') or type(failed['raw_output']) is not str or not 1<=len(failed['raw_output'])<=16384):raise ValueError('invalid_unscored_response')
    if report['status']=='complete':
        if (len(report['rows'])!=400 or (report['model_attempts'],report['metadata_attempts'],report['version_attempts'],report['preload_attempts'])!=(160,2,2,1)
                or report['metadata_after']!=report['metadata_before'] or report['version_after']!=report['version_before']
                or canonical(report['summary'])!=canonical(_summary(report['rows']))):raise ValueError('complete_dev_receipt_invalid')
    elif type(report.get('failure')) is not str or not re.fullmatch('[A-Za-z0-9_]{1,80}',report['failure']):raise ValueError('failure_evidence_required')
    if 'failure_reason' in report or 'failure_detail' in report:
        raise ValueError('unexpected_failure_fields')
    _external(Path(protocol['journal']),protocol)


def _run(directory,expected_digest,journal,*,bank_directory,bank_manifest_sha256,design_directory,resume_only,prepare_only=False):
    if not _identity(expected_digest) or not _identity(bank_manifest_sha256):raise ValueError('full_identity_pins_required')
    root=Path(directory).resolve();journal=Path(journal).resolve()
    evidence_roots=[Path(p).resolve() for p in (bank_directory,design_directory)]
    if any(root==p or root in p.parents or p in root.parents or journal==p or p in journal.parents or journal in p.parents for p in evidence_roots):
        raise ValueError('separate_study_and_evidence_paths_required')
    if resume_only and not (root/'claim.sqlite').is_file():raise ValueError('existing_terminal_receipt_required')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_study_directory_required')
    if journal==root or root in journal.parents:raise ValueError('external_claim_journal_required')
    paths=dict(bank_directory=str(Path(bank_directory).resolve()),bank_manifest_sha256=bank_manifest_sha256,
        design_directory=str(Path(design_directory).resolve()))
    tasks,proposal,inputs=_host_inputs(**paths);pins=sources()
    policies=_policies(proposal,expected_digest,pins)
    roster=[dict(task_id=t['task_id'],stratum=t['stratum'],content_sha256=t['content_sha256']) for t in tasks]
    protocol=dict(version=VERSION,directory=str(root),journal=str(journal),expected_digest=expected_digest,model=transport.MODEL,origin=transport.ORIGIN,
        sources=pins,paths=paths,inputs=inputs,seed=SEED,roster=roster,dataset_sha256=_hash(roster),policies=policies,
        schedule=schedule(tasks),max_model_calls=160,max_wall_seconds=MAX_WALL_SECONDS,
        max_output_tokens=128,socket_timeout_seconds=30,development_reuse_allowed=True,
        prediction="Candidate v3 may tie or improve over a schema-constrained six-field baseline. Ties retain baseline. No holdout or promotion.",
        scoring="Candidate JSON components independently parsed without repair; baseline six-field JSON strict-parsed; zero-call controls retain original triplet decoding. Numeric Decimal equivalence; exact unit/source/entity/measurement. Value/unit/provenance scores null on abstention tasks; abstention correctness separate.",
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
            if prepare_only:
                if old[1] is not None:raise ValueError('study_already_started')
                smoke._save_exact(root/'preregistration.json',protocol)
                return protocol
            if not created and old[1] is None and not (root/'preregistration.json').is_file():raise ValueError('incomplete_registration_consumed')
            if (root/'preregistration.json').exists() and _read(root/'preregistration.json')!=(canonical(protocol)+'\n').encode():raise ValueError('preregistration_changed')
            if not created and old[1] is not None:
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
            if resume_only:raise ValueError('existing_terminal_receipt_required')
            smoke._save_exact(root/'preregistration.json',protocol)
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
                if report['metadata_before']!={'model':transport.MODEL,'digest':expected_digest}:raise ValueError('model_identity_mismatch')
                report['version_attempts']=1;_save(db,report);report['version_before']=runtime_version()
                if type(report['version_before']) is not str or not re.fullmatch('[A-Za-z0-9._+-]{1,80}',report['version_before']):raise ValueError('runtime_version_required')
                report['preload_attempts']=1;_save(db,report);report['preload']=preload()
                if not _preload_valid(report['preload']):raise ValueError('preload_measurement_invalid')
                for row_index,(task_id,arm) in enumerate(schedule(tasks)):
                    task=by_id[task_id];authorize(task);prepared=prepared_for(task,arm);route=_route(task,arm)
                    usage=None;calls=0;call_index=None;row_start=time.perf_counter()
                    if route=='model':
                        if MAX_WALL_SECONDS-(time.monotonic()-start)<30:raise TimeoutError('remaining_wall_budget_below_socket_allowance')
                        call_index=report['model_attempts'];report['model_attempts']+=1
                        if report['model_attempts']>160:raise ValueError('model_budget_exhausted')
                        _save(db,report,claim=(call_index,task_id,arm,row_index))
                        response=transport.run(prepared,authorize=lambda:authorize(task),timeout_seconds=30)
                        if (response['model']!=transport.MODEL or response['origin']!=transport.ORIGIN or response['input_sha256']!=prepared['input_sha256']
                                or type(response['model_calls']) is not int or response['model_calls']!=1
                                or response['review_required'] is not True or response['synthetic_only'] is not True
                                or type(response['model_sampling_seed']) is not int or response['model_sampling_seed']!=SEED
                                or response['finish_reason'] not in ('stop','length')):raise ValueError('measured_transport_required')
                        raw=response['raw_output'];usage=response['usage'];_usage(usage)
                        if type(raw) is not str or not 1<=len(raw)<=16384:raise ValueError('bounded_raw_output_required')
                        calls=1
                    else:raw=_random_raw(task,prepared) if arm=='random' else 'ABSTAIN'
                    authorize(task)
                    row=dict(task_id=task_id,stratum=task['stratum'],arm=arm,route=route,raw_output=raw,usage=usage,model_calls=calls,
                        model_sampling_seed=SEED if calls else None,finish_reason=response['finish_reason'] if calls else None,
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
                if hasattr(error,'unscored_raw_response'):report['unscored_raw_response']=error.unscored_raw_response
                if not isinstance(error,Exception):interrupt=error
            _save(db,report)
            _validate(db,report,protocol,tasks)
            fresh_tasks,_,fresh_inputs=_host_inputs(**paths)
            if sources()!=pins or canonical(fresh_tasks)!=canonical(tasks) or canonical(fresh_inputs)!=canonical(inputs):raise ValueError('sources_changed')
            smoke._save_exact(root/'report.json',report)
            if interrupt is not None:raise interrupt
            return report


def run(directory,expected_digest,journal,**inputs):return _run(directory,expected_digest,journal,**inputs,resume_only=False)
def validate_receipt(directory,expected_digest,journal,**inputs):return _run(directory,expected_digest,journal,**inputs,resume_only=True)

def register(directory,expected_digest,journal,**inputs):return _run(directory,expected_digest,journal,**inputs,resume_only=False,prepare_only=True)
