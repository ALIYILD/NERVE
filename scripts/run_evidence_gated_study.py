#!/usr/bin/env python3
"""Run the registered evidence-gated comparison from a verified memory coordinator."""
import argparse
from nerve_awim.memory_gateway.evidence_gated_study import run_study

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--claims',required=True)
    parser.add_argument('--coordinator-directory',required=True)
    parser.add_argument('--coordinator-journal',required=True)
    args=parser.parse_args()
    print(run_study(args.directory,args.claims,args.coordinator_directory,args.coordinator_journal)['recommendation'])
