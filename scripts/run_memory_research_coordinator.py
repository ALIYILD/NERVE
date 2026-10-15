#!/usr/bin/env python3
"""Run/resume the registered synthetic memory-guided rejection diagnostic."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_v18 import MemoryAuthority, TrustedMemoryLedger
from nerve_awim.memory_gateway import MemoryGateway, MemoryScope
from nerve_awim.memory_gateway.memory_research_coordinator import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('memory','directory','journal','study','claims','supervisor'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    if not Path(args.memory).is_file(): parser.error('existing memory database required')
    scope = MemoryScope('synthetic-research','scientific-coordinator','verified-experiments')
    authority = MemoryAuthority()
    reader = authority.issue(scope.tenant_id,scope.agent_id,permissions=('read',))
    gateway = MemoryGateway(TrustedMemoryLedger(Path(args.memory),authority))
    report = run(gateway,reader,scope,directory=args.directory,journal=args.journal,
                 study_directory=args.study,study_claims=args.claims,
                 supervisor_directory=args.supervisor)
    print(json.dumps({k:v for k,v in report.items() if k not in ('protocol','diagnostic')},sort_keys=True))


if __name__ == '__main__': main()
