#!/usr/bin/env python3
"""Ingest completed format probes and register hypotheses, without inference."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_format_feedback import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('directory', 'episode-directory', 'study-directory', 'study-journal', 'expected-digest'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--disabled', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(**vars(args)), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
