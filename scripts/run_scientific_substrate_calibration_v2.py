#!/usr/bin/env python3
"""Register or run one 30-call supported-task calibration; stop before holdout."""
import argparse
import json
import os
from pathlib import Path
import sys
from nerve_awim.memory_gateway import scientific_substrate_calibration_v2 as study


def install_development_file_guard(bank_directory):
    """Deny exact holdout/seed Python opens, not an OS or subprocess sandbox."""
    bank=Path(bank_directory).resolve()
    blocked=frozenset((bank/'holdout.json',Path(str(bank)+'.seed')))
    def guard(event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            if Path(os.fsdecode(args[0])).resolve() in blocked:raise PermissionError('development_only_file_guard')
    sys.addaudithook(guard)
    return {'enabled':True,'boundary':'Exact Python holdout/seed opens; not an OS sandbox'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','journal','expected-digest','bank-directory','bank-manifest-sha256','predecessor-directory','predecessor-journal'):
        parser.add_argument('--'+name,required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare',action='store_true')
    mode.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    guard=install_development_file_guard(args.bank_directory)
    method=study.register if args.prepare else study.validate_receipt if args.verify else study.run
    result=method(args.directory,args.expected_digest,args.journal,bank_directory=args.bank_directory,bank_manifest_sha256=args.bank_manifest_sha256,predecessor_directory=args.predecessor_directory,predecessor_journal=args.predecessor_journal)
    print(json.dumps(dict(result,execution_file_guard=guard),sort_keys=True,indent=2))
    return 0 if args.prepare or result['status']=='complete' else 1


if __name__=='__main__':raise SystemExit(main())
