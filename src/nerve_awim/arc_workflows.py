"""Local ARC vertical slices using NERVE's governed dispatcher and SQLite store.

Clinical records here are synthetic ONLY. No DeepSynaps API contract is present
in this repository; this typed boundary does not invent an external endpoint.
No registered handler can submit a referral, prescribe or send a message.
"""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from pathlib import Path
import time

from .agent_learning_v12 import AgentTask, RegisteredStrategy
from .governed_learning_v20 import GovernedLearning, LearningAuthority
from .repository_agents_v20 import ast_inventory, token_inventory


@dataclass(frozen=True)
class SyntheticAssessment:
    assessment_id: str
    tenant_scope: str
    captured_at: float
    valid_until: float
    findings: str
    approved: bool

    def __post_init__(self):
        import math
        if not all(type(v) is str and 0 < len(v) <= 2048 for v in
                   (self.assessment_id, self.tenant_scope, self.findings)):
            raise ValueError('bounded synthetic assessment fields required')
        if (type(self.approved) is not bool or
                any(type(v) not in (int, float) or not math.isfinite(v)
                    for v in (self.captured_at, self.valid_until)) or
                self.valid_until < self.captured_at):
            raise ValueError('valid assessment timestamps and explicit approval required')


@dataclass(frozen=True)
class ReferralDraft:
    schema_version: str
    synthetic: bool
    findings: str
    assessment_id: str
    citations: list
    unknowns: list
    review_state: str
    submitted: bool = False


class SyntheticClinicalBoundary:
    """Host-scoped synthetic evidence retrieval, never a live clinical connector."""
    def __init__(self, tenant):
        self.tenant = tenant

    def retrieve(self, raw, *, accessible=True):
        if not accessible or raw is None:
            return None
        if type(raw) is not dict:
            raise ValueError('typed synthetic assessment required')
        # Exclude other tenants before reading or validating their content.
        if raw.get('tenant_scope') != self.tenant:
            return None
        return SyntheticAssessment(**raw)


def _arguments(value):
    if type(value) is not dict or set(value) != {'payload'}:
        raise ValueError('exact payload argument required')
    json.dumps(value, allow_nan=False)


def _content_hash(content):
    return sha256(json.dumps(content, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _binding(source, content, refs):
    return any(ref.get('source_id') == source and
               ref.get('reference_to_redacted_or_protected_content') == 'sha256:' + _content_hash(content)
               for ref in refs)


def _validate_inventory(arguments):
    _arguments(arguments)
    if type(arguments['payload']) is not str:
        raise ValueError('inventory requires Python source text')


def _validate_referral(arguments, now):
    _arguments(arguments)
    payload = arguments['payload']
    if type(payload) is not dict or set(payload) != {'assessment', 'source_hash'}:
        raise ValueError('assessment and source hash required')
    assessment = SyntheticAssessment(**payload['assessment'])
    if not assessment.approved or not assessment.captured_at <= now <= assessment.valid_until:
        raise ValueError('fresh approved assessment required')
    if payload['source_hash'] != _content_hash(payload['assessment']):
        raise ValueError('assessment hash mismatch')


def _draft(payload):
    assessment = SyntheticAssessment(**payload['assessment'])
    return asdict(ReferralDraft('synthetic-referral-v1', True,
        assessment.findings, assessment.assessment_id,
        [{'source_id': 'assessment', 'field': 'findings',
          'source_hash': payload['source_hash']}], [], 'awaiting_clinician_review'))


def _verify_draft(value, arguments):
    payload = arguments['payload']
    assessment = payload['assessment']
    good = (type(value) is dict and value.get('synthetic') is True and
            value.get('schema_version') == 'synthetic-referral-v1' and
            value.get('findings') == assessment['findings'] and
            value.get('assessment_id') == assessment['assessment_id'] and
            value.get('citations') == [{'source_id': 'assessment', 'field': 'findings',
                                       'source_hash': payload['source_hash']}] and
            value.get('unknowns') == [] and
            value.get('review_state') == 'awaiting_clinician_review' and
            value.get('submitted') is False)
    return {'objective': good}


def _verify_inventory(value, arguments):
    try:
        correct = type(value) is list and value == token_inventory(arguments['payload'])
    except Exception:
        correct = False
    return {'objective': correct}


def _verify_abstention(value, arguments):
    return {'objective': type(value) is dict and value == arguments['payload']}


def build_workflow_engine(path, *, tenant='synthetic', mode='full', now=None,
                          outcome_verified=True, tool_failure=False, offline_evaluation=False):
    """Compose existing host authority/dispatcher; no new memory or scheduler.

    baseline/structured are explicitly labelled offline benchmark ablations.
    They are not selectable releases or provider-controlled settings.
    """
    from .arc_execution import ArcRuntime, ToolSpec
    if mode not in ('full', 'baseline', 'structured'):
        raise ValueError('unknown offline workflow evaluation mode')
    if mode != 'full' and offline_evaluation is not True:
        raise PermissionError('ablation modes require explicit offline evaluation')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    authority = LearningAuthority()
    runtime_actor = authority.issue(tenant, 'arc-workflow', 'runtime')
    operator = authority.issue(tenant, 'arc-workflow', 'operator')
    receipt = {}
    handlers = {'inventory': lambda p: ast_inventory(p), 'prepare-draft': _draft,
                'request-information': lambda p: p, 'await-review': lambda p: p, 'no-action': lambda p: p}
    verifiers = {'inventory': _verify_inventory, 'prepare-draft': _verify_draft,
                 'request-information': _verify_abstention, 'await-review': _verify_abstention, 'no-action': _verify_abstention}
    strategies, specs = [], {}
    for name, handler in handlers.items():
        def wrapped(arguments, handler=handler, name=name):
            if tool_failure and name in ('inventory', 'prepare-draft'):
                raise RuntimeError('synthetic tool failure')
            value = handler(arguments['payload'])
            if not outcome_verified and name in ('inventory', 'prepare-draft'):
                value = None  # Transport returned, but required result is absent.
            receipt['value'] = value
            receipt['dispatches'] = receipt.get('dispatches', 0) + 1
            return value
        strategies.append(RegisteredStrategy(name, name, wrapped))
        verifier = verifiers[name] if mode != 'structured' else lambda result, args: {'objective': True}
        validator = _validate_inventory if name == 'inventory' else (
            (lambda arguments: _validate_referral(arguments, now if now is not None else time.time()))
            if name == 'prepare-draft' else _arguments)
        binding = (lambda args, refs: _binding('input', args['payload'], refs)) if name == 'inventory' else (
            (lambda args, refs: _binding('assessment', args['payload']['assessment'], refs) and
             args['payload']['assessment']['tenant_scope'] == tenant)
            if name == 'prepare-draft' else None)
        required = ('input',) if name == 'inventory' else ('assessment',) if name == 'prepare-draft' else ()
        specs[name] = ToolSpec(context=name, validate_arguments=validator, verify=verifier,
                              required_sources=required, evidence_bindings=binding)
    engine = GovernedLearning(path, authority=authority, strategies=strategies,
        judge=lambda task, value: verifiers[task.context](value, task.payload)['objective'],
        contract_revision='arc-workflows-v1-' + mode,
        baseline_routes={name: name for name in handlers})
    try:
        engine.status(operator)
    except LookupError:
        engine.bootstrap(operator)
    runtime = ArcRuntime(engine, tools=specs, mode='off' if mode == 'baseline' else 'enforce', clock=(lambda: now) if now is not None else time.time)
    return {'engine': engine, 'runtime': runtime, 'actor': runtime_actor,
            'operator': operator, 'receipt': receipt, 'tools': specs}


def _select(scenario, tenant, now):
    workflow = scenario.get('workflow', 'inventory')
    if workflow == 'inventory':
        source = scenario.get('source')
        if source is None:
            return 'request-information', {'reason': 'missing_source', 'unknowns': ['source']}, {}, ['source']
        if type(source) is not str:
            raise ValueError('Python source must be text')
        action, payload, evidence, unknowns = 'inventory', source, {'input': source}, []
    elif workflow == 'clinical':
        if scenario.get('synthetic', True) is not True:
            raise ValueError('only synthetic clinical fixtures are authorized')
        raw = scenario.get('assessment')
        boundary = SyntheticClinicalBoundary(tenant)
        assessment = boundary.retrieve(raw, accessible=scenario.get('accessible', True))
        if assessment is None:
            return 'request-information', {'reason': 'assessment_unavailable', 'unknowns': ['assessment']}, {}, ['assessment']
        evidence = {'assessment': asdict(assessment)}
        other = boundary.retrieve(scenario.get('conflicting_assessment'), accessible=scenario.get('accessible', True))
        if other is not None and other.findings != assessment.findings:
            evidence['conflicting_assessment'] = asdict(other)
            return 'await-review', {'reason': 'conflicting_assessment', 'unknowns': ['resolved_assessment']}, evidence, ['resolved_assessment']
        if not assessment.captured_at <= now <= assessment.valid_until:
            return 'await-review', {'reason': 'stale_assessment', 'unknowns': ['current_assessment']}, evidence, ['current_assessment']
        if not scenario.get('approved', assessment.approved) or not assessment.approved:
            return 'await-review', {'reason': 'unapproved_assessment', 'unknowns': ['assessment_approval']}, evidence, ['assessment_approval']
        source_hash = _content_hash(asdict(assessment))
        action, payload, unknowns = 'prepare-draft', {'assessment': asdict(assessment), 'source_hash': source_hash}, []
    else:
        raise ValueError('registered workflow required')
    if not scenario.get('tool_available', True):
        return 'await-review', {'reason': 'tool_unavailable', 'unknowns': ['tool_availability']}, evidence, ['tool_availability']
    if scenario.get('strategy') == 'conservative':
        return 'await-review', {'reason': 'conservative_strategy', 'unknowns': []}, evidence, []
    return action, payload, evidence, unknowns


def run_workflow(db_path, scenario, *, mode='full', offline_evaluation=False):
    """Execute one synthetic/local task through the production dispatcher.

    Outcome injection is host-only offline test configuration, never untrusted
    decision arguments. No Python input is executed: inventory parses it only.
    """
    tenant = scenario.get('tenant', 'synthetic')
    now = scenario.get('now', time.time())
    task_id = scenario.get('task_id', 'local-workflow')
    action, payload, evidence, unknowns = _select(scenario, tenant, now)
    components = build_workflow_engine(db_path, tenant=tenant, mode=mode, now=now,
        outcome_verified=scenario.get('outcome_verified', True), tool_failure=scenario.get('tool_failure', False),
        offline_evaluation=offline_evaluation)
    engine, runtime, actor = (components[k] for k in ('engine', 'runtime', 'actor'))
    result = {'action': action, 'mode': mode, 'permitted': True, 'unknowns': unknowns,
              'verified': False, 'decision_id': None, 'outcome_id': None,
              'offline': True, 'synthetic': scenario.get('workflow') == 'clinical'}
    if mode == 'baseline':
        try:
            value = engine.execute(actor, AgentTask(task_id, action, {'payload': payload}))['value']
            result.update(value=value, status='succeeded', verified=action in ('inventory', 'prepare-draft'))
        except Exception:
            result.update(value=None, status='failed')
        return result
    refs = [runtime.snapshot(actor, source_id, content, source_type='synthetic' if scenario.get('workflow') == 'clinical' else 'local')
            for source_id, content in evidence.items()]
    # Empty observations remain explicit; never fabricate an assessment snapshot.
    decision = runtime.propose(actor, task_id, action, {'payload': payload}, refs,
        goal='Inventory Python functions' if scenario.get('workflow', 'inventory') == 'inventory' else 'Prepare a synthetic referral draft for clinician review',
        completion_criteria=['objective'], unknowns=unknowns, domain='synthetic-clinical' if scenario.get('workflow') == 'clinical' else 'nonclinical')
    try:
        outcome = runtime.execute(actor, decision.decision_id)
    except PermissionError:
        result.update(decision_id=decision.decision_id, status='blocked', permitted=False,
                      value=None, dispatches=0, reason='Dispatch denied by current authorization or release mode')
        return result
    if type(outcome) is dict and outcome.get('status') == 'shadow':
        result.update(decision_id=decision.decision_id, status='shadow', value=None, dispatches=0)
        return result
    result.update(decision_id=decision.decision_id, outcome_id=outcome.outcome_id,
        status='succeeded' if outcome.semantic_status == 'verified' else 'failed',
        semantic_status=outcome.semantic_status,
        verified=outcome.semantic_status == 'verified' and action in ('inventory', 'prepare-draft'),
        value=components['receipt'].get('value'), dispatches=components['receipt'].get('dispatches', 0))
    if scenario.get('restart'):
        from .arc_execution import ArcRuntime
        resumed = build_workflow_engine(db_path, tenant=tenant, mode=mode, now=now, offline_evaluation=offline_evaluation)
        again = resumed['runtime'].execute(resumed['actor'], decision.decision_id)
        result['restart_same_outcome'] = again.outcome_id == outcome.outcome_id
        result['dispatches'] = components['receipt'].get('dispatches', 0)
    return result
