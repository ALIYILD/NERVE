"""Goal-linked A→B→A sandbox adaptation proof with fixed-strategy controls."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from . import auto_adaptation as adaptation
from .goal_learning import execute as retrieve
from .goal_orchestrator import GoalOrchestrator

DOMAINS = {'clinical_os': ['title', 'abstract'], 'perfflux': ['direct', 'memoized']}
PROTOCOL = 'auto-adapt-aba-v1'


def execute(domain, task, strategy):
    if domain == 'clinical_os':
        return retrieve(domain, task, strategy)
    if strategy not in DOMAINS[domain]:
        raise ValueError('unregistered strategy')
    cache, output, calls = {}, [], 0
    for payload in task['payloads']:
        if strategy == 'memoized' and payload in cache:
            value = cache[payload]
        else:
            value = sha256(payload.encode()).hexdigest()
            calls += 1
            if strategy == 'memoized':
                cache[payload] = value
        output.append(value)
    return {'digests': output, 'calls': calls, 'cache_entries': len(cache)}


def judge(domain, task, output, expected):
    if domain == 'clinical_os':
        return output == expected
    return (output['digests'] == expected['digests'] and output['calls'] <= task['call_limit']
            and output['cache_entries'] <= task['cache_limit'])


def dataset(domain, phase, split, count):
    """Synthetic labels stay at the evaluator; controller receives outcomes only.

    Phase names are not inputs to the state machine or detector. A and B favor
    different existing strategies. Retention uses tasks both strategies solve.
    """
    result = []
    for index in range(count):
        ident = f'{domain}-{phase}-{split}-{index}'
        neutral = split == 'retained'
        second = phase == 1
        if domain == 'clinical_os':
            topic = 'topic'+ident
            correct = {'id': 'correct-'+ident,
                       'title': topic if not second or neutral else 'other',
                       'abstract': topic if second or neutral else 'other'}
            distractor = {'id': 'distractor-'+ident,
                          'title': topic if second and not neutral else 'other',
                          'abstract': topic if not second and not neutral else 'other'}
            task = {'query': topic, 'documents': [correct, distractor] if index % 2 else [distractor, correct]}
            expected = {'document': correct['id']}
        else:
            payloads = [ident+'-'+str(n) for n in range(4)]
            if second and not neutral:
                payloads *= 3
            task = {'payloads': payloads, 'call_limit': 4,
                    'cache_limit': 4 if second or neutral else 0}
            expected = {'digests': [sha256(p.encode()).hexdigest() for p in payloads]}
        result.append({'id': ident, 'task': task, 'expected': expected})
    return result


def sample(domain, state, episodes):
    state = deepcopy(state)
    hits = 0
    controls = {s: 0 for s in DOMAINS[domain]}
    for episode in episodes:
        # Choose and execute before the independent label updates the state.
        output = execute(domain, episode['task'], state['active'])
        success = judge(domain, episode['task'], output, episode['expected'])
        hits += int(success)
        for strategy in controls:
            controls[strategy] += int(judge(domain, episode['task'], execute(domain, episode['task'], strategy), episode['expected']))
        state = adaptation.observe(state, {'id': episode['id'], 'observed_at': len(state['events'])+1,
            'success': success, 'scope': state['scope'], 'strategy': state['active'], 'version': state['version']})
    return {'state': state, 'hits': hits, 'tasks': len(episodes), 'controls': controls}


def fault_probe(domain):
    state = adaptation.initial_state(domain, DOMAINS[domain])
    state = sample(domain, state, dataset(domain, 0, 'fault-baseline', 4))['state']
    state = sample(domain, state, dataset(domain, 1, 'fault-change', 4))['state']
    report = adaptation.evaluate(state, dataset(domain, 1, 'fault-evaluation', 4), dataset(domain, 1, 'retained', 4),
        execute=lambda task, strategy: execute(domain, task, strategy),
        judge=lambda task, output, expected: judge(domain, task, output, expected))
    state = adaptation.switch(state, report)
    # Actual environment reversal during the trial, not a fabricated failure flag.
    trial = sample(domain, state, dataset(domain, 0, 'fault-canary', 8))
    final = trial['state']
    return {'rollback_verified': final['rollbacks'] == 1 and final['active'] == DOMAINS[domain][0],
            'version': final['version'], 'trial_hits': trial['hits'], 'trial_tasks': trial['tasks'],
            'scope': 'isolated sandbox reversal during candidate trial'}


def build(directory, domains=('clinical_os', 'perfflux'), *, workload=None):
    workload_digest = None
    if workload is not None:
        from .adaptation_workload import validate
        workload, workload_digest = validate(workload)
        if tuple(domains) != (workload['domain'],):
            raise ValueError('workload must match the single authorized domain')
    if not domains or len(set(domains)) != len(domains) or any(d not in DOMAINS for d in domains):
        raise ValueError('unique registered domains required')
    tasks, handlers, validators, summaries = [], {}, {}, []
    def episodes(domain, phase, split, count):
        return deepcopy(workload['phases'][phase][split]) if workload else dataset(domain, phase, split, count)
    for domain in domains:
        scope = workload['scope'] if workload else domain
        tasks.append({'id': domain})
        last = None
        operational = []
        evaluations = []
        for phase in range(len(workload['phases']) if workload else 3):
            group = f'{domain}:phase-{phase}'
            tasks.append({'id': group, 'parent': domain})
            for stage in ('observe', 'detect', 'evaluate', 'switch', 'monitor'):
                key = group+':'+stage
                dependencies = [last] if last else []
                tasks.append({'id': key, 'parent': group, 'handler': key, 'depends_on': dependencies})

                def handler(context, d=domain, p=phase, s=stage, scoped=scope):
                    incoming = next(iter(context.values())) if context else {'state': adaptation.initial_state(scoped, DOMAINS[d])}
                    state = incoming['state']
                    if s in ('observe', 'monitor'):
                        return sample(d, state, episodes(d, p, s, 4 if s == 'observe' else 8))
                    if s == 'detect':
                        return {'state': state, 'detection': adaptation.detect(state)}
                    if s == 'evaluate':
                        if workload and adaptation.detect(state)['triggered'] and state.get('evaluation_calls', 0) + 16 > workload['target']['max_evaluation_calls']:
                            return {'state': state, 'evaluation': {'eligible': False, 'reason': 'evaluation_budget_exhausted'}}
                        evaluation = adaptation.evaluate(state, episodes(d, p, 'selection', 4), episodes(d, p, 'retained', 4),
                            execute=lambda task, strategy: execute(d, task, strategy),
                            judge=lambda task, output, expected: judge(d, task, output, expected))
                        if workload:
                            state = dict(state, evaluation_calls=state.get('evaluation_calls', 0)+evaluation.get('calls', 0))
                        return {'state': state, 'evaluation': evaluation}
                    return {'state': adaptation.switch(state, incoming['evaluation'])}

                handlers[key] = handler
                # Individual observation failures are data, not supervisor
                # failures. The final independent target gate evaluates recovery.
                validators[key] = lambda r, scoped=scope: (r['state']['scope'] == scoped
                    and r['state']['schema'] == 'auto-adaptation-v1' and not r['state']['production_authorized'])
                if stage in ('observe', 'monitor'):
                    operational.append(key)
                if stage == 'evaluate':
                    evaluations.append(key)
                last = key
        summary = domain+':verify-recovery'
        tasks.append({'id': summary, 'parent': domain, 'handler': summary, 'depends_on': operational + evaluations})

        def verify(context, d=domain):
            receipts = [r for r in context.values() if 'controls' in r]
            final = receipts[-1]['state']
            totals = {s: sum(r['controls'][s] for r in receipts) for s in DOMAINS[d]}
            hits = sum(r['hits'] for r in receipts)
            trials = [r for key, r in context.items() if key.endswith(':monitor')]
            fault = fault_probe(d)
            return {'domain': d, 'adaptive_hits': hits, 'tasks': sum(r['tasks'] for r in receipts),
                'fixed_controls': totals, 'switches': final['switches'], 'final_strategy': final['active'],
                'all_monitoring_targets_met': all(r['hits'] == r['tasks'] for r in trials),
                'beats_all_fixed_controls': all(hits > value for value in totals.values()),
                'rollback_probe': fault, 'policy_version': final['version'], 'production_authorized': False}

        original_verify = verify
        def verify_with_cost(context, verify=original_verify):
            result = verify(context)
            result['additional_evaluation_calls'] = sum(r['evaluation'].get('calls', 0) for r in context.values() if 'evaluation' in r)
            result['cost_limitation'] = 'Fixed controls share operational tasks; adaptive selection incurs extra calls. No equal-total-compute advantage claimed.'
            if workload:
                target = workload['target']
                monitoring = [r for key, r in context.items() if key.endswith(':monitor')]
                result['gain_over_best_fixed'] = (result['adaptive_hits'] - max(result['fixed_controls'].values())) / result['tasks']
                result['target_met'] = (result['gain_over_best_fixed'] >= target['min_gain']
                    and all(r['hits']/r['tasks'] >= target['min_monitor_accuracy'] for r in monitoring)
                    and result['switches'] >= target['min_switches']
                    and result['additional_evaluation_calls'] <= target['max_evaluation_calls']
                    and result['rollback_probe']['rollback_verified'])
                result['workload_digest'] = workload_digest
                result['declared_provenance'] = workload['provenance']
                result['provenance_independently_attested'] = False
            return result

        handlers[summary] = verify_with_cost
        validators[summary] = lambda r: (r['target_met'] if workload else
            r['beats_all_fixed_controls'] and r['all_monitoring_targets_met']
            and r['switches'] == 2 and r['rollback_probe']['rollback_verified'])
        summaries.append(summary)
    tasks.append({'id': 'verify-auto-adaptation-goal', 'handler': 'verify-auto-adaptation-goal', 'depends_on': summaries})
    handlers['verify-auto-adaptation-goal'] = lambda context: {'protocol': PROTOCOL, 'domains': context,
        'target_met': all(r['target_met'] if workload else r['beats_all_fixed_controls'] and r['all_monitoring_targets_met'] and r['rollback_probe']['rollback_verified'] for r in context.values()),
        'workload_digest': workload_digest,
        'limitation': 'Bounded offline replay; declared labels/provenance require independent review. No clinical efficacy, GPU savings, or broad generalization claim.'}
    validators['verify-auto-adaptation-goal'] = lambda r: r['target_met'] is True
    goal = GoalOrchestrator(directory, handlers=handlers, validators=validators)
    goal_id = PROTOCOL if workload is None else workload['goal_id']+':'+workload_digest
    if not goal.path.exists():
        goal.create(goal_id=goal_id,
            target=('External workload target: '+json.dumps(workload['target'], sort_keys=True)) if workload else
                'Automatically detect deterioration, evaluate and switch scoped strategies, recover after A-B-A changes, beat both fixed controls, and verify trial rollback.', tasks=tasks)
    else:
        existing = goal.inspect()
        if existing['goal_id'] != goal_id or [t['id'] for t in existing['tasks']] != [t['id'] for t in tasks]:
            raise ValueError('adaptation goal protocol or domain changed')
    return goal


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'tick', 'status', 'cancel'))
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--domain', action='append', choices=tuple(DOMAINS))
    parser.add_argument('--workload', type=Path, help='Validated offline task and target manifest')
    args = parser.parse_args(argv)
    if args.command in ('status', 'cancel') and not (args.state/'goal.json').exists():
        parser.error('existing goal state required')
    workload = None
    if args.workload:
        from .adaptation_workload import load
        workload = load(args.workload)
    domains = args.domain or ([workload['domain']] if workload else DOMAINS)
    goal = build(args.state, tuple(domains), workload=workload)
    result = getattr(goal, 'inspect' if args.command == 'status' else args.command)()
    print(json.dumps(result, indent=2, allow_nan=False))
    if result['status'] in ('blocked', 'budget_exhausted', 'cancelled'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
