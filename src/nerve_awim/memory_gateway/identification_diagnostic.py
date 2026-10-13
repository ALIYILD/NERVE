"""Training-only identification audit; no execution, fitting, or promotion.

The caller must verify the durable study receipt before using this diagnostic.
Trace validation here establishes arithmetic, not remote execution provenance.
Ground-truth gain is used only for retrospective scoring. Fixed windows and
phase strata describe associations; they do not establish causes.
"""
from __future__ import annotations

from . import dynamics_factorial_study as study
from . import dynamics_factorial_episode as worker
from .recovery_adaptation import STEPS

WINDOW = 20
PHASES = ('active', 'supervision_required', 'awaiting_approval')


def _summarize(steps):
    count = len(steps)
    return {
        'steps': count,
        'learning_updates': sum(s['learning_updates'] for s in steps),
        'no_update_steps': sum(s['learning_updates'] == 0 for s in steps),
        'controller_steps': sum(s['action_source'] == 'controller' for s in steps),
        'external_supervisor_steps': sum(s['action_source'] == 'external_supervisor' for s in steps),
        'sensor_present_steps': sum(s['sensor'] is not None for s in steps),
        'sensor_absent_steps': sum(s['sensor'] is None for s in steps),
        'sensor_active_route_steps': sum(s['sensor'] is not None and s['sensor']['route'] == 'active' for s in steps),
        'sensor_recovery_route_steps': sum(s['sensor'] is not None and s['sensor']['route'] == 'recovery' for s in steps),
        'sensor_accepted_steps': sum(s['sensor'] is not None and s['sensor']['accepted'] for s in steps),
        'mean_absolute_gain_error': sum(abs(s['estimated_gain'] - s['true_gain']) for s in steps) / count if count else None,
        'mean_goal_error': sum(s['goal_error'] for s in steps) / count if count else None,
        'mean_prediction_error': sum(s['prediction_error'] for s in steps) / count if count else None,
    }


def diagnose(report):
    """Exhaustively summarize the registered training roster without new trials."""
    if type(report) is not dict or report.get('status') != 'complete' or type(report.get('rows')) is not list:
        raise ValueError('invalid_completed_study')
    expected = {(seed, scenario, arm) for seed in study.SPLITS['train']
                for scenario in study.SCENARIOS for arm in study.ARMS}
    rows = {}
    for row in report['rows']:
        if (type(row) is not dict or type(row.get('split')) is not str
                or row['split'] not in study.SPLITS):
            raise ValueError('invalid_study_row')
        if row['split'] != 'train':
            continue  # No validation/holdout outcomes enter diagnosis.
        try:
            seed, scenario, arm = row['episode']['seed'], row['episode']['scenario'], row['arm']
            if type(seed) is not int or type(scenario) is not str or type(arm) is not str:
                raise ValueError('invalid_training_identity')
            identity = (seed, scenario, arm)
            if identity not in expected or identity in rows:
                raise ValueError('invalid_training_roster')
            worker.validate({key: value for key, value in row.items() if key != 'split'}, seed, scenario, arm)
        except (KeyError, TypeError) as exc:
            raise ValueError('invalid_training_row') from exc
        rows[identity] = row['episode']['trace']
    if set(rows) != expected:
        raise ValueError('incomplete_training_roster')
    windows = []
    all_steps = []
    for scenario in study.SCENARIOS:
        for arm in study.ARMS:
            for start in range(0, STEPS, WINDOW):
                stop = min(start + WINDOW, STEPS)
                steps = [step for seed in study.SPLITS['train']
                         for step in rows[(seed, scenario, arm)][start:stop]]
                all_steps.extend(steps)
                windows.append({'scenario': scenario, 'arm': arm,
                                'start_step': start, 'stop_step_exclusive': stop,
                                'episodes': len(study.SPLITS['train']),
                                'summary': _summarize(steps),
                                'phases': {phase: _summarize([s for s in steps if s['phase'] == phase])
                                           for phase in PHASES}})
    return {'status': 'complete', 'protocol': 'training-identification-diagnostic-v1',
            'training_episodes': len(rows), 'window_steps': WINDOW,
            'totals': _summarize(all_steps), 'windows': windows,
            'phase_semantics': 'Recorded post-observation/recovery controller phase; sensor route can describe the previous phase',
            'staleness_semantics': 'No-update steps count zero fitted transitions; not proof that a gain is incorrect or obsolete',
            'inference': 'Descriptive training associations only; no causal attribution',
            'true_gain_use': 'Retrospective scoring only, never candidate input',
            'validation_holdout_used': False, 'new_episodes': 0,
            'promotion_authorized': False, 'deployed': False, 'goal_achieved': False,
            'next_action': 'register_observation_aware_adaptation_study'}
