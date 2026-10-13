#!/usr/bin/env python3
"""Run the registered research handoff once; no promotion or arbitrary commands."""
import argparse
from nerve_awim.memory_gateway.research_orchestrator import run_orchestrator

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--online-database', required=True)
    parser.add_argument('--online-output', required=True)
    parser.add_argument('--online-run-id', required=True)
    args = parser.parse_args()
    result = run_orchestrator(args.directory, args.online_database, args.online_output, args.online_run_id)
    print(result['status'])
