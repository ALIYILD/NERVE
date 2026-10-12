#!/usr/bin/env python3
"""Collect compact, allowlisted maintenance evidence without changing sources."""
import argparse
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nerve_awim import agentos_maintenance_policy as policy

MAX_BYTES = 20000


def epoch(value):
    if type(value) is int:
        return value
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return int(parsed.timestamp()) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _json(path):
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return {}, 'invalid'
        return data, 'ok'
    except (OSError, ValueError):
        return {}, 'unavailable'


def _freshness(stamp, now):
    if stamp is None or stamp > now + 60:
        return 'unknown'
    return 'fresh' if now - stamp <= 1800 else 'stale'


def collect(home, now=None):
    home = Path(home)
    now = int(time.time()) if now is None else now
    runtime, runtime_read = _json(home / '.agentic-os/runtime-utilization.json')
    cron, cron_read = _json(home / '.hermes/profiles/coordinator/cron/jobs.json')
    source_health = {'runtime': {'read': runtime_read, 'freshness': _freshness(epoch(runtime.get('ts')), now)},
                     'cron': {'read': cron_read, 'freshness': _freshness(epoch(cron.get('updated_at')), now)}}
    jobs = cron.get('jobs')
    valid_jobs = isinstance(jobs, list) and all(isinstance(j, dict) for j in jobs)
    if not valid_jobs:
        jobs = []
        source_health['cron']['read'] = 'invalid' if cron_read == 'ok' else cron_read
    normalized = []
    schedule = []
    for job in jobs:
        kind = job.get('schedule', {})
        kind = kind.get('kind', kind.get('type')) if isinstance(kind, dict) else None
        normalized.append({'id': job.get('id'), 'enabled': job.get('enabled'), 'kind': kind})
        if job.get('enabled') is not True:
            continue
        due = epoch(job.get('next_run_at'))
        state = 'unknown' if due is None else 'overdue' if now - due > 60 else 'within_tick' if due <= now else 'future'
        # IDs and names are intentionally omitted: counts/times suffice for audit.
        schedule.append({'next_run_at_epoch': due, 'freshness': state,
                         'last_run_at_epoch': epoch(job.get('last_run_at')),
                         'last_status': job.get('last_status') if job.get('last_status') in ('ok', 'error', 'running', None) else 'unknown',
                         'local_delivery': job.get('deliver') == 'local'})
    tasks, runs = [], []
    db = home / '.hermes/kanban/boards/agentos-maintenance/kanban.db'
    try:
        conn = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('BEGIN')  # All board evidence belongs to one read snapshot.
            tasks = [dict(row) for row in conn.execute('SELECT id,status,current_run_id,max_retries,consecutive_failures,max_runtime_seconds FROM tasks')]
            runs = [dict(row) for row in conn.execute('SELECT id,task_id,status,started_at,ended_at,last_heartbeat_at,max_runtime_seconds FROM task_runs')]
            links = [tuple(row) for row in conn.execute('SELECT parent_id,child_id FROM task_links')]
        finally:
            conn.close()
        source_health['maintenance_board'] = {'read': 'ok'}
        for task in tasks:
            task['run_id'] = task.pop('current_run_id')
            task['max_consecutive_failures'] = task.pop('max_retries')
            task['depends_on'] = [parent for parent, child in links if child == task['id']]
        for run in runs:
            run['finished_at'] = run.pop('ended_at')
            run['heartbeat_at'] = run.pop('last_heartbeat_at')
    except (sqlite3.Error, OSError, ValueError):
        tasks, runs = [], []
        source_health['maintenance_board'] = {'read': 'unavailable'}
    latest = policy.latest_run_by_task(runs)
    unresolved = []
    for task in tasks:
        if task['status'] in ('done', 'archived', 'cancelled'):
            continue
        record = {k: task[k] for k in ('id', 'status', 'max_consecutive_failures', 'consecutive_failures', 'depends_on')}
        record['dependency_readiness'] = policy.dependency_readiness(task, tasks)
        record['retry_chain'] = policy.retry_chain_summary(task['id'], runs)
        record['retry_disposition'] = policy.retry_disposition(task, runs, now, 60)
        run = latest.get(task['id'])
        record['latest_run'] = run
        if run and type(run.get('max_runtime_seconds')) is int and run['max_runtime_seconds'] > 0:
            record['timeout_diagnosis'] = policy.timeout_diagnosis(run, run['max_runtime_seconds'])
        unresolved.append(record)
    admission = policy.mission_admission(tasks, None) if source_health['maintenance_board']['read'] == 'ok' else 'unknown'
    services = {}
    source_services = runtime.get('services', {})
    if isinstance(source_services, dict):
        for name in ('hermes', 'dashboard'):
            item = source_services.get(name)
            ok = item.get('ok') if isinstance(item, dict) else None
            services[name] = 'ok' if ok is True and source_health['runtime']['freshness'] == 'fresh' else 'failed' if ok is False and source_health['runtime']['freshness'] == 'fresh' else 'unknown'
    boards = []
    for board in runtime.get('boards', []) if isinstance(runtime.get('boards'), list) else []:
        if not isinstance(board, dict):
            continue
        counts = board.get('counts', {})
        boards.append({'slug': board.get('slug') if isinstance(board.get('slug'), str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', board['slug']) else 'unknown', 'counts': {key: value for key, value in counts.items() if key in ('todo', 'ready', 'running', 'blocked', 'review', 'triage', 'done', 'archived', 'scheduled') and type(value) is int and value >= 0}} if isinstance(counts, dict) else {'counts': {}})
    inventory = policy.schedule_inventory(normalized)
    schedule_status = ('unknown' if not valid_jobs or source_health['cron']['freshness'] != 'fresh'
                       or inventory['invalid'] or any(j['freshness'] == 'unknown' for j in schedule)
                       else 'failed' if any(j['last_status'] == 'error' or not j['local_delivery'] for j in schedule)
                       else 'overdue' if any(j['freshness'] == 'overdue' for j in schedule)
                       else 'unknown' if any(j['last_status'] != 'ok' or j['last_run_at_epoch'] is None for j in schedule)
                       else 'ok')
    source_ok = all(v.get('read') == 'ok' and v.get('freshness', 'fresh') == 'fresh' for v in source_health.values())
    result = {'schema_version': 1, 'collected_at': datetime.fromtimestamp(now, timezone.utc).isoformat(),
              'collected_at_epoch': now, 'status': 'blocked' if admission == 'blocked' else 'ok' if source_ok and admission == 'eligible' else 'unknown',
              'source_health': source_health, 'source_service_status': 'failed' if any(v == 'failed' for v in services.values()) else 'ok' if source_ok and services and all(v == 'ok' for v in services.values()) else 'unknown',
              'schedule': {'inventory': inventory, 'enabled_count': len(schedule) if valid_jobs else None,
                           'tick_grace_seconds': 60, 'status': schedule_status, 'jobs': schedule},
              'services': services, 'boards': boards, 'runtime_snapshot_epoch': epoch(runtime.get('ts')),
              'workflow': {'mission_admission': admission, 'unresolved_tasks': unresolved,
                           'task_count': len(tasks), 'run_count': len(runs),
                           'stale_claims': policy.stale_claims(tasks, runs, now, 300)}}
    if len(json.dumps(result, separators=(',', ':')).encode()) > MAX_BYTES:
        # Preserve counts and honest incompleteness, never silently drop evidence.
        result['status'] = 'unknown'
        result['truncated'] = True
        result['schedule']['jobs'] = []
        result['workflow']['unresolved_tasks'] = []
        result['workflow']['stale_claims'] = []
        result['boards'] = []
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = collect(args.home)
    output = args.output or args.home / '.agentic-os/nerve/maintenance-evidence.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n'
    if len(encoded.encode()) > MAX_BYTES:
        raise ValueError('evidence exceeds size bound')
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(encoded)
    temporary.replace(output)
    print(json.dumps({'status': result['status'], 'output': str(output), 'bytes': len(encoded.encode())}))


if __name__ == '__main__':
    main()
