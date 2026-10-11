"""Build, verify or unpack a pilot bundle; output paths must be new."""
import argparse
import json
from pathlib import Path
import subprocess
from nerve_awim.pilot_bundle_v28 import build_bundle, read_bundle, unpack_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'verify', 'unpack'))
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination')
    args = parser.parse_args()
    if (args.action == 'verify') != (args.destination is None):
        parser.error('build/unpack require destination; verify accepts only source')
    if args.action == 'build':
        root = Path(args.source).resolve()
        def git(*command):
            return subprocess.check_output(['git', '-C', str(root), *command], text=True).strip()
        manifest = build_bundle(root, args.destination, revision=git('rev-parse', 'HEAD'),
                                dirty=bool(git('status', '--porcelain')))
    elif args.action == 'verify':
        manifest, _ = read_bundle(args.source)
    else:
        manifest = unpack_bundle(args.source, args.destination)
    print(json.dumps({'action': args.action, 'source_revision': manifest['source_revision'],
                      'worktree_dirty': manifest['worktree_dirty'], 'files': len(manifest['files'])}, sort_keys=True))


if __name__ == '__main__':
    main()
