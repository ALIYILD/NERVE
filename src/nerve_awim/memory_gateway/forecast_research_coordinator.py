"""Restartable fixed evidence-to-memory-to-review graph; never runs experiments."""
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

from . import forecast_outcome_memory as memory
from .research_supervisor import _exclusive

PROTOCOL = 'forecast-research-coordinator-v1'
ROOT = Path(__file__).resolve().parents[3]
SOURCES = ('src/nerve_awim/memory_gateway/forecast_research_coordinator.py',
           'src/nerve_awim/memory_gateway/forecast_outcome_memory.py',
           'scripts/run_forecast_research_coordinator.py')


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _sources():
    pins = memory.study._sources()
    pins.update(memory._pins())
    pins.update({name: sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES})
    return pins


def _paths(evidence):
    expected = {'directory', 'claims', 'predecessor_path', 'source_paths',
                'online_artifact', 'online_summary'}
    if set(evidence) != expected or type(evidence['source_paths']) is not dict:
        raise ValueError('explicit_forecast_evidence_paths_required')
    return {key: ({k: str(Path(v).resolve()) for k, v in value.items()}
                  if key == 'source_paths' else str(Path(value).resolve()))
            for key, value in evidence.items()}


def _publish(path, encoded):
    if path.exists():
        if path.read_text() != encoded:
            raise ValueError('forecast_review_artifact_changed')
        return
    temporary = path.with_suffix('.json.tmp')
    with temporary.open('x') as stream:
        stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def run(gateway, proposer, reader, scope, *, directory, journal, evidence):
    """Adopt receipts, propose once, await external fact review, emit review packet.

    Approval verifies a historical fact, not a deployment or controller change.
    A claimed interrupted proposal is reconciled only via the bridge's durable
    scoped claim plus the exact authoritative record. Consumed failures stop.
    """
    gateway._require(reader, scope, 'read')
    gateway._require(proposer, scope, 'read')
    gateway._require(proposer, scope, 'propose')
    if 'approve' in proposer.permissions:
        raise PermissionError('proposal_and_review_authority_must_be_separate')
    evidence = _paths(evidence)
    pins = _sources()
    source, content = memory.verified_fact(**evidence)
    root = Path(directory)
    if root.is_symlink(): raise ValueError('symlink_coordinator_root')
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    journal = str(Path(journal).resolve())
    config = {'protocol': PROTOCOL, 'scope': asdict(scope), 'directory': str(root),
              'journal': journal, 'evidence': evidence, 'source_sha256': pins,
              'memory_database': str(Path(gateway.ledger.path).resolve()),
              'source_id': source, 'content_sha256': sha256(content.encode()).hexdigest(),
              'nodes': ['adopt_verified_evidence', 'propose_fact', 'await_fact_review',
                        'emit_forecast_only_review_packet'], 'max_nodes': 4}
    identity = sha256(_json([PROTOCOL, asdict(scope), source]).encode()).hexdigest()
    bridge = memory.ForecastOutcomeMemory(gateway)
    with _exclusive(root):
        with sqlite3.connect(journal) as db:
            db.execute('CREATE TABLE IF NOT EXISTS forecast_research_runs_v1(identity TEXT PRIMARY KEY,config TEXT,status TEXT,memory_id TEXT,digest TEXT)')
            row = db.execute('SELECT config,status,memory_id,digest FROM forecast_research_runs_v1 WHERE identity=?', (identity,)).fetchone()
            if row is None:
                db.execute('INSERT INTO forecast_research_runs_v1 VALUES(?,?,?,NULL,NULL)',
                           (identity, _json(config), 'claimed'))
            elif row[0] != _json(config):
                raise ValueError('consumed_protocol_or_location_changed')
            elif row[1] not in ('claimed', 'waiting_for_fact_review', 'complete'):
                raise RuntimeError('forecast_coordinator_failed_consumed')
        try:
            claim = bridge.claim(reader, scope, source)
            if claim is None:
                if row is not None:
                    raise ValueError('interrupted_proposal_without_complete_claim')
                memory_id = bridge.propose(proposer, scope, **evidence)
                claim = bridge.claim(reader, scope, source)
                if claim != ('proposed', memory_id):
                    raise ValueError('proposal_claim_mismatch')
            else:
                if claim[0] != 'proposed' or not claim[1]:
                    raise ValueError('incomplete_memory_claim_consumed')
                memory_id = claim[1]
            if row is not None and row[2] is not None and row[2] != memory_id:
                raise ValueError('claimed_memory_changed')
            with gateway._lock:
                record = gateway._record_in_scope(reader, memory_id, scope)
                if (record.source_id != source or record.content != content
                        or record.source_sha256 != sha256(content.encode()).hexdigest()
                        or record.kind != 'episodic' or record.status not in ('pending', 'approved')):
                    raise ValueError('claimed_memory_fact_changed')
                if _sources() != pins:
                    raise ValueError('coordinator_source_changed')
                if record.status == 'pending':
                    if (row is not None and row[1] == 'complete') or (root/'report.json').exists():
                        raise ValueError('completed_memory_no_longer_approved')
                    with sqlite3.connect(journal) as db:
                        db.execute('UPDATE forecast_research_runs_v1 SET status=?,memory_id=? WHERE identity=?',
                                   ('waiting_for_fact_review', memory_id, identity))
                    return {'status': 'waiting_for_fact_review', 'memory_id': memory_id,
                            'source_id': source, 'new_episodes': 0, 'promotion_authorized': False,
                            'goal_achieved': False}
                approved = bridge.approved(reader, scope, **evidence)
                if approved is None or approved.memory_id != memory_id:
                    raise ValueError('approved_forecast_fact_required')
                if _sources() != pins:
                    raise ValueError('coordinator_source_changed')
                result = {'status': 'forecast_only_review_required', 'protocol': config,
                          'memory_id': memory_id, 'source_id': source,
                          'fact': json.loads(content), 'new_episodes': 0,
                          'next_action': 'independent_review_of_opt_in_forecast_only_integration',
                          'promotion_authorized': False, 'control_policy_change_authorized': False,
                          'model_weights_trained': False, 'goal_achieved': False}
                encoded = _json(result)+'\n'
                digest = sha256(encoded.encode()).hexdigest()
                if row is not None and row[1] == 'complete':
                    if row[3] != digest or not (root/'report.json').is_file():
                        raise ValueError('completed_review_artifact_missing_or_changed')
                _publish(root/'report.json', encoded)
                with sqlite3.connect(journal) as db:
                    db.execute('UPDATE forecast_research_runs_v1 SET status=?,memory_id=?,digest=? WHERE identity=?',
                               ('complete', memory_id, digest, identity))
                return result
        except Exception:
            with sqlite3.connect(journal) as db:
                db.execute('UPDATE forecast_research_runs_v1 SET status=? WHERE identity=?',
                           ('failed_consumed', identity))
            raise
