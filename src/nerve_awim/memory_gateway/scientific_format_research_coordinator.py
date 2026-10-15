"""Finite format-research graph: adopt failed format, probe once, retain or review.

This coordinator never retries child inference and cannot promote a candidate.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from . import scientific_candidate_transport_smoke as smoke
from . import scientific_candidate_format_study as study
from .scientific_episode_import import canonical, _save_exact
from .scientific_structured_tasks import parse
from .research_supervisor import _exclusive

VERSION='scientific-format-research-coordinator-v1'


def sources():
    pins=smoke.sources();pins.update(study.sources())
    for name in ('src/nerve_awim/memory_gateway/scientific_format_research_coordinator.py','scripts/run_scientific_format_research.py'):
        pins[name]=sha256((smoke.pilot.ROOT/name).read_bytes()).hexdigest()
    return pins


def _read(path,limit=2*1024*1024):
    smoke._private(path)
    with path.open('rb') as stream:raw=stream.read(limit+1)
    if len(raw)>limit:raise ValueError('bounded_research_artifact_required')
    return raw


def adopt(directory,journal,expected_digest):
    """Validate the complete predecessor read-only; never call smoke.run."""
    root,journal=Path(directory).resolve(),Path(journal).resolve()
    if not root.is_dir() or stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_completed_smoke_required')
    path=root/'claim.sqlite';smoke._private(path)
    pins=smoke.sources()
    protocol=dict(version=smoke.VERSION,directory=str(root),journal=str(journal),model=smoke.pilot.MODEL,origin=smoke.pilot.ORIGIN,
        expected_digest=expected_digest,source_sha256=pins,config=dict(smoke.candidates.SPACE['conflict_check']),query=smoke.QUERY,evidence=smoke.evidence(),
        max_model_calls=1,max_metadata_calls=2,max_preload_calls=1,max_version_calls=2,timeout_seconds=90,max_output_tokens=128,constrained=False)
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('smoke_claim_corrupt')
        rows=db.execute('SELECT protocol,report,digest FROM attempt').fetchall()
    if (len(rows)!=1 or rows[0][0]!=canonical(protocol) or rows[0][1] is None
            or sha256(rows[0][1].encode()).hexdigest()!=rows[0][2]):raise ValueError('complete_smoke_receipt_required')
    report=json.loads(rows[0][1]);smoke._validate_common(report,protocol);smoke._validate_complete(report,protocol)
    smoke._verify_external(journal,protocol)
    if (_read(root/'identity.json')!=(canonical(protocol)+'\n').encode()
            or _read(root/'report.json')!=(canonical(report)+'\n').encode() or smoke.sources()!=pins):
        raise ValueError('smoke_published_receipt_changed')
    return report


def decision(report):
    if report['status']!='complete':raise ValueError('completed_format_probe_required')
    rows=report['rows'];tasks={row['task_id'] for row in rows}
    if len(rows)!=4 or len(tasks)!=2:raise ValueError('fixed_four_pair_roster_required')
    indexed={}
    for row in rows:
        arm=row['constrained']
        if type(arm) is not bool or (row['task_id'],arm) in indexed:raise ValueError('fixed_paired_arms_required')
        for key in ('schema_valid','format_valid','strict_correct'):
            if type(row['score'][key]) is not bool:raise ValueError('boolean_probe_metrics_required')
        indexed[row['task_id'],arm]=row
    if set(indexed)!={(task,arm) for task in tasks for arm in (False,True)}:raise ValueError('fixed_paired_arms_required')
    totals={arm:{key:sum(indexed[t,arm]['score'][key] for t in tasks) for key in ('format_valid','strict_correct')} for arm in (False,True)}
    def wrong_answer(row):
        try:parsed=parse(row['response']['raw_output'])
        except ValueError:return False
        return parsed['status']=='answer' and not row['score']['strict_correct']
    no_new_wrong=all(not wrong_answer(indexed[t,True]) or wrong_answer(indexed[t,False]) for t in tasks)
    gain=(totals[True]['format_valid']>totals[False]['format_valid']
          and totals[True]['strict_correct']>=totals[False]['strict_correct'] and no_new_wrong)
    return dict(unrestricted=totals[False],constrained=totals[True],no_new_wrong_answers=no_new_wrong,
        observed_probe_gain=gain,next_action='candidate_requires_independent_evaluation' if gain else 'retain_baseline',
        interpretation='Two paired capability probes; no efficacy or general improvement established.')


def _base_report(config):
    return dict(protocol=config,status='blocked',promotion_authorized=False,efficacy_established=False,
        model_weights_trained=False,automatic_retry=False,goal_achieved=False,new_model_call_budget=4)


def _validate_terminal(report,config,status,child_result=None):
    expected=_base_report(config)
    if status=='complete':
        gate=decision(child_result)
        expected.update(status=gate['next_action'],decision=gate,
            study_sha256=sha256(canonical(child_result).encode()).hexdigest())
    elif status=='failed_consumed':
        failure=report.get('failure')
        if type(failure) is not str or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,79}',failure):raise ValueError('bounded_failure_required')
        expected['failure']=failure
    else:raise ValueError('terminal_status_required')
    if canonical(report)!=canonical(expected):raise ValueError('coordinator_terminal_receipt_changed')


def _claim_read(journal,identity):
    smoke._private(journal)
    with sqlite3.connect(journal.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('coordinator_claim_corrupt')
        return db.execute('SELECT protocol,status,report,digest FROM format_research WHERE identity=?',(identity,)).fetchone()


def run(directory,journal,smoke_directory,smoke_journal,study_directory,study_journal,expected_digest):
    if type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}',expected_digest):raise ValueError('full_model_digest_required')
    paths=[Path(p).resolve() for p in (directory,journal,smoke_directory,smoke_journal,study_directory,study_journal)]
    root,ledger,parent,parent_ledger,child,child_ledger=paths
    dirs=(root,parent,child);journals=(ledger,parent_ledger,child_ledger)
    if len(set(paths))!=6 or any(a in b.parents for a in dirs for b in dirs if a!=b) or any(d in j.parents for d in dirs for j in journals):
        raise ValueError('distinct_external_research_paths_required')
    original=adopt(parent,parent_ledger,expected_digest)
    if original['score']['format_valid'] is not False:raise ValueError('completed_format_failure_required')
    predecessor_hash=sha256(canonical(original).encode()).hexdigest()
    identity=sha256((VERSION+predecessor_hash).encode()).hexdigest()
    config=dict(version=VERSION,paths=[str(p) for p in paths],expected_digest=expected_digest,source_sha256=sources(),
        predecessor_sha256=predecessor_hash,max_new_model_calls=4,nodes=['adopt_completed_format_failure','fixed_paired_format_probe','review_decision'])
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if stat.S_IMODE(root.stat().st_mode)!=0o700:raise ValueError('private_coordinator_required')
    with _exclusive(root):
        if not ledger.exists():
            if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('coordinator_claim_missing')
            fd=os.open(ledger,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
            with sqlite3.connect(ledger) as db:db.execute('CREATE TABLE format_research(identity TEXT PRIMARY KEY,protocol TEXT,status TEXT,report TEXT,digest TEXT)')
        old=_claim_read(ledger,identity);fresh=old is None
        if fresh:
            if any(p.name!='supervisor.lock' for p in root.iterdir()):raise ValueError('coordinator_claim_missing')
            with sqlite3.connect(ledger) as db:
                db.execute('INSERT INTO format_research VALUES(?,?,?,NULL,NULL)',(identity,canonical(config),'claimed'))
        elif old[0]!=canonical(config):raise ValueError('coordinator_protocol_changed')
        if not fresh and old[1] in ('complete','failed_consumed'):
            if old[2] is None or sha256(old[2].encode()).hexdigest()!=old[3]:raise ValueError('coordinator_receipt_corrupt')
            report=json.loads(old[2])
            if _read(root/'report.json')!=(old[2]+'\n').encode():raise ValueError('coordinator_output_changed')
            validated=None
            if old[1]=='complete':
                validated=study.validate_receipt(child,expected_digest,child_ledger)
                if report['study_sha256']!=sha256(canonical(validated).encode()).hexdigest() or report['decision']!=decision(validated):raise ValueError('child_receipt_changed')
            _validate_terminal(report,config,old[1],validated)
            if sources()!=config['source_sha256'] or adopt(parent,parent_ledger,expected_digest)!=original:raise ValueError('research_inputs_changed')
            if _claim_read(ledger,identity)!=old:raise ValueError('coordinator_claim_changed')
            return report
        claimed=(canonical(config),'claimed',None,None)
        if _claim_read(ledger,identity)!=claimed:raise ValueError('coordinator_state_changed')
        _save_exact(root/'identity.json',config)
        report=_base_report(config);result=None
        try:
            if fresh:
                if child.exists():raise ValueError('fresh_child_directory_required')
                study.run(child,expected_digest,child_ledger)
            result=study.validate_receipt(child,expected_digest,child_ledger)
            gate=decision(result)
            report.update(status=gate['next_action'],decision=gate,study_sha256=sha256(canonical(result).encode()).hexdigest())
            status='complete'
        except Exception as error:
            report['failure']=type(error).__name__;status='failed_consumed'
        except BaseException:
            with sqlite3.connect(ledger) as db:db.execute("UPDATE format_research SET status='failed_consumed' WHERE identity=?",(identity,))
            raise
        if sources()!=config['source_sha256'] or adopt(parent,parent_ledger,expected_digest)!=original:raise ValueError('research_inputs_changed')
        if _claim_read(ledger,identity)!=claimed:raise ValueError('coordinator_claim_changed')
        _validate_terminal(report,config,status,result)
        _save_exact(root/'report.json',report)
        encoded=canonical(report)
        with sqlite3.connect(ledger) as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT protocol,status,report,digest FROM format_research WHERE identity=?',(identity,)).fetchone()!=claimed:raise ValueError('coordinator_claim_changed')
            db.execute('UPDATE format_research SET status=?,report=?,digest=? WHERE identity=?',(status,encoded,sha256(encoded.encode()).hexdigest(),identity))
        return report
