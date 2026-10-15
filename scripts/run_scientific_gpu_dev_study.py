#!/usr/bin/env python3
"""Fixed 100-item development study; maximum 160 local-model calls, no holdout."""
import argparse
import json
import os
from pathlib import Path
import sys
from nerve_awim.memory_gateway import scientific_gpu_dev_study as study


def install_development_file_guard(bank_directory):
    """Deny these exact Python-open paths; not an OS or subprocess sandbox."""
    bank=Path(bank_directory).resolve()
    blocked=frozenset((bank/'holdout.json',Path(str(bank)+'.seed')))
    def guard(event,args):
        if event!='open' or not args:return
        path=args[0]
        if isinstance(path,(str,bytes,os.PathLike)):
            if Path(os.fsdecode(path)).resolve() in blocked:
                raise PermissionError('development_only_file_guard')
    sys.addaudithook(guard)
    return {'enabled':True,'boundary':'Python open events for supplied bank holdout and sibling seed paths only; not an OS sandbox'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','expected-digest','journal','bank-directory','bank-manifest-sha256','design-directory'):
        parser.add_argument('--'+name,required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--verify',action='store_true')
    args=vars(parser.parse_args())
    method=study.register if args.pop('prepare') else study.validate_receipt if args.get('verify') else study.run
    args.pop('verify')
    guard=install_development_file_guard(args['bank_directory'])
    report=method(args.pop('directory'),args.pop('expected_digest'),args.pop('journal'),**args)
    print(json.dumps(dict(report,execution_file_guard=guard),sort_keys=True,indent=2))
    return 0 if report.get('status','registered') in ('complete','registered') else 1


if __name__=='__main__':raise SystemExit(main())
