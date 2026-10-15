#!/usr/bin/env python3
"""Audit eligible candidate routing on development evidence without model calls."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_candidate_route_audit import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--screen-directory',required=True)
    parser.add_argument('--bank-directory',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.directory,args.screen_directory,args.bank_directory,args.manifest_sha256),sort_keys=True,indent=2))


if __name__=='__main__':main()
