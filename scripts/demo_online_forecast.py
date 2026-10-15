#!/usr/bin/env python3
"""Run four seed-9 online forecast integration cases with matched controls."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_gateway.online_forecast_demo import run_demo

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    with Path(args.output).open('x') as output:
        report = run_demo()
        json.dump(report,output,sort_keys=True,separators=(',',':'),allow_nan=False)
        output.write('\n')
    print(report['status'])
