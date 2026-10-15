#!/usr/bin/env python3
"""Import completed synthetic validation evidence; never initiate inference."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_episode_import import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--validation-directory', required=True)
    parser.add_argument('--validation-journal', required=True)
    parser.add_argument('--expected-digest', required=True)
    parser.add_argument('--disabled', action='store_true')
    args = parser.parse_args()
    result = run(args.directory, args.validation_directory, args.validation_journal,
                 args.expected_digest, disabled=args.disabled)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__': raise SystemExit(main())
