"""Isolated evidence-window episodes with sensor-derived estimator auditing."""
from functools import partial
import math
from time import perf_counter

from nerve_awim import consistent_dynamics
from nerve_awim.evidence_window_dynamics import EvidenceWindowGain, EvidenceWindowRuntime
from . import recovery_adaptation as episode
from . import dynamics_factorial_episode as controls

ARMS = ('frozen_h1', 'frozen_h3', 'adaptive_consistent_h1', 'adaptive_consistent_h3',
        'evidence_retain_h1', 'evidence_retain_h3', 'evidence_forget_h1', 'evidence_forget_h3')


def _configuration(seed, scenario, arm):
    if type(arm) is not str or arm not in ARMS:
        raise ValueError('invalid_evidence_arm')
    episode._inputs(seed, scenario, not arm.startswith('frozen'))
    return arm.startswith('evidence'), 'forget' in arm, int(arm[-1])


def _snapshot(model):
    return {'gain': model.gain, 'samples': [list(pair) for pair in model.samples],
            'processed': sorted(model.processed), 'variance': model.variance,
            'drift_count': model.drift_count, 'evidence_resets': model.evidence_resets}


def execute(seed, scenario, arm):
    """Dedicated single-threaded child only; all process-local bindings restored."""
    candidate, forget, horizon = _configuration(seed, scenario, arm)
    if not candidate:
        row = controls.execute(seed, scenario, arm)
        row['learning_evidence'] = None
        validate(row, seed, scenario, arm)
        return row
    audit = []
    class AuditedRuntime(EvidenceWindowRuntime):
        def tick(self):
            audit.append(_snapshot(self.controller.core.drift_model))
            return super().tick()
    old_runtime, old_product = episode.NerveResearchRuntime, consistent_dynamics.product
    count = 0
    def counted(*args, **kwargs):
        nonlocal count
        for sequence in old_product(*args, **kwargs):
            count += 1
            yield sequence
    start = perf_counter()
    try:
        episode.NerveResearchRuntime = partial(AuditedRuntime, evidence_window=16,
            prior_weight=4., forget_on_recovery=forget, planning_horizon=horizon,
            consistent_filter=True)
        consistent_dynamics.product = counted
        trace = episode.episode(seed, scenario, True)
    finally:
        episode.NerveResearchRuntime, consistent_dynamics.product = old_runtime, old_product
    row = {'arm': arm, 'episode': trace, 'elapsed_seconds': perf_counter()-start,
           'planning_sequences': count, 'learning_evidence': audit}
    validate(row, seed, scenario, arm)
    return row


def validate(row, seed, scenario, arm):
    candidate, forget, horizon = _configuration(seed, scenario, arm)
    if type(row) is not dict or set(row) != {'arm','episode','elapsed_seconds','planning_sequences','learning_evidence'} or row['arm'] != arm:
        raise ValueError('invalid_evidence_episode')
    if not candidate:
        base = dict(row)
        if base.pop('learning_evidence') is not None:
            raise ValueError('control_has_candidate_evidence')
        controls.validate(base, seed, scenario, arm)
        return
    episode.validate(row['episode'], seed, scenario, True)
    elapsed, count = row['elapsed_seconds'], row['planning_sequences']
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('invalid_elapsed_time')
    expected_count = 27*row['episode']['metrics']['active_steps'] if horizon == 3 else 0
    if type(count) is not int or count != expected_count:
        raise ValueError('invalid_planning_work')
    evidence = row['learning_evidence']
    if type(evidence) is not list or len(evidence) != episode.STEPS:
        raise ValueError('missing_learning_evidence')
    model = EvidenceWindowGain(initial=.27, window=16, prior_weight=4.)
    actions, readings, origin = [], {}, 0
    events = {event['step']: event for event in row['episode']['recovery_events']}
    for step in row['episode']['trace']:
        processed_before = len(model.processed)
        sensor = step['sensor']
        if sensor is not None and sensor['route'] == 'active' and sensor['accepted']:
            readings[sensor['timestamp']-origin] = sensor['velocity']
            for k in range(1, len(actions)):
                if k-1 in readings and k in readings and actions[k] != 0:
                    model.update(k, actions[k], readings[k-1], readings[k], episode.RETENTION)
        if step['step'] in events and events[step['step']]['authorised']:
            actions, readings = [], {}
            origin = sensor['timestamp']+1
            model.processed.clear()
            if forget:
                model.forget_window()
            else:
                values = [value for _, value in model.samples]
                model.samples.clear()
                model.samples.extend((index-len(values), value) for index, value in enumerate(values))
        # Reconstruct fitting solely from noisy sensor pairs and recorded actions.
        # Ground truth is checked by the original physical trace validator only.
        if (episode._digest(evidence[step['step']]) != episode._digest(_snapshot(model)) or
                step['estimated_gain'] != model.gain or
                step['learning_updates'] != max(0, len(model.processed)-processed_before)):
            raise ValueError('learning_evidence_mismatch')
        if step['action_source'] == 'controller':
            actions.append(step['action'])
