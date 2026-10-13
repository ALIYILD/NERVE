#!/usr/bin/env python3
"""Verify and decompose recorded development predictions; never rerun episodes."""
import argparse
import json

from nerve_awim.memory_gateway.standard_learning_diagnostic import run


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.artifact), sort_keys=True, allow_nan=False))
