#!/usr/bin/env python3
"""Replay authenticated observation over validated training traces only."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_gateway.observer_reanalysis import run

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('study','claims','coordinator-directory','coordinator-journal','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    # Reserve before computation so accidental overwrite cannot erase evidence.
    with Path(args.output).open('x') as output:
        result=run(args.study,args.claims,args.coordinator_directory,args.coordinator_journal)
        json.dump(result,output,sort_keys=True,separators=(',',':'),allow_nan=False)
        output.write('\n')
    print(result['training_episodes'])
