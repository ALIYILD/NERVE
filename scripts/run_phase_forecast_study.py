#!/usr/bin/env python3
"""Run or verify the fixed phase-routed prediction study."""
import argparse
from nerve_awim.memory_gateway.phase_forecast_study import run_study, validate_receipt

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('directory','claims','predecessor','source-study','source-claims','coordinator-directory','coordinator-journal'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--verify-only',action='store_true')
    args = parser.parse_args()
    paths = {'study':args.source_study,'claims':args.source_claims,
             'coordinator_directory':args.coordinator_directory,'coordinator_journal':args.coordinator_journal}
    if args.verify_only:
        print(validate_receipt(args.directory,args.claims,args.predecessor,paths))
    else:
        print(run_study(args.directory,args.claims,args.predecessor,paths)['recommendation'])
