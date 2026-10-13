"""Read-only planning over independently validated receipts and scoped memory.

Plans are advisory snapshots, never capabilities to run, retry or promote work.
The existing study journals remain the execution authority.
"""
from dataclasses import asdict, dataclass
import json

from .contracts import MemoryRequest
from .gateway import MemoryGateway
from .research_outcome_memory import verified_fact


@dataclass(frozen=True)
class ResearchPlan:
    action: str
    receipt_sha256: str
    recommendation: str
    memory_id: str | None
    execution_authorized: bool = False
    promotion_authorized: bool = False
    model_weights_trained: bool = False

    def to_dict(self):
        return asdict(self)


class ResearchMemoryPlanner:
    def __init__(self, gateway):
        if type(gateway) is not MemoryGateway:
            raise TypeError('authoritative memory gateway required')
        self.gateway = gateway

    def plan(self, reader, scope, directory, claims, supervisor_directory):
        # Authenticate before touching potentially expensive receipt validation.
        self.gateway._require(reader, scope, 'read')
        source, content = verified_fact(directory, claims, supervisor_directory)
        fact = json.loads(content)
        # Receipt facts, not natural-language instructions, select fixed actions.
        digest = fact['receipt_sha256']
        with self.gateway._lock:
            result = self.gateway.retrieve(reader, MemoryRequest(scope, digest, limit=20,
                                                                  max_context_chars=32768))
            matches = [record for record in result.records
                       if record.kind == 'episodic' and record.source_id == source
                       and record.content == content
                       and record.evaluator_id == 'verified-research-receipt-v1'
                       and record.outcome_score is None]
            if len(matches) != 1:
                action = 'verify_and_record_outcome'
                memory_id = None
            else:
                memory_id = matches[0].memory_id
                action = ('diagnose_rejection_and_register_new_hypothesis'
                          if fact['recommendation'] == 'retain_baseline'
                          else 'candidate_requires_independent_review')
            # Re-check after retrieval; the returned plan grants no lasting rights.
            self.gateway._require(reader, scope, 'read')
            return ResearchPlan(action, digest, fact['recommendation'], memory_id)
