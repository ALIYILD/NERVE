#!/usr/bin/env python3
"""Local synthetic host coordinator; never launches experiments or deployment."""
import argparse
import json
from pathlib import Path

from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway.forecast_outcome_memory import ForecastOutcomeMemory
from nerve_awim.memory_gateway.forecast_research_coordinator import run

SCOPE = MemoryScope('synthetic-research', 'scientific-coordinator', 'verified-experiments')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('memory', 'directory', 'journal', 'study', 'claims', 'predecessor',
                 'source-study', 'source-claims', 'coordinator-directory',
                 'coordinator-journal', 'online-artifact', 'online-summary'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--review-fact', action='store_true',
                        help='Synthetic trusted-host fact review only; no deployment approval')
    args = parser.parse_args()
    evidence = dict(directory=args.study, claims=args.claims, predecessor_path=args.predecessor,
        source_paths=dict(study=args.source_study, claims=args.source_claims,
            coordinator_directory=args.coordinator_directory, coordinator_journal=args.coordinator_journal),
        online_artifact=args.online_artifact, online_summary=args.online_summary)
    authority = MemoryAuthority()
    proposer = authority.issue(SCOPE.tenant_id, SCOPE.agent_id, permissions=('read', 'propose'))
    reader = authority.issue(SCOPE.tenant_id, SCOPE.agent_id, permissions=('read',))
    gateway = MemoryGateway(TrustedMemoryLedger(Path(args.memory), authority))
    result = run(gateway, proposer, reader, SCOPE, directory=args.directory,
                 journal=args.journal, evidence=evidence)
    if args.review_fact and result['status'] == 'waiting_for_fact_review':
        reviewer = authority.issue(SCOPE.tenant_id, SCOPE.agent_id, permissions=('read', 'approve'))
        ForecastOutcomeMemory(gateway).review(reviewer, SCOPE, result['memory_id'], **evidence)
        result = run(gateway, proposer, reader, SCOPE, directory=args.directory,
                     journal=args.journal, evidence=evidence)
    print(json.dumps({key: result[key] for key in ('status', 'memory_id', 'source_id',
                                                   'new_episodes', 'promotion_authorized', 'goal_achieved')}, sort_keys=True))


if __name__ == '__main__': main()
