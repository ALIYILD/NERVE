#!/usr/bin/env python3
"""Build a private synthetic bank once; print no seed or task answers."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_gateway.scientific_task_bank import build, _read


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--seed-file',required=True,help='existing private regular 0600 file containing 64 hex digits')
    args=parser.parse_args()
    seed=_read(Path(args.seed_file),65).decode('ascii').strip()
    result=build(args.directory,host_seed=seed)
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
