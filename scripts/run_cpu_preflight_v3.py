#!/usr/bin/env python3
"""Explicit 60-minute CPU preflight v3; preserves the existing fast selection.

This is not verify_galahad.py's 180-second fast gate and never reports that gate
as passed. Registration is exclusive and precedes the single serial test run.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT)]
import timed_test_runner as timing
VERSION='cpu-preflight-v3'
BUDGET_SECONDS=3600
LOCK=Path('/private/tmp/nerve-overnight-suite.lock')


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def write_new(path,value):
    with Path(path).open('x') as f:
        json.dump(value,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--previous',type=Path,default=Path('/Users/aliyildirim/nerve-research-runs/cpu-preflight-v2-20261016/registration.json'))
    args=parser.parse_args();out=args.directory
    if args.worker:return worker(out)
    out.mkdir(parents=True,exist_ok=True)
    LOCK.mkdir()  # Atomic acquisition; never steal another window's lock.
    start=time.monotonic();process=None
    try:
        manifest=ROOT/'tests/suite_tiers.json'
        def discovery_timeout(*_):raise TimeoutError('discovery_deadline')
        previous_handler=signal.signal(signal.SIGALRM,discovery_timeout)
        signal.alarm(BUDGET_SECONDS)
        try:tests,_=timing.discover(ROOT/'tests')
        finally:
            signal.alarm(0);signal.signal(signal.SIGALRM,previous_handler)
        selected=timing.partition(tests,'fast',json.loads(manifest.read_text()))
        ids=[t.id() for t in selected]
        previous=json.loads(args.previous.read_text())
        if ids!=previous['selected_ids']:raise RuntimeError('previous_exact_inventory_changed')
        if not all(digest(ROOT/name)==value for name,value in previous['sources'].items()):
            raise RuntimeError('previous_registered_sources_changed')
        if any(t.__class__.__name__=='_FailedTest' for t in tests):
            raise RuntimeError('discovery_import_error')
        sources=[*sorted((ROOT/'src').rglob('*.py')),*sorted((ROOT/'tests').rglob('*.py')),
                 ROOT/'scripts/timed_test_runner.py',ROOT/'scripts/verify_galahad.py',Path(__file__),manifest]
        hashes={str(p.relative_to(ROOT)):digest(p) for p in sources}
        registration=dict(version=VERSION,base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            selection='exact timed_test_runner.partition(discover(tests), fast, unchanged suite_tiers.json)',
            selected_ids=ids,selected_count=len(ids),sources=hashes,budget_seconds=BUDGET_SECONDS,
            reason='The unchanged canonical 180-second fast gate timed out after merged module growth; this is a separately registered 3600-second preflight after a preserved 1200-second timeout, not a waiver or old-gate pass.',
            previous_registration_sha256=digest(args.previous),previous_verification='All v2 source hashes unchanged; v2 timeout remains failed; full fresh run, no splicing of verbose successes',
            retries=0,model_calls=0,execution='one serial unittest runner; existing fixture child processes allowed')
        write_new(out/'registration.json',registration)
        env=dict(os.environ,PYTHONPATH=os.pathsep.join((str(ROOT/'src'),str(ROOT))))
        command=[sys.executable,str(Path(__file__).resolve()),str(out),'--worker']
        with (out/'run.log').open('x') as log:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:code=process.wait(timeout=max(.001,BUDGET_SECONDS-(time.monotonic()-start)))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait();code=124
        unchanged=all(digest(ROOT/p)==h for p,h in hashes.items())
        report=json.loads((out/'timings.json').read_text()) if (out/'timings.json').exists() else None
        inventory_match=report is not None and report['selected_ids']==ids
        passed=code==0 and unchanged and inventory_match and report['successful'] and report['complete_coverage']
        result=dict(version=VERSION,verdict='passed' if passed else 'blocked',exit_code=code,
                    registration_sha256=digest(out/'registration.json'),wall_seconds=time.monotonic()-start,
                    suite_seconds=report['suite_seconds'] if report else None,
                    selected_count=len(ids),tests_run=report['tests_run'] if report else None,
                    failures=report['failures'] if report else None,errors=report['errors'] if report else None,
                    skipped=report['skipped'] if report else None,source_hashes_unchanged=unchanged,
                    exact_inventory_match=inventory_match,canonical_180s_fast_gate_passed=False,
                    model_calls=0,budget_seconds=BUDGET_SECONDS,
                    diagnostic_journal_sha256=digest(out/'completed-tests.jsonl') if (out/'completed-tests.jsonl').exists() else None)
        write_new(out/'result.json',result);print(json.dumps(result,sort_keys=True));return 0 if passed else 1
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
        LOCK.rmdir()


def worker(out):
    """Same runner/selection; flush each completed timing for diagnosis only."""
    registration=json.loads((out/'registration.json').read_text())
    previous=digest(out/'registration.json')
    selected_ids=set(registration['selected_ids'])
    if not all(digest(ROOT/p)==h for p,h in registration['sources'].items()):
        raise RuntimeError('registered_sources_changed_before_worker')
    with (out/'completed-tests.jsonl').open('x') as journal:
        class DiagnosticResult(timing.TimedResult):
            def stopTest(self,test):
                nonlocal previous
                super().stopTest(test)
                if self.identity(test) not in selected_ids:return  # Nested runner fixture diagnostics are not coverage.
                body=dict(previous=previous,completion=self.timings[-1])
                raw=json.dumps(body,sort_keys=True,separators=(',',':'))
                previous=sha256(raw.encode()).hexdigest()
                journal.write(json.dumps(dict(body,sha256=previous),sort_keys=True)+'\n')
                journal.flush();os.fsync(journal.fileno())
        original=timing.TimedResult
        timing.TimedResult=DiagnosticResult
        try:return timing.run('fast',out/'timings.json',ROOT/'tests/suite_tiers.json')
        finally:timing.TimedResult=original

if __name__=='__main__':raise SystemExit(main())
