#!/usr/bin/env python3
"""Trusted gate: register, consume once, or verify. Export aggregates only."""
import argparse
import json
from nerve_awim.memory_gateway import scientific_v3_holdout as study


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('register','run','verify'))
    parser.add_argument('--directory',required=True)
    parser.add_argument('--bank-directory')
    args=parser.parse_args()
    if args.mode=='register':
        if not args.bank_directory:parser.error('--bank-directory required for registration')
        result=study.register(args.directory,args.bank_directory)
    else:result=getattr(study,args.mode)(args.directory)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':main()
