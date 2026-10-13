#!/usr/bin/env python3
"""Run fixed matched prequential gain development cases with wrong nominal priors."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_gateway.prequential_gain_demo import run_demo

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    with Path(args.output).open('x') as stream:
        result=run_demo()
        json.dump(result,stream,sort_keys=True,separators=(',',':'),allow_nan=False)
        stream.write('\n')
    print(result['recommendation'])
