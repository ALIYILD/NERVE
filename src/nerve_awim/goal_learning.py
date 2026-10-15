"""Executable sandbox examples of learned strategy selection and rollback.

Synthetic nonpatient evidence retrieval and CPU digest batching, not clinical
efficacy or GPU performance evidence. Strategies are existing allowed tools;
the learner selects from measured training executions, never generates code.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from .goal_orchestrator import GoalOrchestrator
from .improvement_loop import run_improvement_loop
from .learning_study import Episode


STRATEGIES = {'clinical_os': ('title', 'abstract'), 'perfflux': ('direct', 'memoized')}


def execute(domain, task, strategy=None):
    strategy = strategy or STRATEGIES[domain][0]
    if strategy not in STRATEGIES[domain]:
        raise ValueError('unregistered strategy')
    if domain == 'clinical_os':
        query = set(task['query'].lower().split())
        scores = [len(query & set(doc[strategy].lower().split())) for doc in task['documents']]
        return {'document': task['documents'][max(range(len(scores)), key=scores.__getitem__)]['id']}
    cache, values, calls = {}, [], 0
    for payload in task['payloads']:
        if strategy == 'memoized' and payload in cache:
            value = cache[payload]
        else:
            value = sha256(payload.encode()).hexdigest()
            calls += 1
            cache[payload] = value
        values.append(value)
    return {'digests': values, 'hash_calls': calls}


def judge(domain, task, output, expected):
    if domain == 'clinical_os':
        return output == expected
    return output['digests'] == expected['digests'] and output['hash_calls'] <= expected['max_calls']


def observe_policy(policy, *, verified):
    """Versioned sandbox rollback; feedback cannot select a new arbitrary tool."""
    if type(verified) is not bool or policy['scope'] != 'sandbox':
        raise ValueError('verified sandbox feedback required')
    result = deepcopy(policy)
    if not verified:
        result['active_strategy'] = result['previous_strategy']
        result['version'] += 1
        result['status'] = 'rolled_back'
    return result


def fixtures(domain, split, count):
    episodes = []
    for n in range(count):
        key = f'{split}-{n}'
        if domain == 'clinical_os':
            # Explicitly synthetic public research metadata; no patient inputs.
            topic = f'researchtopic{key}'
            correct = {'id': f'source-{key}', 'title': topic if split == 'retained' else 'controlled study', 'abstract': f'{topic} measured research outcome'}
            distractor = {'id': f'distractor-{key}', 'title': topic, 'abstract': 'unrelated research outcome'}
            docs = [correct, distractor] if n % 2 or split == 'retained' else [distractor, correct]
            task, expected = {'query': topic, 'documents': docs}, {'document': correct['id']}
        else:
            payloads = [f'public-{key}-{i}' for i in range(4)]
            # Retain already-working unique batches as a no-regression control.
            if split != 'retained':
                payloads = payloads * 3
            task = {'payloads': payloads}
            expected = {'digests': [sha256(p.encode()).hexdigest() for p in payloads], 'max_calls': len(set(payloads))}
        episodes.append(Episode(key, 'train' if split == 'train' else 'evaluation', task, expected))
    return episodes


def study(domain):
    train, selection, retained, final = [fixtures(domain, split, count) for split, count in
                                       (('train', 6), ('selection', 8), ('retained', 8), ('final', 12))]
    # Measure both allowed tools on training demonstrations only. No selected
    # strategy name is hard-coded into the proposal callback.
    training_hits = Counter({s: sum(judge(domain, e.task, execute(domain, e.task, s), e.expected)
                                   for e in train) for s in STRATEGIES[domain]})
    candidate = max(STRATEGIES[domain], key=training_hits.__getitem__)
    report = run_improvement_loop(train, selection, final, regression=retained,
        iterations=1, propose=lambda request: candidate,
        predict=lambda task, lesson: execute(domain, task, lesson),
        judge=lambda task, output, expected: judge(domain, task, output, expected))
    report['training_hits'] = dict(training_hits)
    report['capable_control_hits'] = sum(judge(domain, e.task, execute(domain, e.task, STRATEGIES[domain][1]), e.expected) for e in final)
    report['domain'] = domain
    return report


def build(directory, domains=('clinical_os', 'perfflux')):
    """One root goal supervises domain groups with study/adopt/monitor subloops.

    Adopted strategy is persisted in the goal receipt and used on fresh probe
    tasks after restart. It never changes a live application configuration.
    Final evidence is consumed once because study execution is checkpointed
    as running before callbacks; interrupted studies block instead of replaying.
    """
    if not domains or len(set(domains)) != len(domains) or any(d not in STRATEGIES for d in domains):
        raise ValueError('registered unique domains required')
    handlers, validators, tasks = {}, {}, []
    for domain in domains:
        study_id, adopt_id, monitor_id = [f'{domain}:{stage}' for stage in ('study', 'adopt', 'monitor')]
        tasks.append({'id': domain})
        for stage, depends in ((study_id, []), (adopt_id, [study_id]), (monitor_id, [adopt_id])):
            tasks.append({'id': stage, 'parent': domain, 'depends_on': depends, 'handler': stage})
        handlers[study_id] = lambda context, d=domain: study(d)
        validators[study_id] = lambda r: (r['status'] == 'observed_final_gain' and r['final']['losses'] == 0
                                         and r['final']['lesson_hits'] == r['final']['tasks'])

        def adopt(context, d=domain, sid=study_id):
            report = context[sid]
            return {'domain': d, 'active_strategy': report['selected_lesson'],
                    'previous_strategy': STRATEGIES[d][0], 'scope': 'sandbox',
                    'version': 1, 'status': 'active',
                    'evidence': sid, 'production_authorized': False}

        handlers[adopt_id] = adopt
        validators[adopt_id] = lambda r, d=domain: (r['active_strategy'] in STRATEGIES[d]
                                                    and r['scope'] == 'sandbox' and not r['production_authorized'])

        def monitor(context, d=domain, aid=adopt_id):
            policy = context[aid]
            fresh = fixtures(d, 'monitor', 12)
            hits = sum(judge(d, e.task, execute(d, e.task, policy['active_strategy']), e.expected) for e in fresh)
            # Fault injection verifies fallback independently of the learned gain.
            # Corrupt candidate output; independent correctness checker rejects it.
            probe = fresh[0]
            corrupt = {'document': 'missing'} if d == 'clinical_os' else {'digests': [], 'hash_calls': 0}
            rejected = not judge(d, probe.task, corrupt, probe.expected)
            after_fault = observe_policy(policy, verified=not rejected)
            fallback_output = execute(d, probe.task, after_fault['active_strategy'])
            baseline_output = execute(d, probe.task, policy['previous_strategy'])
            healthy = observe_policy(policy, verified=hits == len(fresh))
            return {'fresh_hits': hits, 'tasks': len(fresh), 'fault_rejected': rejected,
                    'rollback_verified': (after_fault['status'] == 'rolled_back'
                                          and after_fault['version'] == policy['version'] + 1
                                          and fallback_output == baseline_output),
                    'fault_policy': after_fault, 'healthy_policy': healthy,
                    'active_strategy': healthy['active_strategy'],
                    'fault_injection_scope': 'isolated copy; healthy sandbox candidate retained'}

        handlers[monitor_id] = monitor
        validators[monitor_id] = lambda r: r['fresh_hits'] == r['tasks'] and r['fault_rejected'] and r['rollback_verified']
    final_id = 'verify-goal'
    dependencies = [f'{d}:monitor' for d in domains]
    tasks.append({'id': final_id, 'handler': final_id, 'depends_on': dependencies})
    handlers[final_id] = lambda context: {'domains_verified': sorted(context),
        'all_targets_verified': all(r['fresh_hits'] == r['tasks'] and r['rollback_verified'] for r in context.values()),
        'production_authorized': False,
        'limitation': 'Synthetic fixtures and bounded strategy selection; no gain over capable control, no clinical or GPU efficacy claim.'}
    validators[final_id] = lambda r: r['all_targets_verified'] and r['domains_verified'] == sorted(dependencies)
    supervisor = GoalOrchestrator(directory, handlers=handlers, validators=validators)
    if not supervisor.path.exists():
        supervisor.create(goal_id='sandbox-self-improvement-v1',
            target='Learn a strategy from training executions; improve held-out task success without regression; persist and verify rollback in every selected domain.', tasks=tasks)
    else:
        # Do not reinterpret an existing goal using a different set of handlers.
        existing = supervisor.inspect()
        if [t['id'] for t in existing['tasks']] != [t['id'] for t in tasks]:
            raise ValueError('goal domain specification changed')
    return supervisor


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'tick', 'status', 'cancel'))
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--domain', choices=tuple(STRATEGIES), action='append')
    args = parser.parse_args(argv)
    if args.command in ('status', 'cancel') and not (args.state / 'goal.json').exists():
        parser.error('existing goal state required')
    supervisor = build(args.state, tuple(args.domain or STRATEGIES))
    result = getattr(supervisor, 'inspect' if args.command == 'status' else args.command)()
    print(json.dumps(result, indent=2, allow_nan=False))
    if result['status'] in ('blocked', 'budget_exhausted', 'cancelled'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
