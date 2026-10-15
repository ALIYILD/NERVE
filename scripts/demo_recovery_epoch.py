#!/usr/bin/env python3
"""Exercise development cases; no held-out improvement claim."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_gateway.recovery_epoch_demo import run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    with Path(args.output).open('x') as stream:
        report = run()
        json.dump(report,stream,sort_keys=True,separators=(',',':'),allow_nan=False)
        stream.write('\n')
    print('development cases complete; no promotion')
