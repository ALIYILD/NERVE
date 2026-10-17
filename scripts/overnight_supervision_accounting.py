"""Read-only accounting helpers for the overnight coordinator; no model calls."""
from pathlib import Path


def count_attempts(research_root, registered_roots=()):
    """Count persisted physical-attempt claims across every overnight study family.

    Extra study directories must be registered before dispatch. Resolve paths and
    deduplicate claims so an alias or an overlapping registration cannot double bill.
    Missing explicit roots fail closed: a typo must not silently undercount.
    """
    root = Path(research_root)
    roots = set(root.glob('overnight-20261017-*'))
    roots.add(root / 'overnight-identity-20261017')
    for name in registered_roots:
        path = Path(name)
        if not path.is_absolute() or not path.is_dir():
            raise ValueError('registered_attempt_root_missing_or_relative')
        roots.add(path)
    claims = set()
    for path in roots:
        if path.is_dir():
            claims.update(p.resolve() for p in path.glob('claim-*.json') if p.is_file())
    return len(claims)


def pod_failure_state(events):
    """Two consecutive attributed infrastructure failures retire a pod for the night.

    Starts, reviews and unrelated pods do not reset a streak. Only an explicit
    successful completion on that pod does. Retirement stays sticky after success.
    CPU failures remain available to the caller's global stop counter.
    """
    streaks, retired, seen = {}, set(), set()
    success = {'passed', 'promote_proposal', 'retain_incumbent',
               'insufficient_power', 'kept', 'reverted'}
    for event in events:
        if event.get('event') != 'end' or not event.get('pod_id'):
            continue
        identity = event.get('event_id') or (event.get('loop'), event.get('time'),
                                            event['pod_id'], event.get('verdict'))
        if identity in seen:
            continue
        seen.add(identity)
        pod = event['pod_id']
        if event.get('verdict') == 'incomplete_infrastructure' and event.get('pod_failure') is not False:
            streaks[pod] = streaks.get(pod, 0) + 1
            if streaks[pod] >= 2:
                retired.add(pod)
        elif event.get('verdict') in success:
            streaks[pod] = 0
    return {'consecutive_failures': streaks, 'retired_pods': sorted(retired)}
