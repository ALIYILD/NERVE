"""One bounded CCE improvement step for the existing AWIM loop to invoke.

There is no scheduler or automatic deployment here. Host adapters enforce remote
billing, retries, timeout and isolation; local counters limit dispatches and reject
missing or excessive receipts. A reserved study is consumed even after failure.
"""
from dataclasses import dataclass
from hashlib import sha256
from time import perf_counter
import uuid

from .cue_engine import Cue, ModelProfile, safety_reason
from .cue_evaluation import DatasetManifest, ModelParity, discover_candidates, _id, _number
from .cue_experiment import ExperimentTask, ProviderReceipt, ExperimentBlocked, run_experiment
from .cue_learning import GovernedCueCoordinator


@dataclass(frozen=True)
class DiscoveryReceipt:
    """Host attestation for one discovery dispatch, including any internal retries."""
    result: dict
    cost_usd: float
    synthetic: bool = True

    def __post_init__(self):
        _number(self.cost_usd)
        if type(self.result) is not dict or type(self.synthetic) is not bool:
            raise ValueError('complete discovery receipt required')


def run_cue_cycle(coordinator, trainer, evaluator, *, profile, model, task_type,
                  manifest, selection_tasks, holdout_tasks, discovery_execute,
                  provider, judge, generator_id, evaluator_id, max_calls,
                  max_cost_usd, discovery_cost_cap_usd, per_call_cost_cap_usd,
                  permission_granted=False, clinical=False, risk='low',
                  experiment_clock=perf_counter, uncertainty=None):
    """Discover one proposal, screen selection, evaluate untouched holdout, stop.

    ``discovery_execute`` is a trusted adapter with the existing Hermes execute
    signature plus ``cost_cap_usd`` and a DiscoveryReceipt return value. It must
    enforce this cap before dispatch. Discovery gets IDs only, never test content
    or expected answers. Trainer/evaluator capabilities must share an exact scope.
    A successful result is pending operator approval, never an active route.
    """
    if not isinstance(coordinator, GovernedCueCoordinator):
        raise TypeError('existing governed cue coordinator required')
    scope = coordinator._scope(trainer, 'trainer')
    if coordinator._scope(evaluator, 'evaluator') != scope:
        raise PermissionError('trainer and evaluator scopes must match')
    _id(task_type)
    if (not coordinator.enabled or permission_granted is not True or clinical is not False
            or risk != 'low' or task_type.lower() in ('clinical', 'medical', 'diagnosis', 'treatment')):
        raise PermissionError('enabled low-risk nonclinical cycle and host permission required')
    for value in (task_type, generator_id, evaluator_id):
        _id(value)
    if generator_id == evaluator_id:
        raise ValueError('independent evaluator identity required')
    if (not isinstance(profile, ModelProfile) or not isinstance(model, ModelParity)
            or model.profile_key != profile.key or 'instruction' not in profile.supported_modes):
        raise ValueError('exact instruction profile and inference configuration required')
    for field in ('provider', 'model', 'revision', 'tokenizer', 'tokenizer_revision'):
        if getattr(model, field) != getattr(profile, field):
            raise ValueError('inference metadata differs from profile')
    if not isinstance(manifest, DatasetManifest):
        raise TypeError('frozen dataset manifest required')
    selections, holdouts = tuple(selection_tasks), tuple(holdout_tasks)
    for split, tasks in (('selection', selections), ('holdout', holdouts)):
        if (any(not isinstance(t, ExperimentTask) for t in tasks)
                or len(tasks) != len(getattr(manifest, split))
                or {t.task_id for t in tasks} != set(getattr(manifest, split))):
            raise ValueError('exact frozen tasks required for each partition')
    instruction_hashes = [sha256(t.instruction.strip().encode()).hexdigest() for t in selections + holdouts]
    if len(instruction_hashes) != len(set(instruction_hashes)):
        raise ValueError('duplicate instruction content across evaluation partitions')
    required_calls = 1 + 2 * (len(selections) + len(holdouts))
    if type(max_calls) is not int or not required_calls <= max_calls <= 20000:
        raise ValueError('complete cycle must fit bounded provider call budget')
    for amount in (max_cost_usd, discovery_cost_cap_usd, per_call_cost_cap_usd):
        _number(amount)
    if (discovery_cost_cap_usd <= 0 or per_call_cost_cap_usd <= 0
            or discovery_cost_cap_usd + (required_calls - 1) * per_call_cost_cap_usd > max_cost_usd):
        raise ValueError('complete worst-case cycle must fit cost budget')
    if not all(callable(f) for f in (discovery_execute, provider, judge, experiment_clock)):
        raise ValueError('trusted host adapters required')

    if uncertainty is not None:
        if coordinator.uncertainty is not None and coordinator.uncertainty is not uncertainty:
            raise PermissionError('cycle cannot replace its existing uncertainty adapter')
        coordinator.uncertainty = uncertainty
    coordinator.uncertainty_state(trainer, task_type, require_learning=True)

    # Atomic reservation occurs before the first remote dispatch. It is never
    # recycled after absent candidates, synthetic evidence or callback failures.
    reservation = coordinator.reserve_study(trainer, manifest)
    calls, cost, candidate = 0, 0., None
    discovery_synthetic = True
    selection_digest = None

    def finish(state, reason, holdout_digest=None):
        if candidate is not None and state in ('blocked', 'rejected', 'skipped'):
            if coordinator.status(evaluator, candidate)['status'] == 'pending':
                coordinator.reject_pending(evaluator, candidate, reason=reason)
        summary = {'state': state, 'reason': reason, 'candidate': candidate,
                   'attempted_calls': calls, 'known_cost_usd': cost,
                   'selection_digest': selection_digest, 'holdout_digest': holdout_digest,
                   'activated': False}
        with coordinator.engine._db() as con:
            coordinator.engine._state(con, scope)
            coordinator.engine._event(con, scope, 'cce_cycle', summary)
        return summary

    def discover(role, payload, *, tenant, agent):
        nonlocal calls, cost, discovery_synthetic
        envelope = coordinator.uncertainty_state(trainer, task_type, require_learning=True)
        if envelope is not None:
            payload = {**payload, 'uncertainty': envelope}
        calls += 1
        receipt = discovery_execute(role, payload, tenant=tenant, agent=agent,
                                    cost_cap_usd=discovery_cost_cap_usd)
        if not isinstance(receipt, DiscoveryReceipt):
            raise ValueError('complete discovery billing receipt required')
        cost += receipt.cost_usd
        if receipt.cost_usd > discovery_cost_cap_usd or cost > max_cost_usd:
            raise ValueError('discovery cost cap violated')
        discovery_synthetic = receipt.synthetic
        coordinator.uncertainty_state(trainer, task_type, require_learning=True)
        return receipt.result

    def dispatch(request):
        nonlocal calls, cost
        coordinator.uncertainty_state(trainer, task_type, require_learning=True)
        if calls >= max_calls or cost + request.cost_cap_usd > max_cost_usd:
            raise RuntimeError('cycle dispatch budget exhausted')
        calls += 1
        receipt = provider(request)
        if isinstance(receipt, ProviderReceipt):
            cost += receipt.cost_usd
        coordinator.uncertainty_state(trainer, task_type, require_learning=True)
        return receipt

    try:
        proposals = discover_candidates(discover, manifest, tenant=scope[0], agent=scope[1], max_candidates=1)
    except Exception:
        return finish('blocked', 'discovery_failed_or_unknown_cost')
    if not proposals:
        return finish('skipped', 'no_candidate')
    if discovery_synthetic:
        return finish('skipped', 'synthetic_discovery')
    cue = Cue(uuid.uuid4().hex, 1, proposals[0], 'instruction', profile.key,
              (task_type,), 'host-discovery:' + generator_id)
    if safety_reason(cue):
        return finish('rejected', 'unsafe_candidate')
    candidate = coordinator.propose(trainer, cue, profile, task_type, manifest,
        generator_id=generator_id, model_config=model, reservation=reservation)

    def experiment(tasks, split):
        return run_experiment(candidate, cue, manifest, tasks, model, dispatch, judge,
            max_calls=max_calls - calls, max_cost_usd=max_cost_usd - cost,
            per_call_cost_cap_usd=per_call_cost_cap_usd, split=split,
            clock=experiment_clock, permission_granted=True, clinical=False, risk='low')

    try:
        selected = experiment(selections, 'selection')
        selection_digest = selected.digest
        metrics = selected.metrics
        if metrics['synthetic']:
            return finish('skipped', 'synthetic_selection')
        if (metrics['paired_accuracy_delta'] <= 0 or metrics['candidate']['safety'] < 1
                or any(metrics['candidate'][m] > metrics['baseline'][m]
                       for m in ('brier_score', 'latency_ms', 'cost_usd'))):
            return finish('rejected', 'selection_gate_failed')
        report = experiment(holdouts, 'holdout')
    except ExperimentBlocked as exc:
        return finish('blocked', exc.reason)
    except Exception:
        return finish('blocked', 'evaluation_failed')
    try:
        result = coordinator.evaluate(evaluator, candidate, report.pairs, evaluator_id=evaluator_id)
    except Exception:
        return finish('blocked', 'governed_evaluation_failed')
    return finish('awaiting_approval' if result['decision']['eligible'] else 'rejected',
                  'holdout_passed' if result['decision']['eligible'] else 'holdout_gate_failed', report.digest)
