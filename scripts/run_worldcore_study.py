#!/usr/bin/env python3
"""Run the fixed fresh-seed CPU WorldCore study in a new output directory."""
import argparse
import json
from nerve_awim.memory_gateway.worldcore_study import run_study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, help='New, nonexistent study directory')
    args = parser.parse_args()
    report = run_study(args.directory)
    print(json.dumps({'status': report['status'], 'decision': report['result']['status'],
                      'evaluator_calls': report['evaluator_calls'],
                      'simulation_episodes': report['simulation_episodes']}))


if __name__ == '__main__':
    main()
