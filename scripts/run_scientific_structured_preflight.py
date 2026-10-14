#!/usr/bin/env python3
"""Four claimed JSON capability probes; never a promotion decision."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_structured_preflight import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('directory','expected-digest','journal'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args();report=run(**vars(args));print(json.dumps(report,sort_keys=True,indent=2))
    return 0 if report['status']=='complete' else 1


if __name__=='__main__':raise SystemExit(main())
