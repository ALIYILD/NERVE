"""Host-only bridge from verified research receipts to existing scoped memory.

Approving a factual outcome does not approve a candidate or award utility.
Proposals and independent host review use distinct capability permissions.
"""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .gateway import MemoryGateway
from . import evidence_window_study as study


def verified_fact(directory, claims, supervisor_directory):
    path = Path(directory)/'report.json'
    snapshot = path.read_bytes()
    study.validate_receipt(directory, claims, supervisor_directory)
    if path.read_bytes() != snapshot:
        raise ValueError('research_receipt_changed')
    report = json.loads(snapshot)
    # Receipt validation uses canonical JSON: whitespace/key order must not
    # create another outcome identity or escape a consumed receipt claim.
    digest = sha256(json.dumps(report,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()
    fact = {
        'kind': 'verified_synthetic_research_outcome',
        'protocol': report['protocol']['protocol'],
        'receipt_sha256': digest,
        'episodes': report['episodes'], 'plant_steps': report['plant_steps'],
        'recommendation': report['recommendation'],
        'selected_candidate': report['selection']['candidate'],
        'validation_consumed': 'validation' in report['stages'],
        'holdout_consumed': report['holdout_consumed'],
        'training_candidates': len(report['selection']['evaluations']),
        'training_eligible': sum(v['passed'] for v in report['selection']['evaluations'].values()),
        'candidate_promoted': False, 'model_weights_trained': False,
        'interpretation': 'Verified experiment outcome only. Retain baseline when gates fail. No general learning benefit or clinical readiness established.'}
    content = json.dumps(fact, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(content) > 2048:
        raise ValueError('research_fact_too_large')
    return 'research-receipt:'+digest, content


class ResearchOutcomeMemory:
    def __init__(self, gateway):
        if type(gateway) is not MemoryGateway:
            raise TypeError('authoritative memory gateway required')
        self.gateway = gateway

    def propose(self, proposer, scope, directory, claims, supervisor_directory):
        gateway = self.gateway
        gateway._require(proposer, scope, 'propose')
        gateway._require(proposer, scope, 'read')
        if 'approve' in proposer.permissions:
            raise PermissionError('use a proposal-only host capability')
        source, content = verified_fact(directory, claims, supervisor_directory)
        with gateway._lock:
            gateway._require(proposer, scope, 'propose')
            gateway._require(proposer, scope, 'read')
            with sqlite3.connect(gateway.ledger.path) as db:
                db.execute('CREATE TABLE IF NOT EXISTS research_memory_receipts_v1(tenant TEXT,agent TEXT,context TEXT,source TEXT,status TEXT,memory_id TEXT,PRIMARY KEY(tenant,agent,context,source))')
                try:
                    db.execute('INSERT INTO research_memory_receipts_v1 VALUES(?,?,?,?,?,NULL)',
                        (scope.tenant_id, scope.agent_id, scope.context, source, 'claimed'))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('research_receipt_already_consumed') from exc
            identity = (scope.tenant_id, scope.agent_id, scope.context, source)
            try:
                memory_id = gateway.propose(proposer, scope=scope, content=content,
                                            source_id=source, kind='episodic')
                with sqlite3.connect(gateway.ledger.path) as db:
                    db.execute('UPDATE research_memory_receipts_v1 SET status=?,memory_id=? WHERE tenant=? AND agent=? AND context=? AND source=?',
                               ('proposed', memory_id, *identity))
                return memory_id
            except BaseException:
                with sqlite3.connect(gateway.ledger.path) as db:
                    db.execute('UPDATE research_memory_receipts_v1 SET status=? WHERE tenant=? AND agent=? AND context=? AND source=?',
                               ('failed_consumed', *identity))
                raise

    def review(self, reviewer, scope, memory_id, directory, claims, supervisor_directory):
        gateway = self.gateway
        gateway._require(reviewer, scope, 'approve')
        gateway._require(reviewer, scope, 'read')
        source, content = verified_fact(directory, claims, supervisor_directory)
        with gateway._lock:
            gateway._require(reviewer, scope, 'approve')
            record = gateway._record_in_scope(reviewer, memory_id, scope)
            if (record.status != 'pending' or record.kind != 'episodic' or
                    record.source_id != source or record.content != content or
                    record.source_sha256 != sha256(content.encode()).hexdigest()):
                raise ValueError('research_memory_does_not_match_verified_receipt')
            with sqlite3.connect(gateway.ledger.path) as db:
                claim = db.execute('SELECT status,memory_id FROM research_memory_receipts_v1 WHERE tenant=? AND agent=? AND context=? AND source=?',
                    (scope.tenant_id, scope.agent_id, scope.context, source)).fetchone()
            if claim != ('proposed', memory_id):
                raise ValueError('research_proposal_not_reviewable')
            # Memory approval attests receipt facts, never candidate promotion.
            return gateway.decide(reviewer, memory_id, scope=scope, approve=True,
                                  evaluator_id='verified-research-receipt-v1')
