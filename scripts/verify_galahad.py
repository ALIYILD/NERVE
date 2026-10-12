#!/usr/bin/env python3
"""Bounded local verification entrypoint; never installs or deploys anything."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'cpu': ('test_memory_gateway.py', 'test_galahad_provider.py',
            'test_memory_gateway_evaluation.py', 'test_memory_service.py',
            'test_memory_lifecycle.py', 'test_memory_holdout.py'),
    'security': ('test_memory_gateway.py', 'test_memory_service.py', 'test_galahad_provider.py',
                 'test_memory_lifecycle.py', 'test_memory_holdout.py'),
    'faults': ('test_memory_gateway.py', 'test_galahad_provider.py', 'test_memory_lifecycle.py'),
    'api': ('test_memory_service.py',),
    'baseline': ('test*.py',),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gate', choices=tuple(GROUPS) + ('readiness',))
    args = parser.parse_args()
    if args.gate == 'readiness':
        print(json.dumps({'clinical_deployment': 'blocked', 'gpu_restore': 'blocked',
            'commercial_licence': 'unverified', 'cpu_tests': 'run cpu gate for current evidence',
            'shadow_deployment': 'not_deployed', 'canary': 'not_authorised'}, indent=2))
        return 2
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    failed = False
    for pattern in GROUPS[args.gate]:
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                 '-p', pattern, '-v'], cwd=ROOT, env=env, timeout=300)
        failed = failed or result.returncode != 0
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
