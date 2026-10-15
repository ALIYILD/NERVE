#!/usr/bin/env python3
"""One durably claimed synthetic local-model transport probe; no retries."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_candidate_transport_smoke import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--expected-digest',required=True)
    parser.add_argument('--journal',required=True)
    args=parser.parse_args()
    report=run(args.directory,args.expected_digest,args.journal)
    print(json.dumps(report,sort_keys=True,indent=2))
    return 0 if report['status']=='complete' else 1


if __name__=='__main__':raise SystemExit(main())
