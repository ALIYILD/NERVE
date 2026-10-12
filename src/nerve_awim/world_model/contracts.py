"""Strict versioned JSON contracts for the local synthetic research backend."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import re

MAX_BYTES = 1048576
REVISION = 'normalized-workflow-v1'

class PolicyDenied(PermissionError):
    pass

class IntegrityError(ValueError):
    pass

class BudgetExhausted(RuntimeError):
    pass

class StaleWorker(RuntimeError):
    pass


def canonical(value):
    def check(v, depth=0):
        if depth > 24:
            raise ValueError('JSON nesting limit')
        if v is None or type(v) in (str, bool, int):
            return
        if type(v) is float and math.isfinite(v):
            return
        if type(v) is list:
            for x in v:
                check(x, depth+1)
            return
        if type(v) is dict and all(type(k) is str for k in v):
            for x in v.values():
                check(x, depth+1)
            return
        raise ValueError('finite JSON values required')
    check(value)
    result = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(result.encode()) > MAX_BYTES:
        raise ValueError('artifact size limit')
    return result


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def identifier(value):
    if type(value) is not str or not re.fullmatch(r'[a-zA-Z0-9_-]{1,96}', value):
        raise ValueError('bounded identifier required')
    return value


def exact(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('unexpected or missing fields')
    canonical(value)
    return value


def observation(value):
    if value is not None:
        if type(value) is not dict or not value or len(value) > 64:
            raise ValueError('bounded observation object or explicit unknown required')
        canonical(value)
    return value


@dataclass(frozen=True)
class Policy:
    schema_version: int = 1
    enabled: bool = False
    mode: str = 'offline'
    max_generations: int = 5
    max_candidates_per_generation: int = 3
    max_population: int = 3
    max_revision_attempts_per_candidate: int = 3
    max_llm_calls_per_run: int = 30
    max_run_seconds: int = 1800
    max_artifact_bytes: int = MAX_BYTES
    sandbox_wall_seconds: int = 5
    sandbox_memory_mb: int = 256
    max_plan_depth: int = 5
    max_simulated_nodes_per_decision: int = 100
    max_real_actions_per_run: int = 20
    provider_spend_limit: int = 0
    promotion_mode: str = 'manual'
    allow_clinical_actions: bool = False

    def __post_init__(self):
        if type(self.enabled) is not bool or type(self.allow_clinical_actions) is not bool:
            raise ValueError('boolean flags required')
        if (self.schema_version != 1 or type(self.schema_version) is not int or
                self.mode != 'offline' or type(self.provider_spend_limit) is not int or self.provider_spend_limit != 0 or
                self.promotion_mode != 'manual' or self.allow_clinical_actions):
            raise PolicyDenied('only offline, zero-spend, nonclinical manual research supported')
        if self.sandbox_memory_mb != 256 or self.sandbox_wall_seconds != 5:
            raise ValueError('only the fixed 5-second/256-MB declarative profile is supported')
        bounds = {'max_generations':5, 'max_candidates_per_generation':3,
                  'max_population':3, 'max_revision_attempts_per_candidate':3,
                  'max_llm_calls_per_run':30, 'max_run_seconds':1800,
                  'max_artifact_bytes':MAX_BYTES, 'sandbox_wall_seconds':5,
                  'sandbox_memory_mb':256, 'max_plan_depth':5,
                  'max_simulated_nodes_per_decision':100, 'max_real_actions_per_run':20}
        for name, maximum in bounds.items():
            if type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= maximum:
                raise ValueError('invalid budget: '+name)

    @classmethod
    def load(cls, value):
        exact(value, cls.__dataclass_fields__)
        return cls(**value)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: int
    domain: str
    preconditions: dict
    action: str
    predicted_effect: dict
    completion: object
    supporting_transition_ids: list
    contradicting_transition_ids: list
    status: str = 'hypothesis'
    uncertainty: str = 'uncalibrated'
    exceptions: tuple = ()
    unresolved_alternatives: tuple = ()
    authoring_run_id: str = 'offline'

    def __post_init__(self):
        for value in (self.rule_id, self.domain, self.action, self.authoring_run_id):
            identifier(value)
        if type(self.version) is not int or self.version < 1:
            raise ValueError('positive rule version required')
        observation(self.preconditions)
        observation(self.predicted_effect)
        if self.preconditions is None or self.predicted_effect is None:
            raise ValueError('rule conditions and effects required')
        if self.completion is not None and type(self.completion) is not bool:
            raise ValueError('completion must be boolean or unknown')
        if self.status not in ('hypothesis', 'supported', 'retracted') or self.uncertainty != 'uncalibrated':
            raise ValueError('invalid rule status/uncertainty')
        for values in (self.supporting_transition_ids, self.contradicting_transition_ids):
            if type(values) is not list or len(values) != len(set(values)):
                raise ValueError('unique evidence identifiers required')
            for value in values:
                identifier(value)
        if type(self.exceptions) not in (list,tuple) or type(self.unresolved_alternatives) not in (list,tuple):
            raise ValueError('structured exception and alternative lists required')
        if len(self.exceptions) > 32 or len(self.unresolved_alternatives) > 32:
            raise ValueError('bounded exception and alternative lists required')
        if not self.supporting_transition_ids:
            raise ValueError('supporting evidence required')

    def to_dict(self):
        result = asdict(self)
        result['exceptions'] = list(result['exceptions'])
        result['unresolved_alternatives'] = list(result['unresolved_alternatives'])
        canonical(result)
        return result

    @classmethod
    def load(cls, value):
        exact(value, cls.__dataclass_fields__)
        return cls(**value)
