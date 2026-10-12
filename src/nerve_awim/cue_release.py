"""Offline CCE release review: snapshots and attestations, never authorization.

Inputs must be collected by the trusted host. Receipts are attestations rather
than signatures; this builder neither performs staging nor authenticates their
issuer. It emits no prompts, cue text, answers or task-level observations.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
import time

from .cue_engine import ModelProfile
from .cue_evaluation import EvaluationReport, IndependentReceipt, promotion_decision
from .governed_learning_v20 import _id


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _digest(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('SHA256 evidence binding required')


def _time(value):
    if type(value) not in (int, float) or not isfinite(value) or value <= 0:
        raise ValueError('finite positive timestamp required')


@dataclass(frozen=True)
class StagingReceipt:
    evidence_id: str
    candidate: str
    report_digest: str
    profile_key: str
    worker_attested: bool
    cue_applied: bool
    smoke_passed: bool
    observed_at: float
    synthetic: bool = True

    def __post_init__(self):
        _id(self.evidence_id); _id(self.candidate)
        _digest(self.report_digest); _digest(self.profile_key); _time(self.observed_at)
        for name in ('worker_attested', 'cue_applied', 'smoke_passed', 'synthetic'):
            if type(getattr(self, name)) is not bool:
                raise ValueError('explicit staging verdicts required')


@dataclass(frozen=True)
class RollbackReceipt:
    evidence_id: str
    candidate: str
    profile_key: str
    target: str
    verified: bool
    observed_at: float
    synthetic: bool = True

    def __post_init__(self):
        _id(self.evidence_id); _id(self.candidate); _digest(self.profile_key)
        _time(self.observed_at)
        if self.target != 'no-cue' or type(self.verified) is not bool or type(self.synthetic) is not bool:
            raise ValueError('explicit verified no-cue rollback required')


_ACTIONS = {
    'host_disabled': 'Review explicit host configuration; keep routing disabled until approval.',
    'profile_unconfigured': 'Configure the exact installed model profile for handoff.',
    'profile_mismatch': 'Re-evaluate against the exact configured model and tokenizer revisions.',
    'profile_unpinned': 'Record pinned provider, model, tokenizer and template revisions.',
    'candidate_missing': 'Select a candidate from the scoped governed coordinator.',
    'candidate_not_approved': 'Obtain operator approval through existing governed activation.',
    'candidate_ineligible_state': 'Run a new preregistered experiment for a fresh candidate.',
    'candidate_not_active': 'Verify the approved candidate is the current scoped route.',
    'evidence_expired': 'Collect fresh evidence and a current time-limited approval.',
    'evaluation_missing': 'Complete the frozen holdout using trusted measured observations.',
    'evaluation_invalid': 'Repair invalid evidence or bindings; never invent missing metrics.',
    'stored_evidence_mismatch': 'Investigate altered report, metrics or decision records.',
    'staging_missing': 'Run a controlled staging worker with exact runtime attestation and smoke checks.',
    'staging_invalid': 'Repeat staging with fresh, live, candidate-bound worker and smoke receipts.',
    'rollback_missing': 'Verify scoped cue revocation restores the no-cue baseline in staging.',
    'rollback_invalid': 'Repeat a live no-cue rollback drill for this candidate and exact profile.',
    'unsupported_task': 'Use the supported low-risk nonclinical handoff context only.',
    'dataset_binding_required': 'Collect fresh evidence through the dataset-bound cycle; legacy evidence cannot be retroactively bound.',
}


def build_release_manifest(*, profile_name, profile, host_status, candidate_status,
                           generator_id, staging=None, rollback=None, now=None):
    """Review a single exact-profile release, without touching DBs or providers.

    A clear manifest describes readiness at the supplied snapshot time only.
    It is not an activation token; the coordinator still checks current scope,
    generation, approval, expiry and permissions at use time.
    """
    _id(profile_name); _id(generator_id)
    if not isinstance(profile, ModelProfile):
        raise ValueError('exact model profile required')
    now = time.time() if now is None else now
    _time(now)
    if type(host_status) is not dict or set(host_status) != {'enabled', 'reason', 'profiles'}:
        raise ValueError('CueHost.status snapshot required')
    if type(host_status['enabled']) is not bool or type(host_status['profiles']) is not dict:
        raise ValueError('typed host status required')
    if staging is not None and not isinstance(staging, StagingReceipt):
        raise ValueError('typed staging receipt required')
    if rollback is not None and not isinstance(rollback, RollbackReceipt):
        raise ValueError('typed rollback receipt required')
    blockers = []
    def block(reason):
        if reason not in blockers: blockers.append(reason)
    if not host_status['enabled'] or host_status['reason'] != 'enabled': block('host_disabled')
    unpinned = {'unknown', 'unspecified', 'latest', 'auto', 'default', 'none'}
    if any(getattr(profile, f).strip().lower() in unpinned for f in
           ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision', 'template_revision')):
        block('profile_unpinned')
    entry = host_status['profiles'].get(profile_name)
    if type(entry) is not dict or entry.get('configured') is not True:
        block('profile_unconfigured'); entry = {}
    if entry.get('profile_key') != profile.key: block('profile_mismatch')
    if entry.get('task_type') != 'handoff' or profile.supported_modes != ('instruction',):
        block('unsupported_task')
    candidate, report, metrics, decision = None, None, None, None
    dataset = None
    state, expires = None, None
    if candidate_status is None:
        block('candidate_missing')
    else:
        if (type(candidate_status) is not dict or
                set(candidate_status) not in (
                    {'candidate','status','task_type','expires','evaluation','profile_key','generator_id'},
                    {'candidate','status','task_type','expires','evaluation','profile_key','generator_id','dataset'})):
            raise ValueError('coordinator.status snapshot required')
        dataset = candidate_status.get('dataset')
        if 'dataset' in candidate_status:
            if (type(dataset) is not dict or set(dataset) != {'required','bound','digest'}
                    or type(dataset['required']) is not bool or type(dataset['bound']) is not bool):
                raise ValueError('typed dataset binding status required')
            if dataset['bound']:
                _digest(dataset['digest'])
            elif dataset['digest'] is not None:
                raise ValueError('unbound dataset cannot claim a digest')
            if dataset['required'] and not dataset['bound']:
                block('dataset_binding_required')
            dataset = dict(dataset)
        candidate = _id(candidate_status['candidate'])
        if candidate_status['profile_key'] != profile.key: block('profile_mismatch')
        if candidate_status['generator_id'] != generator_id:
            raise ValueError('generator identity must match governed candidate')
        state, expires = candidate_status['status'], candidate_status['expires']
        if state not in ('passed', 'approved'): block('candidate_ineligible_state')
        if state != 'approved': block('candidate_not_approved')
        if entry.get('active_candidate') != candidate: block('candidate_not_active')
        if candidate_status['task_type'] != 'handoff': block('unsupported_task')
        if type(expires) not in (int,float) or not isfinite(expires) or expires <= now:
            block('evidence_expired')
            expires = None
        evidence = candidate_status['evaluation']
        if evidence is None:
            block('evaluation_missing')
        else:
            try:
                if type(evidence) is not dict or set(evidence) != {'report','metrics','receipt','decision'}:
                    raise ValueError('strict stored evaluation required')
                report = EvaluationReport.from_dict(evidence['report'])
                receipt = IndependentReceipt(**evidence['receipt'])
                decision = promotion_decision(report, (receipt,), generator_id=generator_id)
                metrics = report.metrics
                if report.candidate_id != candidate or report.profile_key != profile.key:
                    block('profile_mismatch')
                if report.task_type != 'handoff': block('unsupported_task')
                model = report.pairs[0].baseline.model
                if any(getattr(model, f) != getattr(profile, f) for f in
                       ('provider','model','revision','tokenizer','tokenizer_revision')):
                    block('profile_mismatch')
                if _hash(evidence['metrics']) != _hash(metrics) or _hash(evidence['decision']) != _hash(decision.to_dict()):
                    block('stored_evidence_mismatch')
                for reason in decision.reasons: block('evaluation:' + reason)
            except (ValueError, TypeError, KeyError, AttributeError):
                report, metrics, decision = None, None, None
                block('evaluation_invalid')
    if staging is None:
        block('staging_missing')
    elif (report is None or staging.candidate != candidate or staging.profile_key != profile.key or
          staging.report_digest != report.digest or staging.synthetic or not staging.worker_attested or
          not staging.cue_applied or not staging.smoke_passed or not 0 <= now-staging.observed_at <= 86400):
        block('staging_invalid')
    if rollback is None:
        block('rollback_missing')
    elif (rollback.candidate != candidate or rollback.profile_key != profile.key or rollback.synthetic or
          not rollback.verified or not 0 <= now-rollback.observed_at <= 86400 or
          (staging is not None and staging.evidence_id == rollback.evidence_id)):
        block('rollback_invalid')
    value = {'schema_version':1, 'kind':'cce-release-readiness', 'profile_name':profile_name,
        'profile_key':profile.key, 'candidate':candidate, 'candidate_state':state,
        'dataset':dataset,
        'checked_at':now, 'evidence_expires':expires, 'ready':not blockers,
        'authorization_granted':False, 'blockers':blockers,
        'next_steps':[_ACTIONS.get(reason, 'Resolve '+reason+' with fresh independent evidence.') for reason in blockers],
        'report_digest':report.digest if report else None, 'metrics':metrics,
        'staging_evidence_id':staging.evidence_id if staging else None,
        'rollback':{'target':'no-cue', 'action':'revoke_candidate',
                    'evidence_id':rollback.evidence_id if rollback else None},
        'scope':'low-risk nonclinical handoff; exact model profile only',
        'limitation':'Trusted host snapshots and attestations; not deployment authorization.'}
    value['manifest_digest'] = _hash(value)
    return value
