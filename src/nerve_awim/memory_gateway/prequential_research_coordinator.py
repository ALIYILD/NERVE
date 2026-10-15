"""Finite receipt adoption and timing diagnosis, with no experiment retry path."""
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

from . import prequential_timing_diagnostic as diagnostic
from .research_supervisor import _exclusive
from .standard_learning_demo import ROOT

PROTOCOL='prequential-research-coordinator-v1'
NODES=('adopt_completed_development_experiment','diagnose_rejected_selector_timing')
MAX_ARTIFACT_BYTES=32*1024*1024


def _json(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def sources():
    pins=diagnostic.sources()
    for name in ('src/nerve_awim/memory_gateway/prequential_research_coordinator.py',
                 'src/nerve_awim/memory_gateway/research_supervisor.py','scripts/run_prequential_research.py'):
        pins[name]=sha256((ROOT/name).read_bytes()).hexdigest()
    return pins


def _read(path):
    with path.open('rb') as stream:
        raw=stream.read(MAX_ARTIFACT_BYTES+1)
    if len(raw)>MAX_ARTIFACT_BYTES: raise ValueError('oversized_research_artifact')
    return raw


def _snapshot(path):
    raw=_read(path)
    if raw.startswith(b'\x1f\x8b'):
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            content=stream.read(MAX_ARTIFACT_BYTES+1)
    else: content=raw
    if len(content)>MAX_ARTIFACT_BYTES: raise ValueError('oversized_research_artifact')
    parsed=json.loads(content)
    canonical=sha256(_json(parsed).encode()).hexdigest()
    return raw,parsed,canonical


def _atomic_write(path,encoded):
    temporary=path.with_suffix('.json.tmp')
    with temporary.open('x') as stream:
        stream.write(encoded);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor=os.open(path.parent,os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def run(directory,journal,artifact):
    root=Path(directory)
    if root.is_symlink(): raise ValueError('symlink_coordinator_root')
    root.mkdir(parents=True,exist_ok=True);root=root.resolve()
    ledger=Path(journal).resolve();source=Path(artifact).resolve()
    if root==ledger or root in ledger.parents: raise ValueError('shared_journal_must_be_outside_run')
    if source==root/'report.json' or source==ledger: raise ValueError('overlapping_research_paths')
    with _exclusive(root):
        raw,original,identity=_snapshot(source)
        pins=sources()
        config={'protocol':PROTOCOL,'directory':str(root),'journal':str(ledger),'artifact':str(source),
            'source_identity':identity,'raw_artifact_sha256':sha256(raw).hexdigest(),
            'source_sha256':pins,'nodes':NODES,'max_nodes':2,'max_new_episodes':0}
        with sqlite3.connect(ledger) as db:
            db.execute('CREATE TABLE IF NOT EXISTS prequential_research_runs_v1(identity TEXT PRIMARY KEY,config TEXT,status TEXT,digest TEXT)')
            previous=db.execute('SELECT config,status,digest FROM prequential_research_runs_v1 WHERE identity=?',(identity,)).fetchone()
            if previous is None:
                db.execute('INSERT INTO prequential_research_runs_v1 VALUES(?,?,?,NULL)',(identity,_json(config),'claimed'))
            elif previous[0]!=_json(config): raise ValueError('consumed_source_configuration_changed')
            elif previous[1] not in ('claimed','complete'): raise RuntimeError('research_failed_consumed')
        output=root/'report.json'
        try:
            # A restart can only reconcile an existing complete artifact; it
            # cannot use an abandoned claim as permission to rebuild evidence.
            if previous is not None and not output.is_file():
                raise ValueError('claimed_research_output_missing')
            if previous is None and output.exists(): raise ValueError('unclaimed_research_output')
            result=diagnostic.run(source)
            if original.get('status')!='complete' or original.get('screen',{}).get('passed') is not False:
                raise ValueError('completed_rejected_development_experiment_required')
            if (result.get('status')!='diagnostic_complete' or type(result.get('new_episodes')) is not int or result.get('new_episodes')!=0
                    or result.get('promotion_authorized') is not False or result.get('goal_achieved') is not False):
                raise ValueError('invalid_registered_diagnostic_result')
            report={'protocol':config,'status':'new_registered_hypothesis_required',
                'completed_nodes':[{'node':NODES[0],'origin':'adopted','source_identity':identity},
                                   {'node':NODES[1],'origin':'diagnosed','evidence':result}],
                'next_action':'review_evidence_timing_and_register_new_hypothesis',
                'baseline_retained':True,'new_episodes':0,'automatic_retry':False,
                'promotion_authorized':False,'model_weights_trained':False,'goal_achieved':False}
            encoded=_json(report)+'\n';digest=sha256(encoded.encode()).hexdigest()
            if _read(source)!=raw or sources()!=pins: raise ValueError('research_source_changed')
            if previous is not None:
                if output.read_bytes()!=encoded.encode() or (previous[1]=='complete' and previous[2]!=digest):
                    raise ValueError('research_output_changed')
            else: _atomic_write(output,encoded)
            with sqlite3.connect(ledger) as db:
                db.execute('UPDATE prequential_research_runs_v1 SET status=?,digest=? WHERE identity=?',('complete',digest,identity))
            return report
        except BaseException:
            with sqlite3.connect(ledger) as db:
                db.execute("UPDATE prequential_research_runs_v1 SET status='failed_consumed' WHERE identity=?",(identity,))
            raise
