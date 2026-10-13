"""Registered factorial episode runner for isolated, single-threaded children.

The scoped runtime and planner instrumentation replace process-local module
globals. They are restored on every exit, but this runner is deliberately not
thread-safe: callers must run episodes serially in a dedicated child process.
Timing is observed wall-clock duration, not a hardware-independent cost claim.
"""
from __future__ import annotations

from functools import partial
import math
from time import perf_counter

from nerve_awim import consistent_dynamics
from . import recovery_adaptation


ARMS = (
    'frozen_h1', 'frozen_h3',
    'adaptive_legacy_h1', 'adaptive_legacy_h3',
    'adaptive_consistent_h1', 'adaptive_consistent_h3',
)


def _configuration(seed, scenario, arm):
    if type(arm) is not str or arm not in ARMS:
        raise ValueError('invalid factorial arm')
    adaptive = arm.startswith('adaptive_')
    recovery_adaptation._inputs(seed, scenario, adaptive)
    return adaptive, arm.startswith('adaptive_consistent_'), int(arm[-1])


def execute(seed: int, scenario: str, arm: str) -> dict:
    adaptive, consistent, horizon = _configuration(seed, scenario, arm)
    old_runtime = recovery_adaptation.NerveResearchRuntime
    old_product = consistent_dynamics.product
    planning_sequences = 0

    def counted_product(*args, **kwargs):
        nonlocal planning_sequences
        for sequence in old_product(*args, **kwargs):
            planning_sequences += 1
            yield sequence

    start = perf_counter()
    try:
        recovery_adaptation.NerveResearchRuntime = partial(
            consistent_dynamics.ConsistentDynamicsRuntime,
            consistent_filter=consistent, planning_horizon=horizon)
        consistent_dynamics.product = counted_product
        episode = recovery_adaptation.episode(seed, scenario, adaptive)
    finally:
        recovery_adaptation.NerveResearchRuntime = old_runtime
        consistent_dynamics.product = old_product
    row = dict(arm=arm, episode=episode,
               elapsed_seconds=perf_counter() - start,
               planning_sequences=planning_sequences)
    validate(row, seed, scenario, arm)
    return row


def validate(row, seed, scenario, arm):
    """Check complete trace and accounting, without replaying a plant episode.

    Each returned h3 episode has exactly one completed enumeration per active
    action. A controller planning failure aborts the underlying episode; it
    cannot be represented as a successful row with partial accounting.
    """
    adaptive, _, horizon = _configuration(seed, scenario, arm)
    if type(row) is not dict or set(row) != {
            'arm', 'episode', 'elapsed_seconds', 'planning_sequences'}:
        raise ValueError('invalid factorial episode evidence')
    if type(row['arm']) is not str or row['arm'] != arm:
        raise ValueError('factorial arm mismatch')
    recovery_adaptation.validate(row['episode'], seed, scenario, adaptive)
    elapsed = row['elapsed_seconds']
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('invalid factorial elapsed time')
    sequences = row['planning_sequences']
    expected = (27 * row['episode']['metrics']['active_steps'] if horizon == 3 else 0)
    if (type(sequences) is not int or not 0 <= sequences <= 27 * recovery_adaptation.STEPS
            or sequences != expected):
        raise ValueError('invalid factorial planning sequence count')
