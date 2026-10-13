#!/usr/bin/env python3
"""Resume or execute the registered finite NERVE adaptation research graph."""
import argparse
from nerve_awim.memory_gateway.research_supervisor import PATH_KEYS, run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    for key in PATH_KEYS:
        parser.add_argument('--'+key.replace('_', '-'), required=True)
    args = parser.parse_args()
    paths = {key: getattr(args, key) for key in PATH_KEYS}
    print(run(args.directory, paths)['status'])
