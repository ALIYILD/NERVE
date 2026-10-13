#!/usr/bin/env python3
"""Run the fixed, bounded process-restart persistence experiment once."""
import argparse
import json
from nerve_awim.memory_gateway.restart_learning_study import run_study


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,help='Exclusive study directory; never replayed')
    args=parser.parse_args()
    report=run_study(args.directory)
    print(json.dumps({k:report[k] for k in ('status','claimed_pipeline_episodes','completed_pipeline_episodes')}))
    return 0 if report['status']=='complete' else 1


if __name__=='__main__':
    raise SystemExit(main())
