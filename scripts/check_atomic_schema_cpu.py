"""Exclusive CPU regression checks; no inference or gate/manifest mutations."""
import json
import argparse
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
STATE = Path.home() / 'nerve-orchestration'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait-seconds', type=int, default=0)
    parser.add_argument('--compare-arc', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.wait_seconds <= 300:
        parser.error('wait must be between 0 and 300 seconds')
    lock = STATE / 'test.lock'
    token = uuid.uuid4().hex
    deadline = time.monotonic() + args.wait_seconds
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                print('TEST_LOCK_BUSY: no test process started')
                return 75
            time.sleep(1)
    owner = lock / 'owner.json'
    owner.write_text(json.dumps({'owner': 'atomic-schema-cpu-checks', 'token': token, 'pid': os.getpid()}))
    reports = []
    try:
        groups = [
            ('permission-rerun-exclusive', Path.home() / 'nerve-w0', [
                'test_agentos_taskbench', 'test_agentos_taskbench_v2', 'test_agentos_taskbench_v3',
                'test_galahad_gpu_smoke', 'test_memory_inference']),
            ('atomic-schema-regressions', ROOT, [
                'test_atomic_schema_initialization', 'test_governed_learning_v20',
                'test_arc_runtime', 'test_arc_schema_migration', 'test_arc_workflows',
                'test_arc_evaluation', 'test_arc_optional_adaptation', 'test_arc_provider',
                'test_arc_review', 'test_arc_cli']),
        ]
        if args.compare_arc:
            groups = [(label, root, ['test_arc_evaluation']) for label, root in (
                ('arc-baseline-1', Path.home()/'nerve-w0'), ('arc-patched-1', ROOT),
                ('arc-patched-2', ROOT), ('arc-baseline-2', Path.home()/'nerve-w0'))]
        for label, root, modules in groups:
            source_paths = ['src/nerve_awim/arc_execution.py', 'src/nerve_awim/governed_learning_v20.py']
            sources = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in source_paths}
            started = time.monotonic()
            log_path = STATE / (label + '.log')
            with log_path.open('w') as log:
                process = subprocess.Popen([sys.executable, '-m', 'unittest', *modules, '-v'],
                    cwd=root, env=dict(os.environ, PYTHONPATH=os.pathsep.join((str(root/'src'), str(root/'tests')))),
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    code = process.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    code = 124
            report = {'label': label, 'exit_code': code, 'elapsed_seconds': time.monotonic()-started,
                      'log': str(log_path), 'modules': modules, 'model_calls': 0,
                      'source_sha256': sources, 'source_stable': all(
                          hashlib.sha256((root/name).read_bytes()).hexdigest() == value for name, value in sources.items())}
            reports.append(report)
            print(json.dumps(report), flush=True)
        filename = 'atomic-schema-comparison.json' if args.compare_arc else 'atomic-schema-cpu-checks.json'
        (STATE/filename).write_text(json.dumps(reports, indent=2)+'\n')
        return int(any(r['exit_code'] or not r['source_stable'] for r in reports))
    finally:
        if owner.exists() and json.loads(owner.read_text()).get('token') == token:
            owner.unlink()
            lock.rmdir()


if __name__ == '__main__':
    raise SystemExit(main())
