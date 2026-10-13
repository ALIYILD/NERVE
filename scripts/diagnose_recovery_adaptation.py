#!/usr/bin/env python3
"""Automatically diagnose a verified rejected recovery study without rerunning it."""
import argparse
from nerve_awim.memory_gateway.adaptation_followup import run_followup

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--predecessor', required=True)
    parser.add_argument('--study-claims', required=True)
    parser.add_argument('--followup-claims', required=True)
    args = parser.parse_args()
    report = run_followup(args.directory, args.predecessor, args.study_claims, args.followup_claims)
    print(report['next_action'])
