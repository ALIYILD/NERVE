"""Fixed memory-guided diagnostic dispatch with durable consumption and resume.

This host entry point has one registered diagnostic, no generated-code executor,
no trial retries, and no automatic promotion. Memory advice is revalidated each run.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

from . import evidence_window_study as study
from . import evidence_rejection_diagnostic as diagnostic
from .research_memory_planner import ResearchMemoryPlanner
from .research_supervisor import _exclusive

PROTOCOL = 'memory-research-coordinator-v1'
SOURCES = tuple(dict.fromkeys(study.SOURCES + (
    'src/nerve_awim/memory_gateway/research_outcome_memory.py',
    'src/nerve_awim/memory_gateway/research_memory_planner.py',
    'src/nerve_awim/memory_gateway/evidence_rejection_diagnostic.py',
    'src/nerve_awim/memory_gateway/memory_research_coordinator.py',
    'scripts/run_memory_research_coordinator.py',
)))


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _sources():
    return {name: sha256((study.recovery.ROOT/name).read_bytes()).hexdigest() for name in SOURCES}


def _read_study(directory, digest):
    report = json.loads((Path(directory)/'report.json').read_bytes())
    if sha256(_json(report).encode()).hexdigest() != digest:
        raise ValueError('study_changed_after_planning')
    return report


def run(gateway, reader, scope, *, directory, journal, study_directory, study_claims,
        supervisor_directory):
    # Invalid/missing/revoked memory never reaches dispatch or claims.
    plan = ResearchMemoryPlanner(gateway).plan(reader, scope, study_directory,
                                              study_claims, supervisor_directory)
    if plan.action != 'diagnose_rejection_and_register_new_hypothesis':
        return {'status': 'waiting_for_verified_rejection', 'plan': plan.to_dict(),
                'new_episodes': 0, 'promotion_authorized': False, 'goal_achieved': False}
    root = Path(directory)
    if root.is_symlink():
        raise ValueError('symlink_coordinator_root')
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    pins = _sources()
    config = {'protocol': PROTOCOL, 'scope': asdict(scope),
              'memory_database': str(Path(gateway.ledger.path).resolve()),
              'memory_id': plan.memory_id, 'receipt_sha256': plan.receipt_sha256,
              'study_directory': str(Path(study_directory).resolve()),
              'study_claims': str(Path(study_claims).resolve()),
              'supervisor_directory': str(Path(supervisor_directory).resolve()),
              'directory': str(root), 'source_sha256': pins, 'max_nodes': 1}
    key = sha256(_json([PROTOCOL, asdict(scope), plan.receipt_sha256]).encode()).hexdigest()
    with _exclusive(root):
        with sqlite3.connect(journal) as db:
            db.execute('CREATE TABLE IF NOT EXISTS memory_research_runs_v1(identity TEXT PRIMARY KEY,config TEXT,status TEXT,digest TEXT)')
            row = db.execute('SELECT config,status,digest FROM memory_research_runs_v1 WHERE identity=?', (key,)).fetchone()
            if row is None:
                db.execute('INSERT INTO memory_research_runs_v1 VALUES(?,?,?,NULL)',
                           (key, _json(config), 'claimed'))
            elif row[0] != _json(config):
                raise ValueError('consumed_protocol_or_location_changed')
            elif row[1] not in ('claimed', 'complete'):
                raise RuntimeError('diagnostic_failed_consumed')
        artifact = root/'report.json'
        try:
            gateway._require(reader, scope, 'read')
            report = _read_study(study_directory, plan.receipt_sha256)
            result = diagnostic.diagnose(report)
            expected = {'status': 'new_registered_experiment_required', 'protocol': config,
                        'plan': plan.to_dict(), 'diagnostic': result,
                        'new_episodes': 0, 'promotion_authorized': False,
                        'model_weights_trained': False, 'goal_achieved': False,
                        'next_action': result['next_action']}
            encoded = _json(expected)+'\n'
            digest = sha256(encoded.encode()).hexdigest()
            # Refresh memory permission and content immediately before publishing.
            refreshed = ResearchMemoryPlanner(gateway).plan(reader, scope, study_directory,
                                                            study_claims, supervisor_directory)
            if refreshed != plan or _sources() != pins:
                raise ValueError('planning_authority_or_source_changed')
            if row is not None:
                # A claimed partial run is reconciled only from complete evidence.
                if artifact.read_text() != encoded or (row[1] == 'complete' and row[2] != digest):
                    raise ValueError('diagnostic_artifact_changed')
            else:
                if artifact.exists():
                    raise ValueError('unclaimed_existing_artifact')
                temporary = root/'report.json.tmp'
                with temporary.open('w') as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(artifact)
                descriptor = os.open(root, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            with sqlite3.connect(journal) as db:
                db.execute('UPDATE memory_research_runs_v1 SET status=?,digest=? WHERE identity=?',
                           ('complete', digest, key))
            return expected
        except BaseException:
            with sqlite3.connect(journal) as db:
                db.execute('UPDATE memory_research_runs_v1 SET status=? WHERE identity=?',
                           ('failed_consumed', key))
            raise
