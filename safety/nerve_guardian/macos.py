"""Read-only same-Mac provisioning inventory; never authorises containment."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import platform
import plistlib
import stat
import time


def _metadata(path):
    try:
        info = path.lstat()
        return {'exists': True, 'uid': info.st_uid, 'mode': stat.S_IMODE(info.st_mode),
                'regular': stat.S_ISREG(info.st_mode), 'directory': stat.S_ISDIR(info.st_mode),
                'symlink': stat.S_ISLNK(info.st_mode)}
    except OSError:
        return {'exists': False}


def _read(path):
    # Reject linked ancestors as well as a linked final file. This routine never
    # follows paths supplied by a plist, report or credential configuration.
    if any(parent.is_symlink() for parent in path.parents):
        raise OSError('linked ancestor')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 262144:
            raise OSError('bounded regular input required')
        value = source.read(262145)
    if len(value) > 262144:
        raise OSError('oversized input')
    return value


def inspect_local(*, home=None, root=Path('/'), platform_name=None, uid=None,
                  now=None, read_bytes=None, metadata=None, max_age=30):
    """Return facts and blocking gates without reading secret/config bodies.

    Every platform/filesystem/time input is injectable for isolated tests. The
    native macOS controller and its independent deployment are not implemented;
    `ready` therefore always remains false, regardless of observed file presence.
    """
    home = Path.home() if home is None else Path(home)
    root = Path(root)
    current_uid = os.getuid() if uid is None else uid
    system = platform.system() if platform_name is None else platform_name
    now = time.time() if now is None else now
    reader, info = read_bytes or _read, metadata or _metadata
    if type(max_age) not in (int, float) or not math.isfinite(max_age) or not 0 < max_age <= 3600:
        raise ValueError('bounded freshness required')

    def file_fact(path):
        record = info(path)
        return {'exists': record.get('exists') is True,
                'uid': record.get('uid') if type(record.get('uid')) is int else None,
                'mode': oct(record['mode']) if type(record.get('mode')) is int else None,
                'symlink': record.get('symlink') is True}

    def read(path):
        meta = info(path)
        if not meta.get('exists') or not meta.get('regular') or meta.get('symlink'):
            raise ValueError('untrusted file')
        value = reader(path)
        if not isinstance(value, bytes) or len(value) > 262144:
            raise ValueError('bounded bytes required')
        return value

    learning = home / 'Library/LaunchAgents/com.aliyildirim.nerve.learning.plist'
    learning_fact = dict(file_fact(learning), status='UNKNOWN', expected_command=False)
    try:
        document = plistlib.loads(read(learning))
        expected = [str(root / 'Library/Frameworks/Python.framework/Versions/3.10/bin/python3'),
                    str(home / 'nerve-review/scripts/agentos_bridge.py'), 'cycle']
        learning_fact.update(status='OBSERVED',
            expected_label=document.get('Label') == 'com.aliyildirim.nerve.learning',
            expected_command=document.get('ProgramArguments') == expected,
            interval_seconds=document.get('StartInterval') if type(document.get('StartInterval')) is int else None,
            run_at_load=document.get('RunAtLoad') is True,
            independently_owned=learning_fact['uid'] == 0 and current_uid != 0)
    except (OSError, ValueError, TypeError, AttributeError, plistlib.InvalidFileException):
        pass

    telemetry = home / '.local/share/nerve-watchtower/state/telemetry.json'
    telemetry_fact = {'status': 'UNKNOWN', 'fresh': False, 'collection_health': 'UNKNOWN'}
    try:
        report = json.loads(read(telemetry))
        stamp = report.get('timestamp')
        fresh = (type(stamp) in (float, int) and math.isfinite(stamp)
                 and type(now) in (float, int) and math.isfinite(now) and 0 <= now - stamp <= max_age)
        health = report.get('health', {})
        collection_ok = (isinstance(health, dict) and health.get('status') == 'OK'
                         and type(health.get('dropped')) is int and health['dropped'] == 0)
        observations = report.get('observations')
        sources_ok = isinstance(observations, list) and 0 < len(observations) <= 128
        if sources_ok:
            for item in observations:
                source_time = item.get('observed_at') if isinstance(item, dict) else None
                if (not isinstance(item, dict) or item.get('status') != 'OK'
                        or type(source_time) not in (float, int) or not math.isfinite(source_time)
                        or not fresh or not 0 <= now - source_time <= max_age):
                    sources_ok = False
                    break
        telemetry_fact.update(fresh=fresh, collection_health='OK' if collection_ok else 'UNKNOWN',
                              status='OBSERVED_METADATA_ONLY' if fresh and collection_ok and sources_ok else 'UNKNOWN')
    except (OSError, ValueError, TypeError, AttributeError):
        pass

    install = root / 'Library/Application Support/NERVE-Guardian'
    config = install / 'config.json'
    daemon = root / 'Library/LaunchDaemons/com.nerve.guardian.plist'
    installation = {'directory': file_fact(install), 'configuration': file_fact(config),
                    'launch_daemon': file_fact(daemon), 'protected_metadata': False}
    # Only metadata: do not open independent administration configuration or keys.
    inspected = (install, config, daemon, *install.parents, *daemon.parent.parents, daemon.parent)
    protected = all((m := info(path)).get('exists') and not m.get('symlink')
                    and m.get('uid') == 0 and type(m.get('mode')) is int and not m['mode'] & 0o022
                    for path in inspected)
    installation['protected_metadata'] = bool(protected)
    return {'schema': 'nerve-macos-preflight-v1', 'ready': False, 'status': 'NOT_READY',
            'facts': {'platform': 'Darwin' if system == 'Darwin' else 'UNSUPPORTED',
                      'current_uid': current_uid, 'learning_launch_agent': learning_fact,
                      'passive_telemetry': telemetry_fact, 'independent_installation': installation},
            'blocking_gates': [
                {'id': 'native_macos_enforcement', 'status': 'BLOCKED', 'reason': 'controller_not_implemented'},
                {'id': 'workload_identity_isolation', 'status': 'BLOCKED', 'reason': 'dedicated_restricted_account_not_verified'},
                {'id': 'independent_administration', 'status': 'BLOCKED', 'reason': 'root_owned_files_do_not_verify_admin_isolation'},
                {'id': 'owner_recovery_and_alerts', 'status': 'BLOCKED', 'reason': 'mfa_and_external_delivery_not_verified'},
                {'id': 'shutdown_and_restart_acceptance', 'status': 'BLOCKED', 'reason': 'disposable_host_acceptance_not_run'}],
            'mutations_performed': False, 'coverage': 'local_configuration_metadata_only'}
