"""Read-only external Guardian health check.

Run from an independently administered host scheduler/health agent. Nothing here
installs that scheduler or alerts a remote owner. Process state and fresh health
metadata cover only the configured Guardian service; they cannot establish
universal safety or prove the Guardian's own claims independently.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time


def check(unit, health_file, max_age=30, runner=None):
    """Return OBSERVED_SCOPE_ONLY only for an active service and fresh healthy file.

    The system manager is queried separately from the application's health report.
    Neither the health file nor stdout contributes command arguments. Approved
    file and parent ownership must prevent monitored agents from forging the file.
    """
    now = time.time()
    result = {'status': 'UNKNOWN', 'observed_at': now, 'service': 'UNKNOWN',
              'health_report': 'UNKNOWN', 'coverage': 'configured_guardian_service_only'}
    if (not isinstance(unit, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*\.service', unit)
            or type(max_age) not in (int, float) or not math.isfinite(max_age) or not 0 < max_age <= 3600):
        return result
    execute = runner or subprocess.run
    try:
        response = execute(['/usr/bin/systemctl', '--no-pager', '--no-ask-password', 'show', unit,
                            '--property=LoadState,ActiveState,SubState,MainPID,ControlGroup'],
                           capture_output=True, text=True, timeout=5, check=False,
                           env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        if response.returncode != 0 or not isinstance(response.stdout, str) or len(response.stdout) > 16384:
            return result
        properties = dict(line.split('=', 1) for line in response.stdout.splitlines() if '=' in line)
        group = properties.get('ControlGroup', '')
        running = (properties.get('LoadState') == 'loaded' and properties.get('ActiveState') == 'active'
                   and properties.get('SubState') == 'running' and properties.get('MainPID', '').isdigit()
                   and int(properties['MainPID']) > 0 and group.startswith('/') and group != '/'
                   and '..' not in Path(group).parts)
        if not running:
            return result
        result['service'] = 'ACTIVE_WITH_CGROUP'
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, AttributeError):
        return result
    try:
        fd = os.open(health_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022 or info.st_size > 65536:
                return result
            payload = source.read(65537)
        if len(payload) > 65536:
            return result
        report = json.loads(payload)
        stamp = report.get('timestamp')
        if (type(stamp) not in (float, int) or not math.isfinite(stamp)
                or not 0 <= now - stamp <= max_age or not 0 <= now - info.st_mtime <= max_age
                or report.get('status') != 'OBSERVED_SCOPE_ONLY'
                or not isinstance(report.get('tenants'), (dict, list)) or not report['tenants']):
            return result
        # Never echo tenant details, health text, private paths or provider errors.
        result.update(status='OBSERVED_SCOPE_ONLY', health_report='FRESH_SCOPE_ONLY',
                      age_seconds=round(now - stamp, 3))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--health-file', required=True, type=Path)
    parser.add_argument('--max-age', type=float, default=30)
    args = parser.parse_args()
    result = check(args.unit, args.health_file, args.max_age)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'OBSERVED_SCOPE_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
