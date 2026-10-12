"""Versioned, JSON-native action-grounded records (audit summaries, not thought traces)."""
from dataclasses import dataclass, asdict, field
import json
import math

def _timestamp(value):
    return type(value) in (int,float) and math.isfinite(value)

def _strings(values):
    return type(values) is list and all(type(v) is str for v in values)

def _identity(value):
    return type(value) is str and 0 < len(value) <= 128 and all(c.isalnum() or c in '_.:-' for c in value)

SCHEMA = 'nerve-arc-v1'
STATUSES = {'proposed','validated','awaiting_approval','ready','executing','awaiting_verification','succeeded','failed','uncertain','cancelled','expired'}

class Record:
    def to_dict(self):
        return asdict(self)
    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, allow_nan=False)
    @classmethod
    def from_json(cls, value):
        return cls(**json.loads(value))

@dataclass(frozen=True)
class EvidenceRef(Record):
    source_id: str
    source_version_or_hash: str
    captured_at: float
    valid_until_if_known: float | None
    tenant_scope: str
    source_type: str
    provenance: str
    access_scope: str
    reference_to_redacted_or_protected_content: str
    schema_version: str = SCHEMA
    def __post_init__(self):
        if self.schema_version != SCHEMA: raise ValueError('unsupported evidence schema version')
        if not all(isinstance(v,str) and v for v in (self.source_id,self.source_version_or_hash,self.tenant_scope,self.access_scope,self.provenance)): raise ValueError('evidence identity, scope and provenance required')
        if not _timestamp(self.captured_at): raise ValueError('finite observation timestamp required')
        if self.valid_until_if_known is not None and (not _timestamp(self.valid_until_if_known) or self.valid_until_if_known < self.captured_at): raise ValueError('invalid evidence expiry')

@dataclass(frozen=True)
class DecisionRecord(Record):
    decision_id: str
    task_id: str
    episode_id: str
    tenant_scope: str
    actor_id: str
    agent_id: str
    correlation_id: str
    created_at: float
    expires_at: float
    observation_version: str
    goal: str
    observed_facts: list
    unknowns: list
    evidence_refs: list
    concise_rationale: str
    anticipated_consequence: str
    intended_effect: str
    action: dict
    forbidden_effects: list
    completion_criteria: list
    verification_method: str
    uncertainty: dict
    approval_requirement: bool
    approval_ref: str | None
    policy_version: str
    model_version: str
    prompt_version: str
    status: str
    parent_decision_id: str | None = None
    schema_version: str = SCHEMA
    def __post_init__(self):
        if self.schema_version != SCHEMA: raise ValueError('unsupported decision schema version')
        if not all(_identity(v) for v in (self.decision_id,self.task_id,self.episode_id,self.tenant_scope,self.actor_id,self.agent_id,self.correlation_id)): raise ValueError('bounded decision identities required')
        if type(self.approval_requirement) is not bool: raise ValueError('approval requirement must be Boolean')
        if not all(_strings(v) for v in (self.observed_facts,self.unknowns,self.forbidden_effects,self.completion_criteria)): raise ValueError('decision facts and criteria must be string lists')
        if type(self.evidence_refs) is not list or any(type(v) is not dict for v in self.evidence_refs): raise ValueError('evidence references must be typed object list')
        for ref in self.evidence_refs: EvidenceRef(**ref)
        if type(self.action) is not dict or type(self.uncertainty) is not dict: raise ValueError('typed action and uncertainty required')
        if self.status not in STATUSES: raise ValueError('unknown lifecycle status')
        if not self.goal or not self.completion_criteria: raise ValueError('goal and completion criteria required')
        if not _timestamp(self.created_at) or not _timestamp(self.expires_at) or self.expires_at <= self.created_at: raise ValueError('invalid decision expiry')
        if set(self.action) != {'registered_tool','validated_arguments_ref','idempotency_key'}: raise ValueError('invalid action contract')
        if self.uncertainty.get('confidence_if_calibrated') is not None: raise ValueError('calibration not configured; confidence must be unknown')

@dataclass(frozen=True)
class OutcomeRecord(Record):
    outcome_id: str
    decision_id: str
    execution_id: str
    observed_at: float
    transport_status: str
    semantic_status: str
    criterion_results: dict
    actual_effect: str
    verification_evidence_refs: list
    discrepancy: str
    retry_classification: str
    reviewer_status: str
    latency: float
    usage_and_cost_if_available: dict | None = None
    schema_version: str = SCHEMA
    def __post_init__(self):
        if self.schema_version != SCHEMA: raise ValueError('unsupported outcome schema version')
        if not all(_identity(v) for v in (self.outcome_id,self.decision_id,self.execution_id)) or not _timestamp(self.observed_at): raise ValueError('outcome identity and timestamp required')
        if self.transport_status not in {'success','error','timeout','unknown'}: raise ValueError('unknown transport status')
        if type(self.criterion_results) is not dict or any(type(v) is not bool for v in self.criterion_results.values()): raise ValueError('Boolean criterion results required')
        if not _timestamp(self.latency) or self.latency < 0: raise ValueError('nonnegative finite latency required')
        if self.semantic_status not in {'verified','partial','failed','unverifiable','contradicted'}: raise ValueError('unknown semantic status')
