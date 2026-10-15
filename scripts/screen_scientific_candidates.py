#!/usr/bin/env python3
"""Screen registered candidates; initializing empty negative history is explicit."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_candidate_screening import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--registration-directory',required=True)
    parser.add_argument('--history-directory',required=True)
    parser.add_argument('--initialize-history',action='store_true')
    args=parser.parse_args()
    print(json.dumps(run(args.directory,args.registration_directory,args.history_directory,
                         initialize_history=args.initialize_history),sort_keys=True,indent=2))


if __name__=='__main__': main()
