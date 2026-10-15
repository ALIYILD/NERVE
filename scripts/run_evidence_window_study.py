#!/usr/bin/env python3
"""Run the registered evidence-window comparison from a verified supervisor."""
import argparse
from nerve_awim.memory_gateway.evidence_window_study import run_study

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--claims',required=True)
    parser.add_argument('--supervisor-directory',required=True)
    args=parser.parse_args()
    print(run_study(args.directory,args.claims,args.supervisor_directory)['recommendation'])
