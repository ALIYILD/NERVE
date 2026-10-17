"""Wire the staged gate to trusted evaluators, replay cache, archive and reporting.

Host callers provide an evaluator callback, never candidate code. This API is
for dev/synthetic experiments only. CLI production/holdout dispatch is absent.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import statistics

from .contracts import register, digest, route
from .gate import Gate
from .evaluator import diagnose, score, verify_domain
from .evidence import ResponseCache, Archive, RepairPlanner, review_readiness, probe_status
from .workflow import wilson


def ordered_tasks(tasks, seed):
    groups = defaultdict(list)
    for task in tasks: groups[task['stratum']].append(task)
    rng = random.Random(seed)
    for group in groups.values():
        group.sort(key=lambda t: t['task_id']); rng.shuffle(group)
    order = []
    while any(groups.values()):
        strata = sorted(s for s, group in groups.items() if group); rng.shuffle(strata)
        for s in strata: order.append(groups[s].pop())
    return order


def evaluate(registration, tasks, directory, *, key, evaluator, evidence=None):
    """Resume cached results; refuse ambiguous in-flight calls rather than repeat."""
    register(registration)
    if registration['bank']['split'] not in ('dev', 'synthetic'):
        raise PermissionError('live_holdout_adapter_disabled')
    if any(t['split'] != registration['bank']['split'] for t in tasks):
        raise ValueError('registered_split_mismatch')
    if len({t['task_id'] for t in tasks}) != len(tasks): raise ValueError('unique_tasks_required')
    if digest(tasks) != registration['bank']['manifest']: raise ValueError('bank_manifest_mismatch')
    if set(t['stratum'] for t in tasks) != set(registration['gate']['strata']): raise ValueError('strata_mismatch')
    root = Path(directory)
    gate = Gate(root/'gate', key=key)
    cache = ResponseCache(root/'responses', split=registration['bank']['split'])
    archive = Archive(root/'archive.sqlite')
    planner = RepairPlanner(root/'repairs.sqlite')
    try:
        gate.start(registration)
        histogram, violations, by_stratum = Counter(), Counter(), defaultdict(list)
        latencies, usage = [], Counter()
        for task in ordered_tasks(tasks, registration['gate']['order_seed']):
            request = dict(model_digest=registration['model']['checkpoint_digest'],
                prompt={'task': {k:v for k,v in task.items() if k not in ('expected', 'expected_behavior')},
                        'prompts': registration['prompts'], 'schemas': registration['schemas']},
                params=registration['sampling'], replicate=registration['study_id']+':'+task['task_id'])
            request_key = digest(request)
            cached = (cache.root/(request_key+'.json')).exists()
            current = gate.report(registration['study_id'])
            # Replay previously completed rows even after a terminal verdict.
            if current['verdict'] != 'running' and not cached: break
            claim = gate.claim(registration['study_id'], task['task_id'], task['stratum'])
            if cached:
                result = cache.get(request_key)['response']
            elif claim == 'dispatch_once':
                try: result = evaluator(request)
                except (TimeoutError, OSError): break
                # Persist the response before scores. Restart recovers it without inference.
                cache.put(request, result)
            else:
                break
            required = {'candidate', 'incumbent', 'always_abstain', 'random', 'capacity', 'latency', 'usage', 'abstention_rule'}
            if set(result) != required: raise ValueError('trusted_evaluator_result_required')
            from .contracts import number
            number(result['latency'])
            candidate = result['candidate']
            labels = diagnose(task, candidate)
            vetoes = verify_domain(task, candidate, abstention_rule=result['abstention_rule'])
            correct = score(task, candidate)
            controls = {name: score(task, result[name]) for name in ('always_abstain', 'random')}
            gate.record(registration['study_id'], task['task_id'], candidate=correct,
                incumbent=score(task, result['incumbent']), controls=controls,
                violations=vetoes, measured_capacity=result['capacity'])
            histogram.update(labels); violations.update(vetoes); by_stratum[task['stratum']].append(correct)
            latencies.append(result['latency']); usage.update(result['usage'])
        verdict = gate.report(registration['study_id'])
        archived = archive.retain(registration['candidate'], bank=registration['bank']['manifest'],
            model=registration['model']['checkpoint_digest'], incumbent=registration['incumbent'],
            study=registration['study_id'], verdict=('incomplete_infrastructure' if verdict['pending_claims'] else
            'retained' if verdict['verdict'] == 'eligible_for_human_review' else
            'insufficient_power' if verdict['verdict'] == 'insufficient_power' else 'rejected'))
        readiness = dict(evidence or {})
        readiness['sequential_gate'] = verdict['verdict'] == 'eligible_for_human_review'
        return dict(gate=verdict, archive_record=archived, diagnosis=dict(histogram),
            repair=({'status': 'evaluation_incomplete'} if verdict['pending_claims'] or verdict['verdict'] == 'running' else
                    planner.propose(registration['study_id'], dict(histogram))), cache_manifest=cache.manifest(),
            evidence_readiness=review_readiness(registration['tier'], readiness),
            white_box=probe_status(), five_axes=dict(
                accuracy={s: {'correct': sum(v), 'n': len(v), 'wilson95': wilson(sum(v),len(v))} for s,v in by_stratum.items()},
                efficiency={'usage': dict(usage), 'median_latency': statistics.median(latencies) if latencies else None,
                            'max_latency': max(latencies, default=None), 'capacity': registration['capacity']},
                robustness={'order_seed': registration['gate']['order_seed'], 'cross_order_variance': 'requires completed robustness studies'},
                safety={'violations': dict(violations)}, ux='deferred to clinician evaluation'),
            promotion_authorized=False, holdout_accessed=False)
    finally:
        gate.close(); archive.db.close(); planner.db.close()


def robustness_verdict(studies, required_seeds):
    """All registered order runs must be present, including null/negative runs."""
    if {r['seed'] for r in studies} != set(required_seeds) or len(studies) != len(required_seeds):
        return {'status': 'incomplete', 'promotion_authorized': False}
    from .contracts import number
    gains = [number(r['gain'], -1, 1) for r in studies]
    return {'status': 'order_dependent' if min(gains) <= 0 < max(gains) else
            'no_gain' if max(gains) <= 0 else 'consistent_gain',
            'variance': statistics.pvariance(gains), 'worst_gain': min(gains), 'promotion_authorized': False}
