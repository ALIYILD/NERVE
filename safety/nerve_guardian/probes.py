"""Read-only infrastructure evidence; never trusts a risk score from an agent."""
from __future__ import annotations

import hashlib
from pathlib import Path
import time


class InfrastructureProbe:
    def __init__(self, controller, *, protected_files=None, heartbeats=None,
                 max_age=60, clock=time.time):
        self.controller = controller
        self.protected_files = protected_files or {}
        self.heartbeats = heartbeats or {}
        self.max_age = max_age
        self.clock = clock

    def sample(self, tenant):
        now = self.clock()
        observations = []

        def add(source, kind, status, evidence):
            observations.append({'source': source, 'kind': kind, 'observed_at': now,
                                 'status': status, 'evidence': evidence, 'independent': True})

        status = self.controller.verify(tenant)
        latch = self.controller.latch(tenant)
        for unit in status['coverage']:
            if unit['status'] == 'UNKNOWN':
                add('systemd', 'visibility_loss', 'UNKNOWN', {'unit': unit['unit']})
            elif latch and latch.get('latched') and (not unit['stopped'] or not unit['masked']):
                add('systemd', 'unauthorized_restart', 'CRITICAL',
                    {'unit': unit['unit'], 'latched': True, 'stopped': unit['stopped'], 'masked': unit['masked']})
            else:
                add('systemd', 'workload_state', 'NORMAL', unit)
        for path, expected in self.protected_files.get(tenant, {}).items():
            path = Path(path)
            try:
                # Expose the approved filename, never raw bytes or config values.
                if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
                    raise OSError('untrusted file')
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                changed = digest != expected
                add('protected_files', 'protected_file_changed' if changed else 'protected_file_intact',
                    'CRITICAL' if changed else 'NORMAL', {'file': path.name, 'sha256': digest, 'expected': expected})
            except OSError:
                add('protected_files', 'visibility_loss', 'UNKNOWN', {'file': path.name})
        heartbeat = self.heartbeats.get(tenant)
        if heartbeat is None:
            add('host_filesystem', 'visibility_loss', 'UNKNOWN', {'signal': 'observer_ingestion_heartbeat_unconfigured'})
        else:
            try:
                age = now - Path(heartbeat).stat().st_mtime
                fresh = 0 <= age <= self.max_age
                # Filesystem freshness is independent measurement, but not proof
                # of ingestion completeness. Coverage comparisons remain UNKNOWN.
                add('host_filesystem', 'observer_heartbeat', 'NORMAL' if fresh else 'UNKNOWN',
                    {'age_seconds': round(age, 3), 'completeness_verified': False})
            except OSError:
                add('host_filesystem', 'observer_heartbeat', 'UNKNOWN', {'available': False})
        add('coverage_inventory', 'visibility_loss', 'UNKNOWN',
            {'signal': 'cross_source_event_counts_and_unmanaged_process_coverage_unavailable'})
        return observations
