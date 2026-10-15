#!/usr/bin/env python3
"""Execute one registered scientific validation graph; never promote or retry."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_research_coordinator import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('directory','journal','development-directory','development-journal',
                'validation-directory','validation-journal','expected-digest'):
        parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    print(json.dumps(run(**vars(args)),sort_keys=True,indent=2))


if __name__=='__main__':main()
