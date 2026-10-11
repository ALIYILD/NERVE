"""Offline host-operator command: persist a reviewed trial binding; no activation."""
import argparse
import json
from pathlib import Path

from nerve_awim.bound_repository_host_v26 import HostDeployments
from serve_repository_host_v25 import repository_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('database', 'tenant', 'agent', 'canary', 'reason'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--expected-generation', required=True, type=int)
    parser.add_argument('--expected-version', required=True, type=int)
    args = parser.parse_args()
    if not Path(args.database).is_file():
        parser.error('existing host database required')
    engine = repository_engine(args.database)
    operator = engine.authority.issue(args.tenant, args.agent, 'operator')
    try:
        result = HostDeployments(engine).bind(operator, args.canary,
            expected_generation=args.expected_generation, expected_version=args.expected_version,
            reason=args.reason)
        print(json.dumps(result, sort_keys=True))
    finally:
        engine.authority.revoke(operator)


if __name__ == '__main__':
    main()
