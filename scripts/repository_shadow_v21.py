"""Run actual repository inventory tasks through persistent shadow learning.

Explicit local host runner, not a public API. Only selected UTF-8 Python files
inside --root are read. Raw source and inventories are not written to reports.
"""
import argparse
import json

from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.shadow_learning_v21 import ShadowLearning
from nerve_awim.repository_pilot_v22 import file_task


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'report', 'propose', 'evaluate'))
    parser.add_argument('--db', required=True)
    parser.add_argument('--root', default='.')
    parser.add_argument('--file', action='append', default=[])
    parser.add_argument('--candidate')
    parser.add_argument('--tenant', default='local-repository')
    parser.add_argument('--agent', default='inventory-shadow')
    args = parser.parse_args(argv)
    if len(args.file) > 128:
        parser.error('at most 128 files per invocation')
    if args.action in ('run', 'evaluate') and not args.file:
        parser.error('run/evaluate requires explicitly selected files')
    if args.action == 'evaluate' and not args.candidate:
        parser.error('evaluate requires a frozen candidate ID')
    tasks = [file_task(args.root, name) for name in args.file]
    authority = LearningAuthority()
    actors = {role: authority.issue(args.tenant, args.agent, role)
              for role in ('runtime', 'trainer', 'evaluator', 'operator', 'auditor')}
    engine = GovernedLearning(args.db, authority=authority, strategies=REPOSITORY_STRATEGIES,
        judge=repository_judge, contract_revision='repository-shadow-v21-token-judge-v1',
        baseline_routes={CONTEXT: 'ast-inventory'})
    try:
        engine.status(actors['operator'])
    except LookupError:
        if args.action != 'run':
            raise ValueError('initialise this scope with run first') from None
        engine.bootstrap(actors['operator'])
    shadow = ShadowLearning(engine, runtime=actors['runtime'], trainer=actors['trainer'])
    output = {}
    if args.action == 'run':
        counts = {'recorded': 0, 'rejected': 0, 'failed': 0, 'runtime_errors': 0}
        for task in tasks:
            try:
                shadow.execute(task)
            except Exception:
                counts['runtime_errors'] += 1
            # CLI batch runner: separate phase after each response has returned.
            drained = shadow.drain()
            for key in ('recorded', 'rejected', 'failed'):
                counts[key] += drained[key]
        output['collection'] = counts
    elif args.action == 'propose':
        candidate = engine.freeze_candidate(actors['trainer'])
        output['proposal'] = engine.candidate_report(actors['auditor'], candidate)
    elif args.action == 'evaluate':
        output['evaluation'] = engine.evaluate_candidate(actors['evaluator'], args.candidate, tasks)
    output['status'] = engine.status(actors['auditor'])
    output['shadow'] = shadow.report(actors['auditor'])
    print(json.dumps(output, indent=2, sort_keys=True))
    return output


if __name__ == '__main__':
    main()
