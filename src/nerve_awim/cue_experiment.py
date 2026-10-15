"""Bounded experiments over existing injected provider and evaluator adapters.

Callbacks are trusted host integrations. Provider must enforce the per-call cost
cap before dispatch (including retries), isolation, timeouts and permissions.
This synchronous runner cannot terminate a callback or enforce remote billing.
No prompt, expected answer or generated output is written to an evidence report.
"""
from dataclasses import dataclass
from time import perf_counter
from hashlib import sha256
from .cue_engine import Cue, safety_reason
from .cue_evaluation import (
    DatasetManifest, ModelParity, Observation, PairedResult, evaluate_pairs, _id, _number,
)


@dataclass(frozen=True)
class ExperimentTask:
    task_id: str
    instruction: str
    expected: str

    def __post_init__(self):
        _id(self.task_id)
        for field in ('instruction', 'expected'):
            value = getattr(self, field)
            if type(value) is not str or not value or len(value) > 65536:
                raise ValueError('bounded task text required')


@dataclass(frozen=True)
class ProviderRequest:
    task_id: str
    instruction: str
    cue_prefix: str
    cue_mode: str
    cue_digest: str
    arm: str
    model: ModelParity
    cost_cap_usd: float


@dataclass(frozen=True)
class ProviderReceipt:
    """Trusted adapter receipt; confidence is a measured probability, not inferred."""
    output: str
    confidence: float | None
    model: ModelParity
    cost_usd: float
    evidence_id: str
    synthetic: bool = True
    error: bool = False
    cue_digest: str = ''
    arm: str = ''
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self):
        if type(self.output) is not str or len(self.output) > 1000000:
            raise ValueError('bounded provider output required')
        if self.confidence is not None:
            _number(self.confidence, upper=1)
        for tokens in (self.input_tokens, self.output_tokens):
            if tokens is not None and (type(tokens) is not int or tokens < 0):
                raise ValueError('measured nonnegative integer token counts required')
        _number(self.cost_usd); _id(self.evidence_id)
        if self.arm not in ('', 'baseline', 'candidate') or type(self.cue_digest) is not str:
            raise ValueError('cue receipt binding required')
        if self.cue_digest and (len(self.cue_digest) != 64 or any(c not in '0123456789abcdef' for c in self.cue_digest)):
            raise ValueError('invalid cue receipt digest')
        if not isinstance(self.model, ModelParity) or type(self.synthetic) is not bool or type(self.error) is not bool:
            raise ValueError('explicit provider metadata required')


@dataclass(frozen=True)
class JudgeReceipt:
    correct: bool
    safe: bool

    def __post_init__(self):
        if type(self.correct) is not bool or type(self.safe) is not bool:
            raise ValueError('independent boolean verdict required')


class ExperimentBlocked(RuntimeError):
    """Partial experiment cannot qualify. Contains counts only, never raw output."""
    def __init__(self, reason, *, attempted_calls, failed_calls, known_cost_usd):
        super().__init__(reason)
        self.reason = reason
        self.attempted_calls = attempted_calls
        self.failed_calls = failed_calls
        self.known_cost_usd = known_cost_usd


def run_experiment(candidate_id, cue, manifest, tasks, model, provider, judge, *,
                   max_calls, max_cost_usd, per_call_cost_cap_usd, split='holdout',
                   clock=perf_counter, permission_granted=False, clinical=False, risk='low'):
    """Run all frozen split tasks in alternating arm order, without outcome filtering.

    Provider receives ProviderRequest. Judge receives only keyword arguments
    output and expected; it receives no cue, arm, provider or mutable task list.
    A provider error with a complete billing receipt counts as a failed unsafe
    outcome. Unknown billing or callback exceptions block the entire experiment.
    """
    _id(candidate_id)
    if permission_granted is not True or clinical is not False or risk != 'low':
        raise PermissionError('explicit permission and low-risk nonclinical experiment required')
    if not isinstance(cue, Cue) or safety_reason(cue):
        raise ValueError('safe registered cue required')
    if len(cue.task_types) != 1:
        raise ValueError('single preregistered task type required')
    if cue.task_types[0].lower() in ('clinical', 'medical', 'diagnosis', 'treatment'):
        raise PermissionError('clinical research cues remain disabled')
    if not isinstance(model, ModelParity) or model.profile_key != cue.profile_key:
        raise ValueError('exact candidate model binding required')
    if not isinstance(manifest, DatasetManifest) or split not in ('selection', 'holdout', 'regression'):
        raise ValueError('frozen evaluation split required')
    frozen = tuple(tasks)
    if any(not isinstance(t, ExperimentTask) for t in frozen):
        raise ValueError('frozen task records required')
    instruction_hashes = [sha256(t.instruction.strip().encode()).hexdigest() for t in frozen]
    if len(set(instruction_hashes)) != len(instruction_hashes):
        raise ValueError('duplicate instruction content in experiment')
    # Cross-split duplicates and paraphrase families remain host manifest duties.
    ids = [t.task_id for t in frozen]
    if len(ids) != len(set(ids)) or set(ids) != set(getattr(manifest, split)):
        raise ValueError('exact evaluation partition required')
    if type(max_calls) is not int or not 1 <= max_calls <= 20000 or 2 * len(frozen) > max_calls:
        raise ValueError('insufficient or invalid provider call budget')
    _number(max_cost_usd); _number(per_call_cost_cap_usd)
    if per_call_cost_cap_usd <= 0 or 2 * len(frozen) * per_call_cost_cap_usd > max_cost_usd:
        raise ValueError('full worst-case experiment cost must fit budget')
    if not callable(provider) or not callable(judge) or not callable(clock):
        raise ValueError('existing provider, independent judge and clock required')
    attempted, failed, known_cost = 0, 0, 0.0
    pairs = []

    def blocked(reason):
        return ExperimentBlocked(reason, attempted_calls=attempted,
                                 failed_calls=failed, known_cost_usd=known_cost)

    for index, task in enumerate(frozen):
        observations = {}
        for arm in (('baseline', 'candidate') if index % 2 == 0 else ('candidate', 'baseline')):
            request = ProviderRequest(task.task_id, task.instruction,
                cue.text if arm == 'candidate' else '', cue.mode if arm == 'candidate' else '',
                cue.content_hash if arm == 'candidate' else '', arm, model, per_call_cost_cap_usd)
            attempted += 1
            start = clock()
            try:
                receipt = provider(request)
            except Exception:
                failed += 1
                raise blocked('provider_error_or_unknown_cost') from None
            elapsed = (clock() - start) * 1000
            if not isinstance(receipt, ProviderReceipt):
                failed += 1
                raise blocked('complete_provider_receipt_required')
            known_cost += receipt.cost_usd
            if receipt.cost_usd > per_call_cost_cap_usd or known_cost > max_cost_usd:
                failed += 1
                raise blocked('provider_cost_cap_violated')
            if receipt.model != model:
                failed += 1
                raise blocked('provider_model_parity_violation')
            if receipt.cue_digest != request.cue_digest or receipt.arm != request.arm:
                failed += 1
                raise blocked('provider_cue_binding_violation')
            if receipt.error:
                failed += 1
                verdict = JudgeReceipt(False, False)
            else:
                try:
                    verdict = judge(output=receipt.output, expected=task.expected)
                    if not isinstance(verdict, JudgeReceipt):
                        raise ValueError('independent verdict required')
                except Exception:
                    failed += 1
                    raise blocked('independent_judge_failed') from None
            try:
                observations[arm] = Observation(task.task_id, model, verdict.correct, verdict.safe,
                    receipt.confidence, elapsed, receipt.cost_usd, receipt.evidence_id, receipt.synthetic,
                    request.cue_digest, arm, receipt.input_tokens, receipt.output_tokens)
            except ValueError:
                failed += 1
                raise blocked('invalid_measured_observation') from None
        pairs.append(PairedResult(observations['baseline'], observations['candidate']))
    return evaluate_pairs(candidate_id, manifest, pairs, split=split, profile_key=model.profile_key,
                          cue_digest=cue.content_hash, task_type=cue.task_types[0])
