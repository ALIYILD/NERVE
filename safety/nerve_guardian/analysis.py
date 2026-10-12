"""Bounded empirical metadata anomalies. Never authorizes containment."""
from collections import deque
import math
from statistics import median
import time


class BehaviourAnalysis:
    def __init__(self, *, window=30, max_sources=128, stale_seconds=60):
        if type(window) is not int or not 3 <= window <= 1000 or not 1 <= max_sources <= 1024 or not 0 < stale_seconds <= 86400:
            raise ValueError('bounded baseline required')
        self.window, self.max_sources, self.stale_seconds = window, max_sources, stale_seconds
        self.histories, self.last = {}, {}

    def observe(self, snapshot, *, now=None):
        now = time.time() if now is None else now
        result = {'risk': 'UNKNOWN', 'reason': 'invalid_or_missing_observation',
                  'automatic_containment': False, 'source_type': 'application_untrusted'}
        if not isinstance(snapshot, dict):
            return result
        stamp, counters = snapshot.get('observed_at'), snapshot.get('counters')
        if (snapshot.get('status') != 'OK' or type(stamp) not in (int, float)
                or not math.isfinite(stamp) or not 0 <= now - stamp <= self.stale_seconds
                or not isinstance(counters, dict) or not counters or len(counters) > 16
                or any(type(v) is not int or not 0 <= v <= 2**63-1 for v in counters.values())):
            return result
        tenant, source = snapshot.get('tenant'), snapshot.get('source')
        if any(not isinstance(v, str) or not 1 <= len(v) <= 80 for v in (tenant, source)):
            return result
        key = (tenant, source)
        if key not in self.histories and len(self.histories) >= self.max_sources:
            return {**result, 'reason': 'baseline_capacity_exhausted'}
        previous = self.last.get(key)
        if previous and stamp <= previous[0]:
            return {**result, 'reason': 'replayed_or_reordered_observation'}
        self.last[key] = (stamp, dict(counters))
        history = self.histories.setdefault(key, deque(maxlen=self.window))
        if previous is None or set(previous[1]) != set(counters):
            history.clear()
            return {**result, 'risk': 'NOTICE', 'reason': 'baseline_warming'}
        elapsed = stamp - previous[0]
        delta = sum(counters[k] - previous[1][k] for k in counters)
        if any(counters[k] < previous[1][k] for k in counters):
            history.clear()
            return {**result, 'risk': 'WARNING', 'reason': 'counter_decreased_unverified'}
        rate = delta / elapsed
        if len(history) < 3:
            risk, reason = 'NOTICE', 'baseline_warming'
        elif rate > max(10, median(history) * 5):
            risk, reason = 'WARNING', 'activity_rate_anomaly_unverified'
        else:
            risk, reason = 'NORMAL', 'within_observed_metadata_baseline'
        history.append(rate)
        # NORMAL describes these counters only; upstream visibility gaps remain.
        return {**result, 'risk': risk, 'reason': reason, 'samples': len(history),
                'coverage_status': 'UNKNOWN', 'baseline_scope': 'configured_metadata_only'}
