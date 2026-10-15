"""Bounded, training-only description of the evidence-window experiment.

The caller must independently validate the durable study receipt first. This
module validates the training traces again, but does not authenticate a receipt,
execute trials, change gates, tune parameters, or authorize another experiment.
"""
from . import evidence_window_episode as worker
from . import evidence_window_study as study
from .identification_diagnostic import PHASES, WINDOW, _summarize
from .recovery_adaptation import STEPS


def diagnose(report):
    """Describe fixed windows and paired differences; positive deltas are worse."""
    if (type(report) is not dict or report.get('status') != 'complete'
            or type(report.get('rows')) is not list or len(report['rows']) > 320):
        raise ValueError('invalid_completed_study')
    expected = {(seed, scenario, arm) for seed in study.SPLITS['train']
                for scenario in study.SCENARIOS for arm in study.ARMS}
    rows = {}
    for row in report['rows']:
        if (type(row) is not dict or type(row.get('split')) is not str
                or row['split'] not in study.SPLITS):
            raise ValueError('invalid_study_row')
        if row['split'] != 'train':
            continue  # Do not inspect any later-split outcome or trace.
        try:
            seed, scenario, arm = row['episode']['seed'], row['episode']['scenario'], row['arm']
            if type(seed) is not int or type(scenario) is not str or type(arm) is not str:
                raise ValueError('invalid_training_identity')
            identity = (seed, scenario, arm)
            if identity not in expected or identity in rows:
                raise ValueError('invalid_training_roster')
            worker.validate({k: v for k, v in row.items() if k != 'split'}, seed, scenario, arm)
            rows[identity] = row['episode']['trace']
        except (KeyError, TypeError) as exc:
            raise ValueError('invalid_training_row') from exc
    if set(rows) != expected:
        raise ValueError('incomplete_training_roster')

    windows, pairs, all_steps = [], [], []
    for scenario in study.SCENARIOS:
        for arm in study.ARMS:
            horizon = 'h3' if arm.endswith('h3') else 'h1'
            for start in range(0, STEPS, WINDOW):
                stop = min(start + WINDOW, STEPS)
                steps = [s for seed in study.SPLITS['train']
                         for s in rows[(seed, scenario, arm)][start:stop]]
                all_steps.extend(steps)
                identity = {'scenario': scenario, 'arm': arm, 'start_step': start,
                            'stop_step_exclusive': stop, 'episodes': len(study.SPLITS['train'])}
                windows.append({**identity, 'summary': _summarize(steps),
                                'phases': {phase: _summarize([s for s in steps if s['phase'] == phase])
                                           for phase in PHASES}})
                for control in ('frozen_' + horizon, 'adaptive_consistent_' + horizon):
                    deltas = []
                    for seed in study.SPLITS['train']:
                        candidate_steps = rows[(seed, scenario, arm)][start:stop]
                        control_steps = rows[(seed, scenario, control)][start:stop]
                        deltas.append({'seed': seed, **{
                            'mean_' + metric + '_delta': sum(
                                candidate[metric] - baseline[metric]
                                for candidate, baseline in zip(candidate_steps, control_steps)) / (stop-start)
                            for metric in ('goal_error', 'prediction_error')}})
                    pairs.append({**identity, 'control': control, 'paired_episodes': deltas,
                                  **{key: sum(d[key] for d in deltas) / len(deltas)
                                     for key in ('mean_goal_error_delta', 'mean_prediction_error_delta')}})
    return {'status': 'complete', 'protocol': 'evidence-rejection-diagnostic-v1',
            'training_episodes': len(rows), 'window_steps': WINDOW,
            'totals': _summarize(all_steps), 'windows': windows, 'paired_windows': pairs,
            'delta_semantics': 'Arm minus matched control; positive error deltas are worse; equal-arm controls are zero',
            'phase_semantics': 'Recorded post-observation/recovery phase; sensor route can describe the previous phase',
            'inference': 'Descriptive training associations only; prediction calibration is an untested hypothesis',
            'true_gain_use': 'Retrospective scoring only, never candidate input',
            'validation_holdout_used': False, 'new_episodes': 0,
            'parameters_tuned': False, 'gates_changed': False,
            'promotion_authorized': False, 'deployed': False, 'goal_achieved': False,
            'next_action': 'register_prediction_calibration_study'}
