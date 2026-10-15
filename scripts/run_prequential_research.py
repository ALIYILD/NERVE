#!/usr/bin/env python3
"""Adopt a completed rejected development experiment and resume bounded diagnosis."""
import argparse
from nerve_awim.memory_gateway.prequential_research_coordinator import run

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','journal','artifact'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=run(args.directory,args.journal,args.artifact)
    print(result['status'])
