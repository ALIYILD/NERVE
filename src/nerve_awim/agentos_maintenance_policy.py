"""Read-only diagnostics for normalized maintenance evidence.

Inputs are normalized JSON-like records; integer times are UTC epoch seconds.
No helper schedules work, changes a board, or retries an agent. Missing evidence
remains unknown. These policies adapt Oct 3/5 2026 watchdog timeouts, blocked
maintenance dependencies, absent scheduling.json and empty mission directories.
"""


def latest_run_by_task(runs):
    """Select latest (started_at, id) per task; input ordering is irrelevant."""
    result = {}
    for run in runs:
        if not run.get('task_id') or type(run.get('started_at')) is not int or not run.get('id'):
            continue
        old = result.get(run['task_id'])
        if old is None or (run['started_at'], run['id']) > (old['started_at'], old['id']):
            result[run['task_id']] = dict(run)
    return result


def schedule_inventory(jobs):
    """Count distinct enabled job IDs by supported kind, retaining invalid count."""
    counts = dict(cron=0, interval=0, once=0, invalid=0)
    seen = set()
    for job in jobs:
        ident = job.get('id')
        if type(ident) is not str or not ident or ident in seen:
            counts['invalid'] += 1
            continue
        seen.add(ident)
        if job.get('enabled') is not True:
            continue
        kind = job.get('kind')
        if kind not in ('cron', 'interval', 'once'):
            counts['invalid'] += 1
        else:
            counts[kind] += 1
    return counts


def timeout_diagnosis(run, limit, tick_grace=60):
    """Watchdog classification is not an inference about provider availability."""
    if type(limit) is not int or limit <= 0 or type(tick_grace) is not int or tick_grace < 0:
        raise ValueError('invalid watchdog policy')
    if run.get('status') != 'timed_out':
        return 'not_timeout'
    start, end = run.get('started_at'), run.get('finished_at')
    if type(start) is not int or type(end) is not int or end < start:
        return 'missing_timing'
    elapsed = end - start
    if elapsed < limit:
        return 'early_timeout'
    if elapsed <= limit + tick_grace:
        return 'watchdog_window'
    return 'late_watchdog'


def dependency_readiness(task, tasks):
    """Strict evidence gate: archived is not done, unlike scheduler release rules."""
    rows = {}
    duplicates = set()
    for row in tasks:
        ident = row.get('id')
        if ident in rows:
            duplicates.add(ident)
        rows[ident] = row
    dependencies = task.get('depends_on', [])
    if type(dependencies) is not list or any(type(x) is not str for x in dependencies):
        return 'invalid'
    if task.get('id') in dependencies or any(x in duplicates for x in dependencies):
        return 'invalid'
    if any(x not in rows for x in dependencies):
        return 'missing'
    if any(rows[x].get('status') != 'done' for x in dependencies):
        return 'waiting'
    return 'ready'


def retry_disposition(task, runs, now, cooldown):
    """Bounded advisory using authoritative consecutive failure counters."""
    maximum = task.get('max_consecutive_failures')
    failures = task.get('consecutive_failures')
    if type(maximum) is not int or maximum < 1 or type(failures) is not int or failures < 0 or type(now) is not int or type(cooldown) is not int or cooldown < 0:
        return 'invalid'
    attempts = [r for r in runs if r.get('task_id') == task.get('id')]
    if not attempts:
        return 'no_attempt'
    if any(type(r.get('started_at')) is not int or not r.get('id') for r in attempts):
        return 'unknown'
    latest = sorted(attempts, key=lambda r: (r['started_at'], r['id']))[-1]
    if latest.get('status') in ('running', 'claimed'):
        return 'active'
    if latest.get('status') == 'done':
        return 'complete'
    if latest.get('status') not in ('timed_out', 'failed', 'reclaimed'):
        return 'unknown'
    if failures >= maximum:
        return 'exhausted'
    ended = latest.get('finished_at')
    if type(ended) is not int or ended > now:
        return 'unknown'
    if now - ended < cooldown:
        return 'cooldown'
    return 'eligible'


def artifact_receipt_status(task, run, receipt):
    """A success label cannot substitute for same-attempt validated output."""
    if run is None or run.get('task_id') != task.get('id'):
        return 'unknown_run'
    if receipt is None:
        return 'missing'
    if receipt.get('run_id') != run.get('id') or receipt.get('task_id') != task.get('id'):
        return 'wrong_attempt'
    written, started = receipt.get('written_at'), run.get('started_at')
    if type(written) is not int or type(started) is not int or written < started:
        return 'stale'
    if receipt.get('path') != task.get('expected_artifact') or not task.get('expected_artifact'):
        return 'wrong_path'
    if receipt.get('validated') is not True:
        return 'unverified'
    return 'verified'


def mission_admission(tasks, existing_mission):
    """Existing active tasks block admission; empty folders do not prove a run."""
    if existing_mission is not None and existing_mission.get('task_ids'):
        return 'already_created'
    active = ('ready', 'running', 'todo', 'blocked', 'review', 'claimed', 'triage', 'scheduled')
    known = active + ('done', 'cancelled', 'failed', 'archived')
    if any(t.get('status') not in known for t in tasks):
        return 'unknown_state'
    if any(t.get('status') in active for t in tasks):
        return 'blocked'
    return 'eligible'


def stale_claims(tasks, runs, now, lease):
    """Only matching active attempts with expired heartbeat are stale claims."""
    if type(now) is not int or type(lease) is not int or lease <= 0:
        raise ValueError('invalid lease')
    stale = []
    for task in tasks:
        if task.get('status') not in ('running', 'claimed'):
            continue
        matches = [r for r in runs if r.get('id') == task.get('run_id') and r.get('task_id') == task.get('id')]
        if len(matches) != 1 or matches[0].get('status') not in ('running', 'claimed'):
            continue
        heartbeat = matches[0].get('heartbeat_at')
        if type(heartbeat) is int and 0 <= heartbeat <= now and now - heartbeat > lease:
            stale.append(task['id'])
    return sorted(set(stale))


def retry_chain_summary(task_id, runs):
    """Deduplicate identical attempt IDs; conflicts are explicitly ambiguous."""
    attempts = {}
    for run in runs:
        if run.get('task_id') != task_id:
            continue
        ident = run.get('id')
        if not ident or type(run.get('started_at')) is not int:
            return dict(state='unknown', attempts=0, timeouts=0)
        if ident in attempts and attempts[ident] != run:
            return dict(state='ambiguous', attempts=len(attempts), timeouts=0)
        attempts[ident] = run
    if not attempts:
        return dict(state='unknown', attempts=0, timeouts=0)
    ordered = sorted(attempts.values(), key=lambda r: (r['started_at'], r['id']))
    timeouts = sum(r.get('status') == 'timed_out' for r in ordered)
    last = ordered[-1].get('status')
    state = 'recovered' if last == 'done' and timeouts else 'complete' if last == 'done' else 'unresolved'
    return dict(state=state, attempts=len(ordered), timeouts=timeouts)


def mission_terminal_state(task_ids, tasks, receipts):
    """Completion requires unique member records and validated per-task receipts."""
    if not task_ids or len(set(task_ids)) != len(task_ids):
        return 'unknown'
    members = [t for t in tasks if t.get('id') in task_ids]
    if len(members) != len(task_ids) or {t.get('id') for t in members} != set(task_ids):
        return 'unknown'
    if any(t.get('status') in ('failed', 'cancelled') for t in members):
        return 'failed'
    if any(t.get('status') != 'done' for t in members):
        return 'incomplete'
    for task in members:
        matched = [r for r in receipts if r.get('task_id') == task['id'] and r.get('run_id') == task.get('run_id') and r.get('validated') is True]
        if len(matched) != 1 or not task.get('run_id'):
            return 'unverified'
    return 'verified_complete'


def successor_release(task, tasks, receipts):
    """Return sorted unmet prerequisite IDs; receipt must match completed run."""
    unmet = []
    for ident in task.get('depends_on', []):
        matches = [t for t in tasks if t.get('id') == ident]
        if len(matches) != 1 or matches[0].get('status') != 'done' or not matches[0].get('run_id'):
            unmet.append(ident)
            continue
        run_id = matches[0]['run_id']
        proofs = [r for r in receipts if r.get('task_id') == ident and r.get('run_id') == run_id and r.get('validated') is True]
        if len(proofs) != 1:
            unmet.append(ident)
    return sorted(set(unmet))
