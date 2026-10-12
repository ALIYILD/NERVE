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
            'test_memory_lifecycle.py', 'test_memory_holdout.py', 'test_memory_runtime.py',
            'test_memory_agent_wiring.py', 'test_memory_gateway_mcp.py', 'test_memory_policy.py',
                 'test_memory_inference.py', 'test_memory_operations.py', 'test_galahad_gpu_smoke.py', 'test_memory_learning.py', 'test_memory_learning_demo.py', 'test_memory_automation.py', 'test_memory_autoadapt_demo.py'),
    'security': ('test_memory_gateway.py', 'test_memory_service.py', 'test_galahad_provider.py',
                 'test_memory_lifecycle.py', 'test_memory_holdout.py', 'test_memory_runtime.py',
                 'test_memory_agent_wiring.py', 'test_memory_gateway_mcp.py', 'test_memory_policy.py',
                 'test_memory_inference.py', 'test_memory_operations.py', 'test_galahad_gpu_smoke.py', 'test_memory_learning.py', 'test_memory_learning_demo.py', 'test_memory_automation.py', 'test_memory_autoadapt_demo.py'),
    'faults': ('test_memory_gateway.py', 'test_galahad_provider.py', 'test_memory_lifecycle.py', 'test_memory_policy.py', 'test_memory_operations.py'),
    'api': ('test_memory_service.py', 'test_memory_runtime.py', 'test_memory_inference.py'),
    'baseline': ('test*.py',),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gate', choices=tuple(GROUPS) + ('readiness',))
    parser.add_argument('--evidence', nargs='*', default=[])
    args = parser.parse_args()
    if args.gate == 'readiness':
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        return subprocess.run([sys.executable, str(ROOT / 'scripts/memory_operations.py'),
                               'readiness', '--evidence', *args.evidence],
                              cwd=ROOT, env=env, timeout=30).returncode
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    failed = False
    for pattern in GROUPS[args.gate]:
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                 '-p', pattern, '-v'], cwd=ROOT, env=env, timeout=300)
        failed = failed or result.returncode != 0
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
