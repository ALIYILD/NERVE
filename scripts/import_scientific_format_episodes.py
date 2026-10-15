#!/usr/bin/env python3
"""Import a completed four-call synthetic format receipt without model calls."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_format_episode_import import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','study-directory','study-journal','expected-digest'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--disabled',action='store_true')
    args=parser.parse_args()
    report=run(args.directory,args.study_directory,args.study_journal,args.expected_digest,disabled=args.disabled)
    print(json.dumps(report,sort_keys=True,indent=2))


if __name__=='__main__':main()
