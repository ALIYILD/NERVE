#!/usr/bin/env python3
"""Record bounded single-use standard-learning mechanism fixtures."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_gateway.single_use_learning_demo import run_demo

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    with Path(args.output).open('x') as stream:
        report = run_demo()
        json.dump(report,stream,sort_keys=True,separators=(',',':'),allow_nan=False)
        stream.write('\n')
    print(report['status'])
