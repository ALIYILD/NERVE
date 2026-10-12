"""Bounded JSON contracts; hashes prove identity, never factual truth."""
from dataclasses import dataclass, asdict, field
import json
import math
import re
from ..governed_learning_v20 import _id
SCHEMA='nerve-uncertainty-v1'
OPEN=frozenset({'suspected','confirmed_open','investigating','unresolved_reported','reopened'})
KINDS=frozenset({'source_disagreement','prior_vs_evidence','missing_required_evidence','stale_evidence','ambiguous_identity','measurement_uncertainty','tool_status_unknown'})
def bounded(value):
    text=json.dumps(value,sort_keys=True,allow_nan=False)
    if len(text.encode())>16384: raise ValueError('contract exceeds 16 KiB limit')
    return value
class Record:
    def to_dict(self): return asdict(self)
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,allow_nan=False)
    @classmethod
    def from_json(cls,value):
        def pairs(items):
            out={}
            for key,val in items:
                if key in out:raise ValueError('duplicate JSON field')
                out[key]=val
            return out
        return cls(**json.loads(value,object_pairs_hook=pairs))
    def validate(self):
        if self.schema_version!=SCHEMA: raise ValueError('unsupported uncertainty schema')
        bounded(self.to_dict())
        for name,value in self.to_dict().items():
            if name.endswith('_ids') or name in {'checks','source_lineage','evidence_refs','remaining_unknowns'}:
                if type(value) is not list or len(value)>128:raise ValueError('bounded list required: '+name)
                if name!='evidence_refs':
                    for member in value:
                        if name!='remaining_unknowns':_id(member)
                        elif type(member) is not str or len(member)>512:raise ValueError('bounded unknown summary required')
                else:
                    for ref in value:
                        if type(ref) is not dict or set(ref)!={'source_ref','source_revision'}:raise ValueError('exact evidence source reference required')
                        for member in ref.values():_id(member)
            if name in {'observed_at','retrieved_at','valid_from','valid_to','detected_at','updated_at','expiry_review_at','started_at','finished_at','created_at','expires_at'} and value is not None:
                if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('finite timestamp required: '+name)
            if name in {'ledger_revision','expected_conflict_revision','revision'}:
                if type(value) is not int or value<0:raise ValueError('nonnegative integer revision required')
            if name in {'concise_reason','rationale_summary'} and (type(value) is not str or not 1<=len(value)<=1024):raise ValueError('bounded concise summary required')
            if name in {'evidence_hash','canonical_request_hash'} and (type(value) is not str or not re.fullmatch('[0-9a-f]{64}',value)):raise ValueError('SHA-256 digest required')

@dataclass(frozen=True)
class Claim(Record):
    claim_id:str
    tenant_id:str
    task_id:str
    subject_ref:str
    predicate:str
    normalized_value:object
    source_ref:str
    source_revision:str
    source_lineage_id:str
    evidence_hash:str
    value_type:str='scalar'
    units:str=''
    polarity:bool=True
    valid_from:float=0
    valid_to:float|None=None
    observed_at:float=0
    retrieved_at:float=0
    context:dict=field(default_factory=dict)
    provenance_class:str='structured'
    extraction_status:str='verified'
    schema_version:str=SCHEMA
    def __post_init__(self):
        self.validate()
        for v in (self.claim_id,self.tenant_id,self.task_id,self.subject_ref,self.predicate,self.source_ref,self.source_revision,self.source_lineage_id):_id(v)
        if self.value_type not in {'scalar','boolean','number','string','unknown'} or type(self.units) is not str or len(self.units)>32:raise ValueError('bounded typed value and units required')
        if self.normalized_value is not None and type(self.normalized_value) not in (str,bool,int,float):raise ValueError('normalized claim value must be scalar or unknown')
        if type(self.polarity) is not bool or type(self.context) is not dict: raise ValueError('typed polarity and context required')
        for t in (self.valid_from,self.observed_at,self.retrieved_at):
            if type(t) not in (int,float) or not math.isfinite(t): raise ValueError('finite timestamps required')
        if self.valid_to is not None and (type(self.valid_to) not in (int,float) or not math.isfinite(self.valid_to) or self.valid_to<=self.valid_from): raise ValueError('invalid applicability interval')
        if self.extraction_status not in {'verified','suggested','unknown'}:raise ValueError('unknown extraction status')

@dataclass(frozen=True)
class Conflict(Record):
    conflict_id:str
    scope:dict
    claim_ids:list
    kind:str
    status:str='suspected'
    affected_decision_ids:list=field(default_factory=list)
    affected_rule_ids:list=field(default_factory=list)
    materiality:str='prerequisite'
    detected_at:float=0
    updated_at:float=0
    revision:int=1
    owner_role:str='operator'
    checks:list=field(default_factory=list)
    resolution_ref:str|None=None
    reopened_from:str|None=None
    expiry_review_at:float|None=None
    schema_version:str=SCHEMA
    def __post_init__(self):
        self.validate();_id(self.conflict_id)
        if self.kind not in KINDS or self.status not in OPEN|{'resolved','dismissed_with_evidence'}: raise ValueError('unknown conflict kind or status')
        if type(self.revision) is not int or self.revision<1:raise ValueError('positive conflict revision required')
        if set(self.scope)!={'tenant_id','agent_id','task_id'}:raise ValueError('exact scoped conflict required')
        for v in self.scope.values():_id(v)
        for v in self.claim_ids+self.affected_decision_ids+self.affected_rule_ids:_id(v)

@dataclass(frozen=True)
class VerificationAttempt(Record):
    attempt_id:str
    conflict_id:str
    tool_id:str
    canonical_request_hash:str
    source_lineage:list=field(default_factory=list)
    started_at:float=0
    finished_at:float|None=None
    status:str='reserved'
    evidence_refs:list=field(default_factory=list)
    cost:float=0
    retry_reason:str|None=None
    provider_revision:str='offline-v1'
    outcome:str='inconclusive'
    schema_version:str=SCHEMA
    def __post_init__(self):
        self.validate()
        for v in (self.attempt_id,self.conflict_id,self.tool_id):_id(v)
        if self.status not in {'reserved','completed','failed','uncertain'}:raise ValueError('unknown verification status')
        if self.outcome not in {'supports','refutes','inconclusive','failed'}:raise ValueError('unknown verification outcome')
        if type(self.cost) not in (int,float) or self.cost<0 or not math.isfinite(self.cost):raise ValueError('finite nonnegative cost required')

@dataclass(frozen=True)
class Resolution(Record):
    resolution_id:str
    conflict_id:str
    expected_conflict_revision:int
    resolution_type:str
    accepted_claim_ids:list
    rejected_or_superseded_claim_ids:list
    evidence_refs:list
    concise_reason:str
    resolver_identity:str
    policy_revision:str
    created_at:float=0
    schema_version:str=SCHEMA
    def __post_init__(self):
        self.validate()
        for v in (self.resolution_id,self.conflict_id,self.resolver_identity,self.policy_revision):_id(v)
        if self.resolution_type not in {'corrected_extraction','unit_normalized','different_context','time_superseded','primary_record_verified','reviewed_resolution'}:raise ValueError('unknown resolution type')
        if type(self.expected_conflict_revision) is not int or self.expected_conflict_revision<1:raise ValueError('expected revision required')

@dataclass(frozen=True)
class DecisionAssessment(Record):
    decision_id:str
    dependency_claim_ids:list
    conflict_ids:list
    status:str
    permitted_action_ids:list
    blocked_action_ids:list
    remaining_unknowns:list
    rationale_summary:str
    policy_revision:str
    ledger_revision:int
    expires_at:float
    schema_version:str=SCHEMA
    def __post_init__(self):
        self.validate();_id(self.decision_id)
        if self.status not in {'proceed','proceed_with_qualification','verify_first','defer_affected_action','request_review','unavailable'}:raise ValueError('unknown decision assessment status')
