#!/usr/bin/env python3
"""Diagnose stale gain from verified training evidence without new episodes."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_gateway.recovery_gain_diagnostic import run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('study','claims','coordinator-directory','coordinator-journal','output'):
        parser.add_argument('--'+name,required=True)
    args = parser.parse_args()
    with Path(args.output).open('x') as stream:
        report = run(args.study,args.claims,args.coordinator_directory,args.coordinator_journal)
        json.dump(report,stream,sort_keys=True,separators=(',',':'),allow_nan=False)
        stream.write('\n')
    print(report['training_episodes'])
