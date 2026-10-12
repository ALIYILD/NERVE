"""Paired cue experiments. Hosts collect evidence; this module never calls providers.

Receipts are advisory host attestations, not signatures or permission grants.
Dataset IDs must identify deduplicated examples, including paraphrase families.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isfinite, ceil, log, sqrt
from .study_statistics_v16 import mcnemar_exact_p


def _id(value):
    if type(value) is not str or not value.strip() or len(value) > 512:
        raise ValueError('nonempty bounded identifier required')


def _number(value, lower=0, upper=None):
    if type(value) not in (int, float) or not isfinite(value) or value < lower or (upper is not None and value > upper):
        raise ValueError('finite measured metric required')


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class DatasetManifest:
    discovery: tuple
    selection: tuple
    holdout: tuple

    def __post_init__(self):
        seen = set()
        for name in ('discovery', 'selection', 'holdout'):
            ids = tuple(getattr(self, name))
            if not ids:
                raise ValueError('all three dataset partitions are required')
            for item in ids:
                _id(item)
                if item in seen:
                    raise ValueError('duplicate or leaking dataset ID')
                seen.add(item)
            object.__setattr__(self, name, ids)


@dataclass(frozen=True)
class ModelParity:
    provider: str
    model: str
    revision: str
    tokenizer: str
    tokenizer_revision: str
    template_digest: str
    sampling_digest: str
    temperature: float
    max_tokens: int
    context_digest: str
    profile_key: str

    def __post_init__(self):
        for name in ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision',
                     'template_digest', 'sampling_digest', 'context_digest', 'profile_key'):
            _id(getattr(self, name))
        _number(self.temperature)
        if type(self.max_tokens) is not int or self.max_tokens <= 0:
            raise ValueError('positive output budget required')


@dataclass(frozen=True)
class Observation:
    task_id: str
    model: ModelParity
    correct: bool
    safe: bool
    confidence: float
    latency_ms: float
    cost_usd: float
    evidence_id: str
    synthetic: bool = True
    cue_digest: str = ''
    arm: str = ''

    def __post_init__(self):
        _id(self.task_id); _id(self.evidence_id)
        if self.arm not in ('', 'baseline', 'candidate') or type(self.cue_digest) is not str:
            raise ValueError('explicit arm and cue digest strings required')
        if self.cue_digest and (len(self.cue_digest) != 64 or any(c not in '0123456789abcdef' for c in self.cue_digest)):
            raise ValueError('invalid cue content digest')
        if not isinstance(self.model, ModelParity):
            raise ValueError('exact model configuration required')
        if any(type(getattr(self, name)) is not bool for name in ('correct', 'safe', 'synthetic')):
            raise ValueError('boolean observations required')
        _number(self.confidence, upper=1)
        _number(self.latency_ms)
        _number(self.cost_usd)


@dataclass(frozen=True)
class PairedResult:
    baseline: Observation
    candidate: Observation

    def __post_init__(self):
        if not isinstance(self.baseline, Observation) or not isinstance(self.candidate, Observation):
            raise ValueError('measured observations required')
        if self.baseline.task_id != self.candidate.task_id or self.baseline.model != self.candidate.model:
            raise ValueError('paired task and exact model configuration must match')
        if self.baseline.evidence_id == self.candidate.evidence_id:
            raise ValueError('distinct baseline and cue evidence required')


@dataclass(frozen=True)
class EvaluationReport:
    candidate_id: str
    profile_key: str
    split: str
    cue_digest: str
    task_type: str
    manifest: DatasetManifest
    pairs: tuple

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {
                'candidate_id', 'profile_key', 'split', 'cue_digest', 'task_type', 'manifest', 'pairs'}:
            raise ValueError('strict evaluation report schema required')
        try:
            manifest = DatasetManifest(**value['manifest'])
            pairs = []
            for pair in value['pairs']:
                if set(pair) != {'baseline', 'candidate'}:
                    raise ValueError('strict pair schema required')
                arms = []
                for arm in ('baseline', 'candidate'):
                    record = dict(pair[arm])
                    record['model'] = ModelParity(**record['model'])
                    arms.append(Observation(**record))
                pairs.append(PairedResult(*arms))
            return evaluate_pairs(value['candidate_id'], manifest, pairs,
                split=value['split'], profile_key=value['profile_key'],
                cue_digest=value['cue_digest'], task_type=value['task_type'])
        except (KeyError, TypeError) as exc:
            raise ValueError('invalid evaluation evidence schema') from exc

    @property
    def digest(self):
        return _digest(self.to_dict())

    @property
    def metrics(self):
        result = {}
        for arm in ('baseline', 'candidate'):
            observations = [getattr(pair, arm) for pair in self.pairs]
            n = len(observations)
            result[arm] = {
                'accuracy': sum(o.correct for o in observations) / n,
                'safety': sum(o.safe for o in observations) / n,
                'brier_score': sum((o.confidence - int(o.correct)) ** 2 for o in observations) / n,
                'latency_ms': sum(o.latency_ms for o in observations) / n,
                'latency_p95_ms': sorted(o.latency_ms for o in observations)[ceil(.95 * n) - 1],
                'cost_usd': sum(o.cost_usd for o in observations) / n,
            }
        better = sum(p.candidate.correct and not p.baseline.correct for p in self.pairs)
        worse = sum(p.baseline.correct and not p.candidate.correct for p in self.pairs)
        result['paired_accuracy_delta'] = result['candidate']['accuracy'] - result['baseline']['accuracy']
        # Each independent paired difference is in [-1, 1]. This conservative
        # distribution-free interval is conditional on independent task units;
        # it does not correct for repeated selection or hidden benchmark overlap.
        radius = sqrt(2 * log(2 / .05) / len(self.pairs))
        delta = result['paired_accuracy_delta']
        result['paired_accuracy_interval'] = {'method': 'hoeffding_independent_pairs',
            'confidence': .95, 'lower': max(-1., delta - radius), 'upper': min(1., delta + radius)}
        result['descriptive_mcnemar_p'] = mcnemar_exact_p(better, worse)
        result['pairs'] = len(self.pairs)
        result['synthetic'] = any(p.baseline.synthetic or p.candidate.synthetic for p in self.pairs)
        return result


def evaluate_pairs(candidate_id, manifest, pairs, *, split='holdout', profile_key=None, cue_digest='', task_type=''):
    _id(candidate_id)
    if not isinstance(manifest, DatasetManifest) or split not in ('selection', 'holdout'):
        raise ValueError('selection or untouched holdout manifest required')
    rows = tuple(pairs)
    if not rows or any(not isinstance(p, PairedResult) for p in rows):
        raise ValueError('nonempty paired observations required')
    ids = [p.baseline.task_id for p in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(getattr(manifest, split)):
        raise ValueError('exact partition coverage required; no duplicates or foreign examples')
    evidence = [o.evidence_id for p in rows for o in (p.baseline, p.candidate)]
    if len(set(evidence)) != len(evidence):
        raise ValueError('reused observation evidence')
    model = rows[0].baseline.model
    if any(p.baseline.model != model for p in rows):
        raise ValueError('mixed experiment configuration')
    if profile_key is not None and model.profile_key != profile_key:
        raise ValueError('candidate profile mismatch')
    return EvaluationReport(candidate_id, model.profile_key, split, cue_digest, task_type, manifest, tuple(sorted(rows, key=lambda p: p.baseline.task_id)))


@dataclass(frozen=True)
class IndependentReceipt:
    evaluator_id: str
    candidate_id: str
    report_digest: str
    approved: bool

    def __post_init__(self):
        for name in ('evaluator_id', 'candidate_id', 'report_digest'):
            _id(getattr(self, name))
        if type(self.approved) is not bool:
            raise ValueError('explicit evaluator verdict required')


@dataclass(frozen=True)
class PromotionDecision:
    eligible: bool
    reasons: tuple
    report_digest: str

    def to_dict(self):
        return asdict(self)


def promotion_decision(report, receipts=(), *, min_pairs=30, generator_id=None):
    """Eligibility only. Host must authenticate receipts and separately approve.

    Min-pair and descriptive significance gates are conservative screening, not
    a statistical claim after repeated candidate selection. Host preregisters
    experiments and prevents holdout reuse and correlated-example leakage.
    """
    if not isinstance(report, EvaluationReport):
        raise ValueError('evaluation report required')
    # Revalidate even reports directly constructed by callers.
    checked = evaluate_pairs(report.candidate_id, report.manifest, report.pairs,
                             split=report.split, profile_key=report.profile_key,
                             cue_digest=report.cue_digest, task_type=report.task_type)
    if type(min_pairs) is not int or min_pairs < 30:
        raise ValueError('at least 30 heldout pairs required')
    reasons = []
    if type(report.cue_digest) is not str or len(report.cue_digest) != 64 or any(c not in '0123456789abcdef' for c in report.cue_digest):
        reasons.append('cue_content_binding_required')
    if type(report.task_type) is not str or not report.task_type.strip():
        reasons.append('task_type_binding_required')
    metrics = checked.metrics
    baseline, candidate = metrics['baseline'], metrics['candidate']
    if any(p.baseline.arm != 'baseline' or p.baseline.cue_digest != '' or
           p.candidate.arm != 'candidate' or p.candidate.cue_digest != report.cue_digest for p in report.pairs):
        reasons.append('observation_cue_binding_required')
    if report.split != 'holdout': reasons.append('untouched_holdout_required')
    if metrics['pairs'] < min_pairs: reasons.append('insufficient_pairs')
    if metrics['synthetic']: reasons.append('live_evidence_required')
    if metrics['paired_accuracy_delta'] <= 0: reasons.append('accuracy_gain_required')
    if metrics['descriptive_mcnemar_p'] > .05: reasons.append('weak_paired_evidence')
    if any(not p.candidate.safe for p in report.pairs): reasons.append('safety_failure')
    for metric in ('brier_score', 'latency_ms', 'latency_p95_ms', 'cost_usd'):
        if candidate[metric] > baseline[metric]: reasons.append(metric + '_regression')
    receipts = tuple(receipts)
    if generator_id is None:
        reasons.append('generator_identity_required')
    elif type(generator_id) is not str or not generator_id.strip():
        reasons.append('generator_identity_required')
    elif not any(isinstance(r, IndependentReceipt) and r.approved and
                 r.evaluator_id != generator_id and r.candidate_id == report.candidate_id and
                 r.report_digest == checked.digest for r in receipts):
        reasons.append('independent_receipt_required')
    if any(isinstance(r, IndependentReceipt) and not r.approved and
           r.candidate_id == report.candidate_id and r.report_digest == checked.digest for r in receipts):
        reasons.append('evaluator_rejected')
    return PromotionDecision(not reasons, tuple(reasons), checked.digest)


def discover_candidates(execute, manifest, *, tenant, agent, max_candidates=4):
    """Use the existing Hermes research role; never send selection/holdout IDs.

    Returns untrusted proposals only. Registry safety validation is mandatory.
    Hermes and the hosting process remain responsible for provider cost limits.
    """
    if not callable(execute) or not isinstance(manifest, DatasetManifest):
        raise ValueError('existing Hermes callback and manifest required')
    _id(tenant); _id(agent)
    if type(max_candidates) is not int or not 1 <= max_candidates <= 16:
        raise ValueError('bounded candidate count required')
    result = execute('research', {'operation': 'propose_cognitive_cues',
        'discovery_ids': list(manifest.discovery), 'max_candidates': max_candidates},
        tenant=tenant, agent=agent)
    if type(result) is not dict or set(result) != {'candidates'} or type(result['candidates']) is not list:
        raise ValueError('candidate list required')
    candidates = result['candidates']
    if len(candidates) > max_candidates or any(type(c) is not str or not c.strip() or len(c) > 512 for c in candidates):
        raise ValueError('invalid or excessive candidate output')
    if len(set(candidates)) != len(candidates):
        raise ValueError('duplicate candidate output')
    return tuple(candidates)
