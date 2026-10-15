#!/usr/bin/env python3
"""Execute the registered objective-alignment study from a verified diagnosis."""
import argparse
from nerve_awim.memory_gateway.dynamics_factorial_study import run_study

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('directory', 'claims', 'diagnosis', 'predecessor', 'study-claims', 'followup-claims'):
        parser.add_argument('--'+flag, required=True)
    args = parser.parse_args()
    report = run_study(args.directory, args.claims,
                       (args.diagnosis, args.predecessor, args.study_claims, args.followup_claims))
    print(report['recommendation'])
