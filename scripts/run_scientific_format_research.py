#!/usr/bin/env python3
"""Adopt a completed format failure, run one bounded probe, retain or request evaluation."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_format_research_coordinator import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','journal','smoke-directory','smoke-journal','study-directory','study-journal','expected-digest'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    report=run(args.directory,args.journal,args.smoke_directory,args.smoke_journal,args.study_directory,args.study_journal,args.expected_digest)
    print(json.dumps(report,sort_keys=True,indent=2))
    return 1 if report['status']=='blocked' else 0


if __name__=='__main__':raise SystemExit(main())
