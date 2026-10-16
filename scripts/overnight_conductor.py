#!/usr/bin/env python3
"""Fail-closed CPU policy/state controller. MCP caller performs returned pod actions.

This program never signs, launches inference, or mutates trust/registry. An action
plan is not proof of a shutdown: only a subsequent fresh MCP observation is.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

VERDICTS = {'promote_proposal','retain_incumbent','candidate_requires_review','insufficient_power','incomplete_infrastructure','kept','reverted'}
WRAP = datetime.fromisoformat('2026-10-17T06:00:00+00:00')
STOP = datetime.fromisoformat('2026-10-17T06:45:00+00:00')

def atomic(path, value):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as f:
        json.dump(value, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    temporary.replace(path)

def append(state, event):
    if 'verdict' in event and event['verdict'] not in VERDICTS:
        raise ValueError('unregistered verdict')
    event.setdefault('time', datetime.now(timezone.utc).isoformat())
    with (state/'ledger.jsonl').open('a') as f:
        f.write(json.dumps(event, sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())

def check_integrity(root, state):
    baseline = json.loads((state/'integrity-baseline.json').read_text())['paths']
    errors = []
    for name, digest in baseline.items():
        path = root/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append(name)
    for directory in ('registry','trust'):
        errors.extend(str(p.relative_to(root)) for p in (root/directory).rglob('*') if p.is_file() and str(p.relative_to(root)) not in baseline)
    return sorted(set(errors))

def inspect(root, state, now=None):
    now = now or datetime.now(timezone.utc)
    inventory = json.loads((state/'pods.json').read_text())
    observed = datetime.fromisoformat(inventory['observed_at'].replace('Z','+00:00'))
    pods = inventory['pods']
    previous = json.loads((state/'spend.json').read_text())
    # Each charged interval is persisted by the MCP coordinator at start/stop.
    intervals = previous.get('intervals', [])
    compute = sum(max(0, (datetime.fromisoformat(x['end']) if x.get('end') else now).__sub__(datetime.fromisoformat(x['start'])).total_seconds()) / 3600 * x['hourly_usd'] for x in intervals)
    active = [p for p in pods if p['status'] != 'EXITED']
    burn = sum(p['hourly_usd'] for p in active)
    calls = previous.get('model_calls', 0)
    errors = check_integrity(root,state)
    reasons = []
    if errors: reasons.append('integrity')
    if compute >= 11: reasons.append('budget_stop')
    if calls >= 12000: reasons.append('call_cap')
    if now >= WRAP: reasons.append('wrap_up')
    if now >= STOP: reasons.append('hard_stop')
    if len(active)>2: reasons.append('concurrency')
    if (now-observed).total_seconds()>660: reasons.append('stale_inventory')
    if previous.get('infrastructure_failures',0)>=3: reasons.append('infrastructure_stop')
    projected = compute + burn * max(0,(WRAP-now).total_seconds()) / 3600
    result = dict(observed_at=inventory['observed_at'],checked_at=now.isoformat(),compute_usd=compute,projected_compute_usd=projected,model_calls=calls,integrity_errors=errors,reasons=reasons,budget_warning=projected>12,actions=[{'id':p['id'],'action':'stop'} for p in active] if reasons else [],all_exited=not active,shutdown_verified=not active and (now-observed).total_seconds()<=660)
    if reasons:
        atomic(state/'inference-revoked.json',result)
    previous.update(compute_usd=compute,projected_compute_usd=projected,last_checked_at=now.isoformat())
    atomic(state/'spend.json',previous)
    atomic(state/'conductor-status.json',result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--state',type=Path,default=Path.home()/'nerve-orchestration');p.add_argument('command',choices=['check','integrity']);a=p.parse_args()
    print(json.dumps(inspect(a.root,a.state) if a.command=='check' else check_integrity(a.root,a.state),indent=2))
if __name__=='__main__': main()
