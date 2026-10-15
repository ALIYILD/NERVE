#!/usr/bin/env python3
"""Run/resume eight synthetic scientific model training calls; no promotion."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_model_learning import run

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--expected-digest',required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.directory,args.expected_digest),sort_keys=True,allow_nan=False))
