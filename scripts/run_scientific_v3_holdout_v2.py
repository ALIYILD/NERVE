#!/usr/bin/env python3
"""Trusted gate; aggregate-only stdout, never automatic promotion."""
import argparse,json
from nerve_awim.memory_gateway import scientific_v3_holdout_v2 as study


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('reclassify','observe','register','run','verify'))
    parser.add_argument('--directory')
    parser.add_argument('--kind',choices=('dry','slice2'))
    parser.add_argument('--partition-directory')
    parser.add_argument('--calibration-directory')
    parser.add_argument('--dry-directory')
    a=parser.parse_args()
    if a.mode=='observe':result=study.observe()
    elif a.mode=='register':
        result=study.register(a.directory,kind=a.kind,partition_directory=a.partition_directory,calibration_directory=a.calibration_directory,dry_directory=a.dry_directory)
    else:result=getattr(study,a.mode)(a.directory)
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__':main()
