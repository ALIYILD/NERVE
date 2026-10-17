#!/usr/bin/env python3
"""Audit a host journal and agent-authored structured report without model calls."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from nerve_awim.memory_gateway.faithfulness_monitor import record

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--experiment',required=True)
    parser.add_argument('--kind',choices=['socratic','agent-node'],required=True)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'docs/galahad/evidence/faithfulness')
    args=parser.parse_args()
    def read(path):
        try:return json.loads(path.read_text())
        except (OSError,ValueError):return None
    result=record(args.output,args.experiment,read(args.journal),read(args.report),kind=args.kind)
    print(json.dumps({'report_trace_consistency':result},sort_keys=True))
    sys.exit(0 if result['consistent'] else 2)
