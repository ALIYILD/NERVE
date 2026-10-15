#!/usr/bin/env python3
"""One-shot matched study of online dynamics learning with supervised recovery."""
import argparse
from nerve_awim.memory_gateway.recovery_adaptation_study import run_study

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--claims',required=True,help='Shared durable dataset-claim SQLite ledger outside the run directory')
    args=parser.parse_args()
    report=run_study(args.directory,args.claims)
    print(report['recommendation'])
