#!/usr/bin/env python3
"""Bounded CPU follow-through. No pod/API/model calls, promotions, or main merges."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

BASE = Path('/Users/aliyildirim')
SHARED = BASE/'nerve-orchestration'
WORK = BASE/'nerve-resume-admission'
REPORT = BASE/'nerve-resume-report'
PYTHON = BASE/'.cache/uv/archive-v0/OI2t9KVJQ6hSK7ic/bin/python'
WRAP = datetime.fromisoformat('2026-10-17T06:00:00+00:00').timestamp()
STOP = datetime.fromisoformat('2026-10-17T06:45:00+00:00').timestamp()
STATUS = SHARED/'cpu-followthrough-status.json'
OWNER = 'resume-cpu-followthrough'
TESTS = ['tests/test_overnight_admission.py', 'tests/test_overnight_cycle.py']


def now():
    return datetime.now(timezone.utc).isoformat()


def hashed(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    tmp = path.with_name(path.name+'.cpu-followthrough.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
    tmp.replace(path)


def event(name, **fields):
    value = dict(time=now(), loop='CPU.followthrough', event=name, **fields)
    fd = os.open(SHARED/'ledger.jsonl', os.O_WRONLY|os.O_APPEND)
    try:
        os.write(fd, (json.dumps(value, sort_keys=True)+'\n').encode()); os.fsync(fd)
    finally:
        os.close(fd)


def command(args, cwd, timeout=60):
    if time.time() >= STOP:
        raise RuntimeError('hard_stop')
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True,
                          check=True, timeout=min(timeout, max(1, STOP-time.time())))


def active_tests():
    result = command(['ps','-axo','pid=,args='], WORK)
    found = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields)<2:
            continue
        pid, executable = fields[:2]
        args = fields[2] if len(fields)>2 else ''
        name = Path(executable).name.lower()
        if ((('python' in name or 'pytest' in name) and
             ('pytest' in args or 'pytest' in name or 'verify_galahad.py' in args))
                or (name in ('node','npm','npx') and
                    re.search(r'\b(vitest|jest|playwright|test)\b', args))):
            found.append(int(pid))
    return found


def integrity(root):
    pins = json.loads((SHARED/'integrity-baseline.json').read_text())['paths']
    mismatches = [name for name,h in pins.items()
                  if not (root/name).is_file() or hashed(root/name)!=h]
    for directory in ('registry','trust'):
        mismatches += [str(p.relative_to(root)) for p in (root/directory).rglob('*')
                       if p.is_file() and str(p.relative_to(root)) not in pins]
    if mismatches:
        raise RuntimeError('integrity:'+','.join(mismatches))
    return len(pins)


def branch_clean(root, branch):
    actual = command(['git','branch','--show-current'], root).stdout.strip()
    if actual != branch or command(['git','status','--porcelain'], root).stdout:
        raise RuntimeError('branch_changed_or_dirty:'+str(root))


def publish(root, branch, files, message):
    command(['git','add','--',*files], root)
    if command(['git','diff','--cached','--name-only'], root).stdout:
        command(['git','commit','-m',message], root)
    command(['git','push','origin',branch], root, timeout=45)


def focused_check(state):
    lock = SHARED/'test.lock'
    if lock.exists() or active_tests():
        return False
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        return False
    owner = dict(owner=OWNER,pid=os.getpid(),time=now())
    write(lock/'owner.json',owner)
    try:
        if active_tests():
            return False
        branch_clean(WORK,'overnight/resume-admission-guard')
        integrity(WORK)
        base_readiness = json.loads((WORK/'research/overnight-20261017/cycle-readiness.json').read_text())
        names = sorted(set(base_readiness['source_sha256'])|set(TESTS))
        before = {name:hashed(WORK/name) for name in names}
        event('start',kind='focused_admission_validation',model_calls=0)
        args = [str(PYTHON),'-m','pytest','-q',*TESTS]
        started = time.monotonic()
        # bounded focused suite only; never invoke a tier runner
        result = subprocess.run(args,cwd=WORK,text=True,capture_output=True,timeout=180)
        after = {name:hashed(WORK/name) for name in names}
        text = result.stdout+result.stderr
        log = 'research/overnight-20261017/admission-focused.log'
        receipt = 'research/overnight-20261017/admission-focused.json'
        (WORK/log).write_text(text)
        passed = result.returncode==0 and before==after
        verification = dict(time=now(),command=args,returncode=result.returncode,
                            wall_seconds=time.monotonic()-started,source_before=before,
                            source_after=after,source_stable=before==after,
                            protected_hashes_checked=integrity(WORK),model_calls=0,
                            full_tier_run=False,tests_passed=passed)
        write(WORK/receipt,verification)
        state.update(tests_finished=True,tests_passed=passed,test_receipt=receipt)
        files=[log,receipt]
        if passed:
            readiness='research/overnight-20261017/cycle-readiness.json'
            write(WORK/readiness,dict(tests_passed=True,source_sha256=after,
                  log=log,log_sha256=hashed(WORK/log),receipt=receipt,
                  receipt_sha256=hashed(WORK/receipt),time=now(),
                  scope='Focused admission and cycle modules only; provider calls mocked',
                  live_end_to_end_validated=False))
            files.append(readiness)
        doc='docs/galahad/admission-guard-review-20261017.md'
        with (WORK/doc).open('a') as f:
            f.write('\n## Unattended focused verification\n\n'+now()+': '+
                    ('passed' if passed else 'failed')+'. See '+receipt+
                    '. No full tier, pod, or inference calls. No main-branch merge.\n')
        files.append(doc)
        event('end',kind='focused_admission_validation',
              verdict='kept' if passed else 'candidate_requires_review',calls=0,
              receipt_sha256=hashed(WORK/receipt))
        publish(WORK,'overnight/resume-admission-guard',files,
                'Record unattended focused admission validation')
        state['worker_head']=command(['git','rev-parse','HEAD'],WORK).stdout.strip()
        return True
    finally:
        owner_file=lock/'owner.json'
        if owner_file.exists() and json.loads(owner_file.read_text())==owner:
            owner_file.unlink();lock.rmdir()


def snapshot(state, final=False):
    branch_clean(REPORT,'overnight/resume-report')
    integrity(REPORT)
    files=[]
    for name in ('spend.json','pods.json','conductor-status.json','ledger.jsonl'):
        target=REPORT/'orchestration'/name
        shutil.copy2(SHARED/name,target);files.append(str(target.relative_to(REPORT)))
    for name in ('admission-independent-review.md',):
        if (SHARED/name).exists():
            shutil.copy2(SHARED/name,REPORT/'orchestration'/name);files.append('orchestration/'+name)
    state['snapshot_at']=now()
    rel='orchestration/cpu-followthrough-status.json';write(REPORT/rel,state);files.append(rel)
    spend=json.loads((REPORT/'orchestration/spend.json').read_text())
    pods=json.loads((REPORT/'orchestration/pods.json').read_text())
    path=REPORT/'docs/galahad/13x-morning-report-20261017.md'
    text=path.read_text(); marker='\n<!-- CPU-FOLLOWTHROUGH -->\n'
    text=text.split(marker)[0]
    summary=(marker+'\n## Autonomous CPU follow-through\n\n'+now()+
       (' — scheduled morning wrap-up.\n\n' if final else ' — interim snapshot.\n\n')+
       'Admission guard branch: `overnight/resume-admission-guard`. Focused tests: '+
       ('passed' if state.get('tests_passed') else 'failed' if state.get('tests_finished') else 'pending; exclusive test slot unavailable')+
       '. No full-tier tests, inference, pod mutations, signing, activation, or main merge were performed by this worker.\n\n'+
       'Shared accounting snapshot: '+str(spend.get('model_calls'))+' calls, $'+
       str(spend.get('compute_usd'))+' estimated compute; storage excluded pending provider billing. '+
       'Pod observation timestamp: '+str(pods.get('observed_at'))+
       '. This CPU worker cannot refresh MCP status and does not claim a new live shutdown verification.\n\n'+
       '[Worker state](../../orchestration/cpu-followthrough-status.json). '+
       'Any earlier D1–D8 outcomes retain their stated evidence boundaries.\n')
    path.write_text(text+summary);files.append(str(path.relative_to(REPORT)))
    for name in ('evidence-index.json','resume-evidence-index.json'):
        path=REPORT/'orchestration'/name;index=json.loads(path.read_text())
        for name2 in files:index['sha256'][name2]=''
        for name2 in index['sha256']:index['sha256'][name2]=hashed(REPORT/name2)
        write(path,index);files.append(str(path.relative_to(REPORT)))
    publish(REPORT,'overnight/resume-report',files,
            'Publish morning CPU follow-through evidence' if final else 'Update autonomous CPU follow-through evidence')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if not args.run:
        print(json.dumps(dict(wrap_utc=WRAP,hard_stop_utc=STOP,tests=TESTS,
             inference=False,pod_calls=False,main_merge=False)));return
    if time.time()>=WRAP:
        raise RuntimeError('start_after_wrap_forbidden')
    own=SHARED/'cpu-followthrough.lock';own.mkdir(mode=0o700)
    state=dict(started_at=now(),pid=os.getpid(),owner=OWNER,tests_finished=False,
               tests_passed=False,model_calls=0,pod_calls=0,full_tier_run=False,
               wrap_utc='2026-10-17T06:00:00+00:00',hard_stop_utc='2026-10-17T06:45:00+00:00')
    write(own/'owner.json',state)
    event('start',kind='unattended_cpu_worker',calls=0)
    last_snapshot=0
    try:
        while time.time()<WRAP:
            state['heartbeat']=now()
            try:
                if not state['tests_finished']:focused_check(state)
                if time.time()-last_snapshot>=600:
                    snapshot(state);last_snapshot=time.time()
            except Exception as error:
                state['error']=type(error).__name__+':'+str(error)
                # Stop on unexpected failure, do not retry tests or mutate registrations.
                event('end',verdict='candidate_requires_review',reason=state['error'],calls=0)
                raise
            write(STATUS,state)
            time.sleep(min(30,max(0,WRAP-time.time())))
        state['finished_at']=now();state['status']='wrapped_up'
        event('end',verdict='kept' if state['tests_passed'] else 'candidate_requires_review',
              kind='unattended_cpu_worker',calls=0)
        write(STATUS,state);snapshot(state,final=True)
    except Exception as error:
        state['status']='stopped_with_error';state['error']=type(error).__name__+':'+str(error)
        write(STATUS,state)
        raise
    finally:
        (own/'owner.json').unlink();own.rmdir()


if __name__=='__main__':
    main()
