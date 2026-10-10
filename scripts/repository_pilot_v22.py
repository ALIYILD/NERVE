"""Local manifest-driven pilot; no activation or external traffic connection."""
import argparse
import json

from nerve_awim.governed_learning_v20 import GovernedLearning, LearningAuthority
from nerve_awim.repository_agents_v20 import CONTEXT, REPOSITORY_STRATEGIES, repository_judge
from nerve_awim.repository_pilot_v22 import RepositoryPilot
from nerve_awim.shadow_learning_v21 import ShadowLearning


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'collect', 'freeze', 'evaluate', 'review'))
    parser.add_argument('--db', required=True)
    parser.add_argument('--study', required=True)
    parser.add_argument('--root', default='.')
    parser.add_argument('--manifest')
    parser.add_argument('--tenant', default='local-repository')
    parser.add_argument('--agent', default='inventory-shadow')
    args = parser.parse_args(argv)
    manifest = None
    if args.action == 'plan':
        if not args.manifest:
            parser.error('plan requires --manifest')
        with open(args.manifest, 'rb') as handle:
            raw = handle.read(65537)
        if len(raw) > 65536:
            parser.error('manifest exceeds 64 KiB')
        manifest = json.loads(raw)
        if (type(manifest) is not dict or set(manifest) != {'repository', 'train', 'holdout'}
                or any(type(manifest[k]) is not list or any(type(p) is not str for p in manifest[k])
                       for k in ('train', 'holdout'))):
            parser.error('manifest must contain repository, train paths and holdout paths')
    authority = LearningAuthority()
    actors = {role: authority.issue(args.tenant, args.agent, role)
              for role in ('runtime', 'trainer', 'evaluator', 'operator', 'auditor')}
    engine = GovernedLearning(args.db, authority=authority, strategies=REPOSITORY_STRATEGIES,
        judge=repository_judge, contract_revision='repository-shadow-v21-token-judge-v1',
        baseline_routes={CONTEXT: 'ast-inventory'})
    try:
        engine.status(actors['operator'])
    except LookupError:
        if args.action != 'plan':
            raise ValueError('create a study plan first') from None
        engine.bootstrap(actors['operator'])
    pilot = RepositoryPilot(engine, args.root)
    output = {}
    if args.action == 'plan':
        pilot.plan(actors['evaluator'], study=args.study, **manifest)
    elif args.action == 'collect':
        shadow = ShadowLearning(engine, runtime=actors['runtime'], trainer=actors['trainer'])
        output['collection'] = pilot.collect(actors['trainer'], args.study, shadow)
        output['shadow'] = shadow.report(actors['auditor'])
    elif args.action == 'freeze':
        output['candidate'] = pilot.freeze(actors['trainer'], args.study)
    elif args.action == 'evaluate':
        output['evaluation'] = pilot.evaluate(actors['evaluator'], args.study)
    output['review'] = pilot.review(actors['auditor'], args.study)
    print(json.dumps(output, sort_keys=True, indent=2))
    return output


if __name__ == '__main__':
    main()
