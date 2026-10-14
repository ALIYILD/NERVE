"""Fixed scientific research graph: adopt, validate once, retain or request review."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

from . import scientific_interface_study as development
from . import scientific_interface_validation as validation
from .prequential_research_coordinator import _atomic_write
from .research_supervisor import _exclusive

REVISION = 'scientific-research-coordinator-v1'
_json = development._json


def sources():
    pins = validation.sources()
    for name in ('src/nerve_awim/memory_gateway/scientific_research_coordinator.py',
                 'src/nerve_awim/memory_gateway/prequential_research_coordinator.py',
                 'scripts/run_scientific_research.py'):
        pins[name] = sha256((development.pilot.ROOT/name).read_bytes()).hexdigest()
    return pins


def _existing(directory):
    path = Path(directory)/'memory.sqlite'
    if not path.is_file():
        raise ValueError('completed_predecessor_required')
    with sqlite3.connect('file:'+quote(str(path.resolve()))+'?mode=ro', uri=True) as db:
        row = db.execute('SELECT report,digest FROM scientific_interface_runs WHERE id=1').fetchone()
    if row is None or row[0] is None or sha256(row[0].encode()).hexdigest()!=row[1]:
        raise ValueError('complete_hashed_receipt_required')
    report = json.loads(row[0])
    if report.get('status')!='complete':
        raise ValueError('incomplete_experiment_consumed')
    return report


def _adopt_development(directory,journal,expected_digest):
    with _exclusive(directory):
        report=_existing(directory)
        protocol=dict(version=development.REVISION,directory=str(directory),journal=str(journal),
            model=development.MODEL,origin=development.ORIGIN,expected_digest=expected_digest,
            dataset_sha256=development._hash(development.tasks.TASKS),direct_prefix=development.tasks.DIRECT_PREFIX,
            pairs=development.pairs(),source_sha256=development.sources(),max_inference_calls=8,
            max_output_tokens=128,socket_timeout_seconds=90,max_preload_calls=1,max_metadata_calls=2,
            development_only=True)
        gateway,_,_,_,reader=development._state(directory/'memory.sqlite')
        development._validate(directory/'memory.sqlite',gateway,reader,report,protocol)
        if _json(_existing(directory))!=_json(report):raise ValueError('predecessor_changed')
        return report


def run(directory,journal,development_directory,development_journal,
        validation_directory,validation_journal,expected_digest):
    paths=[Path(p).resolve() for p in (directory,journal,development_directory,
                                     development_journal,validation_directory,validation_journal)]
    root,ledger,parent,parent_ledger,child,child_ledger=paths
    if len(set(paths))!=6 or any(root in p.parents for p in (ledger,parent,parent_ledger,child,child_ledger)):
        raise ValueError('distinct_external_research_paths_required')
    if any(d==j or d in j.parents for d in (parent,child) for j in (ledger,parent_ledger,child_ledger)):
        raise ValueError('journals_outside_experiment_directories_required')
    # No missing predecessor can trigger inference during adoption.
    original=_adopt_development(parent,parent_ledger,expected_digest)
    parent_hash=sha256(_json(original).encode()).hexdigest()
    identity=sha256((REVISION+parent_hash).encode()).hexdigest()
    root.mkdir(parents=True,exist_ok=True)
    with _exclusive(root):
        config=dict(version=REVISION,paths=[str(p) for p in paths],expected_digest=expected_digest,
                    predecessor_sha256=parent_hash,source_sha256=sources(),
                    nodes=['adopt_completed_development','fresh_fixed_validation','review_decision'],
                    max_new_inference_calls=16,max_experiments=1)
        with sqlite3.connect(ledger) as db:
            db.execute('CREATE TABLE IF NOT EXISTS scientific_research_runs(identity TEXT PRIMARY KEY,config TEXT,status TEXT,digest TEXT)')
            old=db.execute('SELECT config,status,digest FROM scientific_research_runs WHERE identity=?',(identity,)).fetchone()
            if old is None:
                db.execute('INSERT INTO scientific_research_runs VALUES(?,?,?,NULL)',(identity,_json(config),'claimed'))
            elif old[0]!=_json(config):raise ValueError('consumed_research_configuration_changed')
            elif old[1] not in ('claimed','complete'):raise ValueError('research_failed_consumed')
        output=root/'report.json'
        try:
            if old is None:
                if output.exists():raise ValueError('unclaimed_output')
                # Child owns independent durable pre-call claims and budgets.
                result=validation.run(child,expected_digest,child_ledger)
                if result.get('status')!='complete':raise ValueError('validation_failed_consumed')
            else:
                # Interrupted orchestration may only adopt already complete child evidence.
                # It may never dispatch a missing or incomplete child experiment again.
                result=validation.validate_receipt(child,expected_digest,child_ledger)
            if sources()!=config['source_sha256'] or _json(_adopt_development(parent,parent_ledger,expected_digest))!=_json(original):
                raise ValueError('research_inputs_changed')
            screen=result['screen']
            if type(screen.get('passed')) is not bool:raise ValueError('invalid_screen')
            report=dict(protocol=config,status=('candidate_requires_independent_review' if screen['passed'] else 'retain_baseline'),
                completed_nodes=config['nodes'],predecessor_sha256=parent_hash,
                validation_sha256=sha256(_json(result).encode()).hexdigest(),screen=screen,
                validation_summary=result['summary'],new_inference_budget=16,
                automatic_retry=False,feedback_learning=False,promotion_authorized=False,
                model_weights_trained=False,goal_achieved=False)
            encoded=_json(report)+'\n';digest=sha256(encoded.encode()).hexdigest()
            with sqlite3.connect(ledger) as db:
                current=db.execute('SELECT config,status,digest FROM scientific_research_runs WHERE identity=?',(identity,)).fetchone()
                if current!=((_json(config),'claimed',None) if old is None else old):
                    raise ValueError('coordinator_claim_changed')
            if output.exists():
                if output.read_bytes()!=encoded.encode():raise ValueError('coordinator_output_changed')
            elif old is not None and old[1]=='complete':raise ValueError('completed_output_missing')
            else:_atomic_write(output,encoded)
            if old is not None and old[1]=='complete' and old[2]!=digest:raise ValueError('output_digest_changed')
            with sqlite3.connect(ledger) as db:
                db.execute('UPDATE scientific_research_runs SET status=?,digest=? WHERE identity=?',('complete',digest,identity))
            return report
        except BaseException:
            with sqlite3.connect(ledger) as db:
                db.execute("UPDATE scientific_research_runs SET status='failed_consumed' WHERE identity=?",(identity,))
            raise
