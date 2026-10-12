#!/usr/bin/env python3
"""Run a bounded, fixed synthetic research campaign; never promote its results."""
import argparse
from datetime import datetime
import json
from nerve_awim.memory_gateway.research_campaign import run_campaign


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--deadline-utc', required=True, help='UTC ISO-8601, e.g. 2026-10-14T07:00:00Z')
    parser.add_argument('--stop-file', required=True)
    parser.add_argument('--cycles', type=int, default=8)
    parser.add_argument('--seeds-per-cycle', type=int, default=4)
    parser.add_argument('--first-seed', type=int, default=10000)
    parser.add_argument('--trial-timeout', type=float, default=60)
    parser.add_argument('--cycle-interval', type=float, default=0)
    args = parser.parse_args()
    report = run_campaign(args.database, args.output, run_id=args.run_id,
        deadline=datetime.fromisoformat(args.deadline_utc.replace('Z', '+00:00')),
        stop_file=args.stop_file, cycles=args.cycles, seeds_per_cycle=args.seeds_per_cycle,
        first_seed=args.first_seed, trial_timeout=args.trial_timeout, cycle_interval=args.cycle_interval)
    print(json.dumps({key: report[key] for key in ('run_id', 'status', 'claimed_pipeline_episodes',
                                                 'completed_pipeline_episodes', 'recommendation')}))
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
