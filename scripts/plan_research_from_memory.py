#!/usr/bin/env python3
"""Read-only synthetic research planning; does not dispatch experiments."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway.research_memory_planner import ResearchMemoryPlanner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('memory', 'study', 'claims', 'supervisor'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    if not Path(args.memory).is_file():
        parser.error('existing memory database required')
    scope = MemoryScope('synthetic-research', 'scientific-coordinator', 'verified-experiments')
    authority = MemoryAuthority()
    reader = authority.issue(scope.tenant_id, scope.agent_id, permissions=('read',))
    gateway = MemoryGateway(TrustedMemoryLedger(Path(args.memory), authority))
    plan = ResearchMemoryPlanner(gateway).plan(reader, scope, args.study, args.claims, args.supervisor)
    print(json.dumps(plan.to_dict(), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
