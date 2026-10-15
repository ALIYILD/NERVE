"""One-use private holdout gate. No generator, proposal execution, or promotion.

File permissions and Python audit guards protect against ordinary reads, not the
trusted owner/root changing permissions. Aggregate export never carries rows.
"""
from collections import Counter
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time

from . import scientific_candidate_v3_study as dev
from .scientific_task_bank import ScientificTaskBank
from ..memory_v18 import MemoryAuthority
from .contracts import MemoryRequest, MemoryScope

VERSION = 'scientific-v3-holdout-slice1-v1'
SEED = 20261015
STRATA = dev.STRATA
ARMS = dev.ARMS
ROOT = dev.pilot.ROOT
UNTESTED = ('multi-source-agreement', 'stale-vs-current')
MANIFEST_PIN = 'e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6'


def encoded(value):
    return (dev.canonical(value) + '\n').encode()


def write_once(path, value, mode=0o600):
    raw = encoded(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    return sha256(raw).hexdigest()


def read(path):
    return json.loads(dev._read(path))


def pins():
    result = dev.sources()
    for name in ('src/nerve_awim/memory_gateway/scientific_v3_holdout.py',
                 'scripts/run_scientific_v3_holdout.py'):
        result[name] = sha256((ROOT / name).read_bytes()).hexdigest()
    return result


def partition_rows(rows):
    """Data-only partition; no inference, scoring, candidate ranking or answer use."""
    if len(rows) != 300 or len({r['task_id'] for r in rows}) != 300:
        raise ValueError('unique_300_required')
    expected = {s: 43 for s in (*STRATA, 'multi-source-agreement')}
    expected['stale-vs-current'] = 42
    if dict(Counter(r['stratum'] for r in rows)) != expected:
        raise ValueError('original_seven_strata_required')
    groups = {'slice1': [], 'slice2': [], 'reserve': []}
    for s in STRATA:
        pool = sorted((r for r in rows if r['stratum'] == s),
                      key=lambda r: (sha256(f'{SEED}:partition:{r["task_id"]}'.encode()).hexdigest(), r['task_id']))
        groups['slice1'].extend(pool[:20]); groups['slice2'].extend(pool[20:40])
        groups['reserve'].extend(pool[40:])
    groups['reserve'].extend(r for r in rows if r['stratum'] in UNTESTED)
    for group in groups.values():
        group.sort(key=lambda r: (sha256(f'{SEED}:order:{r["task_id"]}'.encode()).hexdigest(), r['task_id']))
    if any(len(group) != 100 for group in groups.values()):
        raise ValueError('three_disjoint_100_required')
    return groups


def register(directory, bank_directory):
    root, bank = Path(directory).resolve(), Path(bank_directory).resolve()
    if root == bank or root in bank.parents or bank in root.parents:
        raise ValueError('separate_private_directories_required')
    # All policy pins and rules are frozen before the trusted partitioner opens items.
    previous = json.loads((ROOT / 'docs/galahad/evidence/scientific-candidate-v3-study.json').read_bytes())
    if previous['status'] != 'complete' or previous['summary']['verdict'] != 'candidate_requires_review':
        raise ValueError('completed_v3_development_required')
    current = pins()
    if any(current.get(k) != v for k, v in previous['protocol']['sources'].items()):
        raise ValueError('development_policy_sources_changed')
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    protocol = dict(version=VERSION, seed=SEED, arms=ARMS, strata=STRATA, items_per_stratum=20,
        bank_directory=str(bank), bank_manifest_sha256=MANIFEST_PIN,
        development_receipt_sha256=sha256((ROOT/'docs/galahad/evidence/scientific-candidate-v3-study.json').read_bytes()).hexdigest(),
        expected_digest=previous['protocol']['expected_digest'], model=dev.pilot.MODEL,
        source_sha256=current, max_calls=160, timeout_seconds=30, max_wall_seconds=7200,
        max_output_tokens=128, temperature=0,
        partition_rule='sha256(seed:partition:task_id) within stratum: first20 slice1,next20 slice2,remainder reserve; no answer-based selection',
        order_rule='sha256(seed:order:task_id); alternate model arms per item as development',
        acceptance='candidate strict total > each of baseline,always_abstain,random; every candidate stratum >= always_abstain; incomplete study retains incumbent',
        confidence_interval='Two-sided 95% Wilson score interval, z=1.959963984540054, strict proportion for every arm/stratum; descriptive marginal intervals, no multiplicity adjustment or significance gate',
        scoring='Reuse unchanged development scoring: value,unit,provenance,strict separately; abstention components N/A',
        public_disclosure='stratum-level counts and derived summaries only; no IDs, prompts, raw outputs, per-item scores or answer keys',
        unused_strata=list(UNTESTED),
        scope_limit='Both unused strata must be studied before any claim beyond these five strata. Same generation templates as development; not unseen-template generalization.',
        future_bank_rule='After slice2 is consumed, generate and seal fresh bank v2 with a new private seed BEFORE designing the next candidate.',
        future_hypothesis='Recency and multi-source agreement are untested gaps, not demonstrated failures. Existing v3 filters current=false; obtain aggregate reserve evidence in a separately registered future study, not now.',
        promotion_authorized=False, boundary='Trusted host; mode000 unused files plus runner audit guard. Not protection against owner/root or arbitrary same-user code changing permissions.')
    write_once(root/'registration-rules.json', protocol)
    authority = MemoryAuthority()
    actor = authority.issue('synthetic-science', 'holdout-partitioner', permissions=('read','approve'))
    source = ScientificTaskBank(bank, authority, expected_manifest_hash=MANIFEST_PIN,
        tenant_id='synthetic-science', generator_agent_id='generator', gate_actor=actor)
    groups = partition_rows(source.holdout(actor))
    manifests = {}
    for name, rows in groups.items():
        digest = write_once(root/(name+'.json'), rows)
        os.chmod(root/(name+'.json'), 0)
        manifest = dict(version=VERSION, name=name, count=100, counts=dict(Counter(r['stratum'] for r in rows)),
            content_sha256=digest, parent_manifest_sha256=MANIFEST_PIN,
            parent_holdout_sha256=json.loads((bank/'manifest.json').read_bytes())['files']['holdout'],
            partition_rule=protocol['partition_rule'], seed=SEED)
        md = write_once(root/(name+'-manifest.json'), manifest)
        manifests[name] = dict(manifest_sha256=md, **manifest)
    # Preserve original bytes, deny ordinary reads of the combined source as well.
    os.chmod(bank/'holdout.json', 0)
    protocol['slices'] = manifests
    write_once(root/'preregistration.json', protocol)
    return protocol


def guard(root, bank):
    root, bank = Path(root).resolve(), Path(bank).resolve()
    blocked = {root/'slice2.json', root/'reserve.json', bank/'holdout.json', Path(str(bank)+'.seed')}
    def audit(event, args):
        if event == 'open' and args and isinstance(args[0], (str,bytes,os.PathLike)):
            if Path(os.fsdecode(args[0])).resolve() in blocked:
                raise PermissionError('sealed_holdout_read_denied')
    sys.addaudithook(audit)


def wilson(k, n):
    if not 0 <= k <= n or n <= 0:
        raise ValueError('binomial_counts_required')
    z = 1.959963984540054; p = k/n; d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return [max(0., c-h), min(1., c+h)]


def aggregate(rows, *, complete):
    arms = {}
    for arm in ARMS:
        strata = {}
        for s in STRATA:
            subset = [r for r in rows if r['arm']==arm and r['stratum']==s]
            correct = sum(r['score']['strict_correct'] for r in subset)
            strata[s] = dict(n=len(subset), strict_correct=correct,
                strict_ci95=wilson(correct,len(subset)) if subset else None,
                model_calls=sum(r['model_calls'] for r in subset),
                components={k:dict(correct=sum(r['score'][k] is True for r in subset),
                    n=sum(r['score'][k] is not None for r in subset)) for k in
                    ('value_correct','unit_correct','provenance_correct','abstention_correct','schema_valid')})
        arms[arm] = strata
    totals = {a:sum(s['strict_correct'] for s in strata.values()) for a,strata in arms.items()}
    full = all(v['n']==20 for strata in arms.values() for v in strata.values())
    passed = complete and full and all(totals['candidate']>totals[a] for a in ('baseline','always_abstain','random')) and all(
        arms['candidate'][s]['strict_correct'] >= arms['always_abstain'][s]['strict_correct'] for s in STRATA)
    return dict(version=VERSION, status='complete' if complete and full else 'failed_consumed',
        verdict='promote_proposal' if passed else 'retain_incumbent', arms=arms, strict_totals=totals,
        model_calls=sum(r['model_calls'] for r in rows), promotion_authorized=False,
        unused_strata=list(UNTESTED), item_level_evidence_exported=False,
        interpretation='Fixed synthetic instance holdout; reused generation templates. Human decides promotion; no claim on unused strata.')


def _load_protocol(root):
    p = read(root/'preregistration.json')
    if p['version'] != VERSION or p['source_sha256'] != pins():
        raise ValueError('frozen_sources_changed')
    if {k:v for k,v in p.items() if k!='slices'} != read(root/'registration-rules.json'):
        raise ValueError('registration_rules_changed')
    bank = Path(p['bank_directory'])
    if sha256(dev._read(bank/'manifest.json')).hexdigest() != p['bank_manifest_sha256']:
        raise ValueError('bank_manifest_changed')
    for name in ('slice1','slice2','reserve'):
        raw = dev._read(root/(name+'-manifest.json'))
        if sha256(raw).hexdigest()!=p['slices'][name]['manifest_sha256']:
            raise ValueError('slice_manifest_changed')
    for path in (root/'slice2.json',root/'reserve.json',bank/'holdout.json'):
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0:
            raise PermissionError('unused_holdout_not_sealed')
    return p


def _validate_rows(tasks, rows, complete):
    schedule = dev.schedule(tasks); lookup={t['task_id']:t for t in tasks}
    if len(rows)>400 or (complete and len(rows)!=400):raise ValueError('row_count_changed')
    for i, row in enumerate(rows):
        task_id, arm = schedule[i]; task=lookup[task_id]; prepared=dev.prepared_for(task,arm)
        route=dev._route(task,arm)
        if (row['task_id']!=task_id or row['arm']!=arm or row['stratum']!=task['stratum']
            or row['model_calls']!=int(route=='model') or row['input_sha256']!=prepared['input_sha256']
            or row['score']!=dev.score(row['raw_output'],task,prepared)):
            raise ValueError('private_row_changed')
        if route=='model':
            dev._usage(row['usage'])
            if row['finish_reason'] not in ('stop','length'):raise ValueError('finish_reason_required')
        elif row['raw_output'] != (dev._random_raw(task,prepared) if arm=='random' else 'ABSTAIN'):
            raise ValueError('control_changed')


def verify(directory):
    root=Path(directory).resolve(); p=_load_protocol(root); guard(root,Path(p['bank_directory']))
    report=read(root/'private-report.json')
    if report['protocol_sha256'] != sha256(dev._read(root/'preregistration.json')).hexdigest():
        raise ValueError('protocol_changed')
    tasks=report['private_tasks']
    if read(root/'consumed.json') != {'protocol_sha256':report['protocol_sha256']}:
        raise ValueError('consumed_binding_changed')
    if sha256(encoded(tasks)).hexdigest()!=p['slices']['slice1']['content_sha256']:
        raise ValueError('private_tasks_changed')
    if report['status'] not in ('complete','failed_consumed'):raise ValueError('terminal_status_required')
    complete=report['status']=='complete'; _validate_rows(tasks, report['rows'], complete)
    with sqlite3.connect((root/'claims.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('claims_corrupt')
        claims=db.execute('SELECT row_index,status FROM calls ORDER BY row_index').fetchall()
    for i,row in enumerate(report['rows']):
        if read(root/f'private-row-{i:03d}.json')!=row:raise ValueError('private_row_artifact_changed')
    done=[(i,'complete') for i,r in enumerate(report['rows']) if r['model_calls']]
    if complete and claims!=done:raise ValueError('call_claims_changed')
    if not len(done)<=len(claims)<=len(done)+1:raise ValueError('attempt_count_changed')
    if complete and (report['metadata_before']!=report['metadata_after'] or report['metadata_before']!={'model':p['model'],'digest':p['expected_digest']} or report['version_before']!=report['version_after']):
        raise ValueError('model_identity_changed')
    result=aggregate(report['rows'],complete=complete)
    result['slice1_manifest_sha256']=p['slices']['slice1']['manifest_sha256']
    result['attempted_model_calls']=len(claims)
    if read(root/'aggregate-report.json')!=result:raise ValueError('aggregate_changed')
    return result


def run(directory):
    root=Path(directory).resolve(); p=_load_protocol(root); bank=Path(p['bank_directory']); guard(root,bank)
    # Permanent one-use claim before opening slice1. No resume/retry path.
    write_once(root/'consumed.json',dict(protocol_sha256=sha256(dev._read(root/'preregistration.json')).hexdigest()))
    os.chmod(root/'slice1.json',0o600)
    try:
        raw=dev._read(root/'slice1.json')
        if sha256(raw).hexdigest()!=p['slices']['slice1']['content_sha256']:raise ValueError('slice1_changed')
        tasks=json.loads(raw)
    finally:os.chmod(root/'slice1.json',0)
    report=dict(protocol_sha256=sha256(dev._read(root/'preregistration.json')).hexdigest(),
        status='running',private_tasks=tasks,rows=[])
    fd=os.open(root/'claims.sqlite',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    db=sqlite3.connect(root/'claims.sqlite');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE calls(row_index INTEGER PRIMARY KEY,status TEXT)');db.commit()
    start=time.monotonic()
    try:
        gateway,_,proposer,reviewer,reader=dev.pilot._state(root/'authority.sqlite')
        contexts={}; snapshots={}
        for i,task in enumerate(tasks):
            scope=MemoryScope('synthetic-science','model-research','holdout-slice1-'+str(i)); contexts[task['task_id']]=scope
            for fact in task['evidence']:
                mid=gateway.propose(proposer,scope=scope,content=fact['content'],source_id=fact['source_id'])
                gateway.decide(reviewer,mid,scope=scope,approve=True,evaluator_id=VERSION)
            snapshots[task['task_id']]=gateway.retrieve(reader,MemoryRequest(scope,task['query'],limit=20))
        def authorize(task):
            current=gateway.retrieve(reader,MemoryRequest(contexts[task['task_id']],task['query'],limit=20))
            old=snapshots[task['task_id']]
            if current.records!=old.records or current.source_digest!=old.source_digest or sorted((r.content,r.source_id) for r in current.records)!=sorted((r['content'],r['source_id']) for r in task['evidence']):
                raise PermissionError('authorized_evidence_changed')
            if pins()!=p['source_sha256']:raise ValueError('sources_changed')
            if time.monotonic()-start>7200:raise TimeoutError('wall_budget')
        report['metadata_before']=dev.metadata()
        if report['metadata_before']!={'model':p['model'],'digest':p['expected_digest']}:raise ValueError('model_changed')
        report['version_before']=dev.runtime_version();report['preload']=dev.preload()
        lookup={t['task_id']:t for t in tasks}
        for i,(task_id,arm) in enumerate(dev.schedule(tasks)):
            task=lookup[task_id];authorize(task);prepared=dev.prepared_for(task,arm);route=dev._route(task,arm)
            usage=None;calls=int(route=='model');response=None;tick=time.monotonic()
            if calls:
                if 7200-(time.monotonic()-start)<30:raise TimeoutError('remaining_wall_budget')
                db.execute('INSERT INTO calls VALUES(?,?)',(i,'claimed'));db.commit()
                response=dev.transport.run(prepared,authorize=lambda:authorize(task),timeout_seconds=30)
                if response['model']!=p['model'] or response['model_sampling_seed']!=SEED or response['input_sha256']!=prepared['input_sha256']:raise ValueError('transport_identity_changed')
                output=response['raw_output'];usage=response['usage'];dev._usage(usage)
            else:output=dev._random_raw(task,prepared) if arm=='random' else 'ABSTAIN'
            authorize(task)
            row=dict(task_id=task_id,stratum=task['stratum'],arm=arm,raw_output=output,usage=usage,model_calls=calls,
                elapsed_seconds=time.monotonic()-tick,input_sha256=prepared['input_sha256'],
                finish_reason=response['finish_reason'] if response else None,score=dev.score(output,task,prepared))
            # Durable private per-row artifact before marking call complete.
            write_once(root/f'private-row-{i:03d}.json',row)
            report['rows'].append(row)
            if calls:db.execute("UPDATE calls SET status='complete' WHERE row_index=?",(i,));db.commit()
            if (i+1)%40==0:print(json.dumps({'completed_rows':i+1,'planned_rows':400}),flush=True)
        report['metadata_after']=dev.metadata();report['version_after']=dev.runtime_version()
        if report['metadata_after']!=report['metadata_before'] or report['version_after']!=report['version_before']:raise ValueError('runtime_changed')
        _validate_rows(tasks,report['rows'],True);_load_protocol(root)
        if time.monotonic()-start>7200:raise TimeoutError('wall_budget')
        report['status']='complete'
    except BaseException as error:
        report['status']='failed_consumed';report['failure_type']=type(error).__name__
        if hasattr(error,'unscored_raw_response'):report['unscored_raw_response']=error.unscored_raw_response
    finally:
        attempts=db.execute('SELECT COUNT(*) FROM calls').fetchone()[0];db.close()
    report['wall_seconds']=time.monotonic()-start
    write_once(root/'private-report.json',report)
    result=aggregate(report['rows'],complete=report['status']=='complete')
    result['slice1_manifest_sha256']=p['slices']['slice1']['manifest_sha256'];result['attempted_model_calls']=attempts
    write_once(root/'aggregate-report.json',result)
    return verify(root)
