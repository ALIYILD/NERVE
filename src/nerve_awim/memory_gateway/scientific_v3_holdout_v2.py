"""Shared dry-run/slice-2 gate with timeout-only identical-request retries.

Historical slice-1 code/receipts remain replayable. No item-level export.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import time
from . import scientific_v3_holdout as old
from . import scientific_retry_transport as retry
from .contracts import MemoryScope,MemoryRequest

dev=old.dev
VERSION='scientific-v3-holdout-v2'
WORKLOAD_RULE='No observed competing process at >=5% CPU at preflight and every row boundary. OS/session/Ollama allowed; virtual machines and background compute are not exempt. Observational, not machine exclusivity or GPU-idleness proof.'


def pins():
    result=old.pins()
    for name in ('src/nerve_awim/memory_gateway/scientific_retry_transport.py',
                 'src/nerve_awim/memory_gateway/scientific_v3_holdout_v2.py',
                 'scripts/run_scientific_v3_holdout_v2.py'):
        result[name]=sha256((old.ROOT/name).read_bytes()).hexdigest()
    return result


def aggregate(rows,*,complete):
    result=old.aggregate(rows,complete=complete)
    result['version']=VERSION
    if result['status']!='complete':result['verdict']='incomplete_infrastructure'
    return result


def reclassify(directory):
    root=Path(directory).resolve()
    prior=old.verify(root) # Includes private score replay, emits no individual rows.
    if prior['status']!='failed_consumed':raise ValueError('incomplete_receipt_required')
    return dict(version=VERSION,verdict='incomplete_infrastructure',supersedes_verdict=prior['verdict'],
        prior_aggregate_sha256=sha256(dev._read(root/'aggregate-report.json')).hexdigest(),
        prior_private_report_sha256=sha256(dev._read(root/'private-report.json')).hexdigest(),
        interpretation='Infrastructure-incomplete study; neither efficacy rejection nor acceptance. Slice remains consumed.',
        model_calls=prior['model_calls'],attempted_model_calls=prior['attempted_model_calls'],
        promotion_authorized=False,prior_artifacts_rewritten=False)


def observe():
    """No command arguments captured. Observational, not scheduler isolation."""
    raw=subprocess.check_output(['ps','-axo','pid,ppid,pcpu,comm'],text=True)
    processes=[]
    for line in raw.splitlines()[1:]:
        pid,ppid,cpu,comm=line.strip().split(None,3)
        processes.append(dict(pid=int(pid),ppid=int(ppid),cpu=float(cpu),comm=comm))
    ancestors={os.getpid()}; byid={p['pid']:p for p in processes};cursor=os.getpid()
    while cursor in byid and byid[cursor]['ppid'] not in ancestors:
        cursor=byid[cursor]['ppid'];ancestors.add(cursor)
    def allowed(p):
        name=os.path.basename(p['comm']).lower()
        if any(term in name for term in ('virtualmachine','compiler','photoanalysis','mdworker','backupd')):return False
        return (p['pid'] in ancestors or p['ppid']==os.getpid()
                or p['comm'].startswith(('/System/','/usr/libexec/','/usr/sbin/','/sbin/'))
                or name.startswith(('ollama','codex')) or '/Codex.app/' in p['comm'])
    active=[dict(pid=p['pid'],name=os.path.basename(p['comm']),cpu_percent=p['cpu']) for p in processes if p['cpu']>=5 and not allowed(p)]
    return dict(competing_processes=active,qualifies=not active,
        rule=WORKLOAD_RULE,
        system_and_session_processes_present=True)


def install_guard(partition_root,bank,*,allow_slice2=False):
    blocked={partition_root/'slice1.json',partition_root/'reserve.json',bank/'holdout.json',Path(str(bank)+'.seed')}
    if not allow_slice2:blocked.add(partition_root/'slice2.json')
    def guard(event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)) and Path(os.fsdecode(args[0])).resolve() in blocked:
            raise PermissionError('sealed_holdout_read_denied')
    sys.addaudithook(guard)


def _partition(partition_root):
    p=old.read(partition_root/'preregistration.json')
    if p['source_sha256']!=old.pins():raise ValueError('slice1_source_changed')
    for name in ('slice1','slice2','reserve'):
        if sha256(dev._read(partition_root/(name+'-manifest.json'))).hexdigest()!=p['slices'][name]['manifest_sha256']:
            raise ValueError('partition_manifest_changed')
        path=partition_root/(name+'.json')
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode)!=0:raise PermissionError('partition_not_sealed')
    return p


def dry_ready(result):
    return (result['status']=='complete' and result['logical_model_calls']==160
        and result['attempts']==160 and result['timeouts']==0 and result['competing_workload_observed'] is False)


def register(directory,*,kind,partition_directory,calibration_directory,dry_directory=None):
    if kind not in ('dry','slice2'):raise ValueError('fixed_study_kind_required')
    root=Path(directory).resolve();parts=Path(partition_directory).resolve();pp=_partition(parts);bank=Path(pp['bank_directory'])
    # Registering slice2 never opens its items; first require the completed same-code dry run.
    dry=None
    if kind=='slice2':
        if dry_directory is None:raise ValueError('dry_run_required')
        dry=verify(dry_directory,install_file_guard=False)
        if not dry_ready(dry):raise ValueError('zero_timeout_160_call_dry_run_required')
    install_guard(parts,bank)
    if root==parts or root in parts.parents or parts in root.parents:raise ValueError('separate_study_directory_required')
    root.mkdir(mode=0o700,parents=False,exist_ok=False)
    protocol=dict(version=VERSION,kind=kind,model_policy_commit='cb65c81',source_sha256=pins(),
        partition_directory=str(parts),bank_directory=str(bank),calibration_directory=str(Path(calibration_directory).resolve()),
        partition_preregistration_sha256=sha256(dev._read(parts/'preregistration.json')).hexdigest(),
        seed=old.SEED,arms=old.ARMS,strata=old.STRATA,items_per_stratum=20,transport=retry.policy(),
        max_logical_calls=160,max_physical_attempts=480,max_wall_seconds=7200,
        acceptance='Complete: candidate strict total > each control and every stratum >= always_abstain; promote_proposal else retain_incumbent. Incomplete: incomplete_infrastructure.',
        ci=pp['confidence_interval'],scope_limit=pp['scope_limit'],future_bank_rule=pp['future_bank_rule'],
        reporting='stratum-level counts and derived summaries only; raw wire responses and item scores gate-private',
        workload_rule=WORKLOAD_RULE,workload_limit='No literal machine-exclusivity claim; required macOS/session/Ollama processes continue. No unrelated process is killed.',
        dry_admission='160 logical calls completed with exactly160 attempts, zero timeouts, and no observed competing workload; same harness/source hashes/transport for slice2',
        promotion_authorized=False)
    if kind=='dry':
        tasks,_,_=dev._host_inputs(bank_directory=bank,bank_manifest_sha256=pp['bank_manifest_sha256'],calibration_directory=calibration_directory)
        protocol['input_sha256']=old.write_once(root/'private-input.json',tasks)
    else:
        protocol['input_sha256']=pp['slices']['slice2']['content_sha256']
        protocol['slice_manifest_sha256']=pp['slices']['slice2']['manifest_sha256']
        protocol['dry_directory']=str(Path(dry_directory).resolve())
        protocol['dry_aggregate_sha256']=sha256(dev._read(Path(dry_directory)/'aggregate-report.json')).hexdigest()
        # Match runtime identity as well as implementation and transport.
        protocol['dry_runtime_version']=dry['runtime_version']
    old.write_once(root/'preregistration.json',protocol)
    return protocol


def _load(root):
    p=old.read(root/'preregistration.json')
    if p['version']!=VERSION or p['source_sha256']!=pins() or p['transport']!=retry.policy():raise ValueError('frozen_policy_changed')
    parts=Path(p['partition_directory']);_partition(parts)
    if sha256(dev._read(parts/'preregistration.json')).hexdigest()!=p['partition_preregistration_sha256']:raise ValueError('partition_changed')
    return p


def validate_attempts(db,rows):
    attempts=db.execute('SELECT row_index,attempt,request_sha,status,timeout,elapsed FROM attempts ORDER BY row_index,attempt').fetchall()
    requests={i:(digest,json.loads(raw)) for i,digest,raw in db.execute('SELECT row_index,request_sha,envelope FROM requests')}
    for i,(digest,env) in requests.items():
        if retry.fingerprint(env)!=digest:raise ValueError('wire_request_hash_changed')
        group=[a for a in attempts if a[0]==i]
        if not 1<=len(group)<=3 or [a[1] for a in group]!=list(range(len(group))):raise ValueError('attempt_sequence_changed')
        if any(a[3]!='timeout' for a in group[:-1]):raise ValueError('non_timeout_retry')
        if any(a[2]!=digest or a[3] not in ('complete','timeout','error','claimed') for a in group):raise ValueError('attempt_journal_changed')
        if i<len(rows) and (not rows[i]['model_calls'] or group[-1][3]!='complete'):raise ValueError('row_without_completed_attempt')
    expected={i for i,r in enumerate(rows) if r['model_calls']}
    if not expected<=requests.keys() or len(requests)-len(expected)>1:raise ValueError('logical_claim_count_changed')
    return attempts,requests


def verify(directory,*,install_file_guard=True):
    root=Path(directory).resolve();p=_load(root)
    if install_file_guard:install_guard(Path(p['partition_directory']),Path(p['bank_directory']))
    report=old.read(root/'private-report.json')
    binding=sha256(dev._read(root/'preregistration.json')).hexdigest()
    if report['protocol_sha256']!=binding or old.read(root/'consumed.json')!={'protocol_sha256':binding}:raise ValueError('claim_binding_changed')
    tasks=report['private_tasks']
    if sha256(old.encoded(tasks)).hexdigest()!=p['input_sha256']:raise ValueError('inputs_changed')
    complete=report['status']=='complete'
    if report['status'] not in ('complete','failed_consumed'):raise ValueError('terminal_receipt_required')
    old._validate_rows(tasks,report['rows'],complete)
    with sqlite3.connect((root/'claims.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('claims_corrupt')
        attempts,requests=validate_attempts(db,report['rows'])
    for i,row in enumerate(report['rows']):
        if old.read(root/f'private-row-{i:03d}.json')!=row:raise ValueError('row_artifact_changed')
    if complete and len(requests)!=160:raise ValueError('complete_call_count_changed')
    for i,(digest,env) in requests.items():
        if not 0<=i<400 or i>len(report['rows']):raise ValueError('request_index_changed')
        tid,arm=dev.schedule(tasks)[i]; task=next(t for t in tasks if t['task_id']==tid)
        prepared=dev.prepared_for(task,arm)
        # Capture frozen original payload with no network and reject after capture.
        captured=[]
        original=dev.transport.calibration._adapter
        class Capture:
            def open(self,req,*,timeout):captured.append(retry.envelope(req));raise RuntimeError('capture_only')
        from types import SimpleNamespace
        dev.transport.calibration._adapter=lambda timeout:SimpleNamespace(_opener=Capture())
        try:
            try:dev.transport.run(prepared,authorize=lambda:None,timeout_seconds=30)
            except RuntimeError:pass
        finally:dev.transport.calibration._adapter=original
        if len(captured)!=1 or retry.fingerprint(captured[0])!=digest:raise ValueError('request_differs_from_cb65c81')
        for attempt in [a for a in attempts if a[0]==i]:
            if attempt[4]!=p['transport']['per_attempt_timeout_seconds'][arm]:raise ValueError('arm_timeout_changed')
        if i<len(report['rows']):
            wire=old.read(root/f'private-wire-{i:03d}.json')
            parsed=json.loads(bytes.fromhex(wire['body_hex']))
            if wire['request_sha256']!=digest or parsed['choices'][0]['message']['content']!=report['rows'][i]['raw_output']:raise ValueError('raw_wire_changed')
    if complete and (report['metadata_before']!=report['metadata_after'] or report['version_before']!=report['version_after']):raise ValueError('runtime_changed')
    if report.get('metadata_before') not in (None,{'model':dev.pilot.MODEL,'digest':p['transport']['model_digest']}):raise ValueError('model_changed')
    result=finish_summary(report,attempts,p)
    if result!=old.read(root/'aggregate-report.json'):raise ValueError('aggregate_changed')
    return result


def finish_summary(report,attempts,p):
    result=aggregate(report['rows'],complete=report['status']=='complete')
    result.update(kind=p['kind'],logical_model_calls=sum(r['model_calls'] for r in report['rows']),
        attempts=len(attempts),timeouts=sum(a[3]=='timeout' for a in attempts),
        competing_workload_observed=any(not s['qualifies'] for s in report['workload_samples']),
        runtime_version=report.get('version_before'),wall_seconds=report['wall_seconds'],
        infrastructure_failure_type=report.get('failure_type'))
    if p['kind']=='dry':result['slice2_admission_passed']=dry_ready(result)
    return result


def run(directory):
    root=Path(directory).resolve();p=_load(root);parts=Path(p['partition_directory']);bank=Path(p['bank_directory'])
    if (root/'consumed.json').exists():raise ValueError('study_already_consumed')
    initial=observe()
    if not initial['qualifies']:
        # Admission failure before input access/consumption; safe to check again when idle.
        return dict(status='blocked_before_consumption',reason='competing_workload',observation=initial)
    if p['kind']=='slice2':
        dry=verify(p['dry_directory'],install_file_guard=False)
        if not dry_ready(dry) or sha256(dev._read(Path(p['dry_directory'])/'aggregate-report.json')).hexdigest()!=p['dry_aggregate_sha256']:raise ValueError('dry_admission_changed')
    install_guard(parts,bank,allow_slice2=p['kind']=='slice2')
    binding=sha256(dev._read(root/'preregistration.json')).hexdigest()
    old.write_once(root/'consumed.json',dict(protocol_sha256=binding))
    path=root/'private-input.json' if p['kind']=='dry' else parts/'slice2.json'
    if p['kind']=='slice2':os.chmod(path,0o600)
    try:
        raw=dev._read(path)
        if sha256(raw).hexdigest()!=p['input_sha256']:raise ValueError('inputs_changed')
        tasks=json.loads(raw)
    finally:
        if p['kind']=='slice2':os.chmod(path,0)
    report=dict(protocol_sha256=binding,status='running',private_tasks=tasks,rows=[],workload_samples=[initial])
    fd=os.open(root/'claims.sqlite',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    db=sqlite3.connect(root/'claims.sqlite');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE requests(row_index INTEGER PRIMARY KEY,request_sha TEXT,envelope TEXT)')
    db.execute('CREATE TABLE attempts(row_index INTEGER,attempt INTEGER,request_sha TEXT,status TEXT,timeout REAL,elapsed REAL,PRIMARY KEY(row_index,attempt))');db.commit()
    start=time.monotonic()
    try:
        gateway,_,proposer,reviewer,reader=dev.pilot._state(root/'authority.sqlite')
        contexts={};snapshots={}
        for i,task in enumerate(tasks):
            scope=MemoryScope('synthetic-science','model-research','v3-evaluation-'+str(i));contexts[task['task_id']]=scope
            for fact in task['evidence']:
                mid=gateway.propose(proposer,scope=scope,content=fact['content'],source_id=fact['source_id'])
                gateway.decide(reviewer,mid,scope=scope,approve=True,evaluator_id=VERSION)
            snapshots[task['task_id']]=gateway.retrieve(reader,MemoryRequest(scope,task['query'],limit=20))
        def authorize(task):
            current=gateway.retrieve(reader,MemoryRequest(contexts[task['task_id']],task['query'],limit=20));previous=snapshots[task['task_id']]
            if current.records!=previous.records or current.source_digest!=previous.source_digest or sorted((r.content,r.source_id) for r in current.records)!=sorted((r['content'],r['source_id']) for r in task['evidence']):raise PermissionError('authorized_evidence_changed')
            if pins()!=p['source_sha256']:raise ValueError('sources_changed')
            if time.monotonic()-start>7200:raise TimeoutError('wall_budget')
        report['metadata_before']=dev.metadata()
        if report['metadata_before']!={'model':dev.pilot.MODEL,'digest':p['transport']['model_digest']}:raise ValueError('model_changed')
        report['version_before']=dev.runtime_version()
        if p['kind']=='slice2' and report['version_before']!=p['dry_runtime_version']:raise ValueError('dry_runtime_changed')
        report['preload']=dev.preload()
        lookup={t['task_id']:t for t in tasks}
        for i,(tid,arm) in enumerate(dev.schedule(tasks)):
            sample=observe();report['workload_samples'].append(sample)
            if not sample['qualifies']:raise RuntimeError('competing_workload_observed')
            task=lookup[tid];authorize(task);prepared=dev.prepared_for(task,arm);calls=int(dev._route(task,arm)=='model');tick=time.monotonic()
            if calls:
                timeout=p['transport']['per_attempt_timeout_seconds'][arm]
                def call_authorize():
                    authorize(task)
                    if 7200-(time.monotonic()-start)<timeout:raise RuntimeError('insufficient_wall_budget')
                response=retry.run(prepared,authorize=call_authorize,db=db,row_index=i,root=root,registered_policy=p['transport'])
                output=response['raw_output'];usage=response['usage'];dev._usage(usage)
            else:output=dev._random_raw(task,prepared) if arm=='random' else 'ABSTAIN';usage=None
            authorize(task)
            row=dict(task_id=tid,stratum=task['stratum'],arm=arm,raw_output=output,usage=usage,model_calls=calls,
                elapsed_seconds=time.monotonic()-tick,input_sha256=prepared['input_sha256'],finish_reason=response['finish_reason'] if calls else None,
                score=dev.score(output,task,prepared))
            old.write_once(root/f'private-row-{i:03d}.json',row);report['rows'].append(row)
            if (i+1)%40==0:print(json.dumps({'completed_rows':i+1,'planned_rows':400}),flush=True)
        last=observe();report['workload_samples'].append(last)
        if not last['qualifies']:raise RuntimeError('competing_workload_observed')
        report['metadata_after']=dev.metadata();report['version_after']=dev.runtime_version()
        if report['metadata_before']!=report['metadata_after'] or report['version_before']!=report['version_after']:raise ValueError('runtime_changed')
        old._validate_rows(tasks,report['rows'],True);_load(root)
        if time.monotonic()-start>7200:raise TimeoutError('wall_budget')
        report['status']='complete'
    except BaseException as error:
        report['status']='failed_consumed';report['failure_type']=type(error).__name__
        if hasattr(error,'unscored_raw_response'):report['unscored_raw_response']=error.unscored_raw_response
    finally:
        attempts,requests=validate_attempts(db,report['rows']);db.close()
    report['wall_seconds']=time.monotonic()-start
    old.write_once(root/'private-report.json',report)
    result=finish_summary(report,attempts,p)
    old.write_once(root/'aggregate-report.json',result)
    return verify(root)
