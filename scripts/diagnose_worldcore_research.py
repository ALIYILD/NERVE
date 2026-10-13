#!/usr/bin/env python3
"""Consume a verified WorldCore receipt and dispatch its registered diagnostic."""
import argparse
from nerve_awim.memory_gateway.research_followup import run_followup

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--predecessor', required=True)
    args = parser.parse_args()
    result = run_followup(args.directory, args.predecessor)
    print(result['status'])
