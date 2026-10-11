"""Backup, verify or restore a host database to a new path; never replace a store."""
import argparse
import json
from nerve_awim.store_recovery_v27 import copy_store, verify_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('backup', 'verify', 'restore'))
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination')
    args = parser.parse_args()
    if (args.action == 'verify') != (args.destination is None):
        parser.error('backup/restore require destination; verify accepts only source')
    try:
        report = verify_store(args.source) if args.action == 'verify' else copy_store(args.source, args.destination)
    except Exception:
        parser.exit(1, 'Store operation failed; existing destination files were not overwritten.\n')
    print(json.dumps({'action': args.action, **report}, sort_keys=True))


if __name__ == '__main__':
    main()
