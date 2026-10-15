"""Frozen adaptation candidates in ARC's existing offline evaluation registry.

This registry contains evidence, never deployable governed route releases.
"""
import json
from pathlib import Path
import subprocess
from .arc_evaluation import _db, _exclusive
from .arc_execution import digest
from .adaptation_replay import benchmark, load_suite


def revision():
    root=Path(__file__).resolve().parents[2]
    names=['src/nerve_awim/'+n for n in ('adaptation.py','adaptation_repository.py','adaptation_repository_evaluation.py','adaptation_cli.py','repository_agents_v20.py','adaptation_replay.py','adaptation_evaluation.py','arc_execution.py','arc_contracts.py','governed_learning_v20.py')]
    return digest({name:digest((root/name).read_text()) for name in names})


@_exclusive
def evaluate_candidate(path, *, candidate, suite, split):
    if not candidate or not candidate.startswith('adaptation-'): raise ValueError('candidate ID must start with adaptation-')
    manifest=load_suite(suite); dataset='adaptation:'+manifest['episodes_digest']; code=revision()
    root=Path(__file__).resolve().parents[2]
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    with _db(path) as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM arc_improvement_candidates WHERE dataset=? AND candidate=?',(dataset,candidate)).fetchone()
        if split=='development':
            if con.execute('SELECT 1 FROM arc_evaluation_runs WHERE dataset=?',(dataset,)).fetchone(): raise ValueError('held-out batch already consumed; use a fresh unseen batch')
            if row: raise ValueError('immutable candidate ID already exists')
            definition=dict(candidate_id=candidate,parent_version='structured-v1',artifact_digest=code,code_commit=commit,data_manifest_digest=manifest['episodes_digest'],split_manifest_digest=digest([(e['id'],e['split']) for e in manifest['episodes']]),encoder_version='none',configuration={'mode':'active-development'},seeds=[730],approvals=[],deployment_state='draft',rollback_target=None)
            con.execute('INSERT INTO arc_improvement_candidates VALUES(?,?,?,?,?,NULL)',(dataset,candidate,code,json.dumps(definition),'development-running'))
        else:
            if row is None or row['state']!='frozen' or row['revision']!=code: raise ValueError('frozen matching candidate required')
            if con.execute('SELECT 1 FROM arc_evaluation_runs WHERE dataset=?',(dataset,)).fetchone(): raise ValueError('held-out batch already consumed')
            con.execute('INSERT INTO arc_evaluation_runs VALUES(?,?,?,NULL)',(dataset,code,'claimed'))
            con.execute("UPDATE arc_improvement_candidates SET state='heldout-running' WHERE dataset=? AND candidate=?",(dataset,candidate))
    report=benchmark(suite,split=split)
    if revision()!=code: raise ValueError('code changed during evaluation; attempt remains consumed')
    report['candidate']=candidate; report['code_digest']=code
    report['activation_authorized']=False
    passed=(report.get('hard_gates_passed',False) and report['overhead_gate_passed'] and report['paired_success_difference']>=.05 and report['paired_bootstrap_95'][0]>0)
    state='frozen' if split=='development' else ('heldout-tested' if passed else 'rejected')
    with _db(path) as con:
        con.execute('UPDATE arc_improvement_candidates SET state=?,report=? WHERE dataset=? AND candidate=?',(state,json.dumps(report),dataset,candidate))
        if split=='heldout': con.execute('UPDATE arc_evaluation_runs SET state=?,report=? WHERE dataset=?',(state,json.dumps(report),dataset))
    report['candidate_state']=state
    return report
