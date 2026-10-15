#!/usr/bin/env python3
"""Staged external-methods CLI. No live holdout or promotion command."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['simulate', 'audit-v3', 'status'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    a = parser.parse_args()
    if a.mode == 'status':
        print(json.dumps({'status': 'staged', 'holdout_enabled': False, 'promotion_enabled': False,
            'requires': ['slice2 verdict', 'human-reviewed signed gate version', 'GPU and reviewed toolkit for Loop 47']}))
        return
    if not a.output: parser.error('--output required')
    if a.mode == 'audit-v3' and not (a.receipt and a.development): parser.error('--receipt and --development required')
    for path in (a.receipt, a.development):
        if path and ('holdout' in str(path.resolve()).lower() or path.suffix == '.seed'):
            raise PermissionError('sealed_input_disabled')
    from nerve_awim.external_methods.protection import verify_manifest
    verify_manifest(ROOT)
    if not a.worker:
        cmd = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], '--worker']
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        print(result.stdout, end='')
        return
    output = a.output.resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    if output.is_relative_to(ROOT) or ROOT.is_relative_to(output):
        raise PermissionError('evidence_directory_must_be_outside_repository')
    if any(p.resolve().is_relative_to(output) for p in (a.receipt, a.development) if p):
        raise PermissionError('evidence_output_must_not_contain_inputs')
    # Trusted code only; candidate patches are never executed in this process.
    # Audit hooks are defense in depth, not a same-user OS security boundary.
    def guard(event, args):
        if event in ('socket.connect', 'socket.__new__', 'subprocess.Popen', 'os.system'):
            raise PermissionError('evaluator_network_and_dispatch_disabled')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(args[0])).resolve()
            flags = args[2] if len(args) > 2 else 0
            writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            if writing and not p.is_relative_to(output): raise PermissionError('evaluator_protected_path_write')
            if 'holdout' in str(p).lower() or p.suffix == '.seed':
                raise PermissionError('sealed_input_disabled')
    sys.addaudithook(guard)
    from nerve_awim.external_methods.workflow import simulate, audit_v3
    result = simulate(output) if a.mode == 'simulate' else audit_v3(a.receipt, a.development, output)
    raw = json.dumps(result, sort_keys=True, indent=2) + '\n'
    (output/'report.json').write_text(raw)
    print(raw, end='')


if __name__ == '__main__': main()
