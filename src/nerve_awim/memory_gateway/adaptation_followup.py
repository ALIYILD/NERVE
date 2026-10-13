"""Bounded, evidence-only objective diagnosis after a registered recovery study."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from . import recovery_adaptation_study as study

SOURCES = ('src/nerve_awim/memory_gateway/adaptation_followup.py',
           'scripts/diagnose_recovery_adaptation.py')


def _sources():
    return {name: sha256((study.ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def diagnose(report):
    """Describe validation traces only; caller must authenticate the receipt first.

    Fixed physical windows and joint command-source strata exhaust every matched
    step. Strata are descriptive, not causal effects or new acceptance gates.
    """
    rows = [row for row in report['rows'] if row['split'] == 'validation']
    comparison = study.compare(rows)
    indexed = {(r['seed'], r['scenario'], r['adaptive']): r for r in rows}
    seeds = sorted({r['seed'] for r in rows})
    groups = []
    for scenario in study.SCENARIOS:
        pairs = [(indexed[seed, scenario, False], indexed[seed, scenario, True]) for seed in seeds]
        for baseline, adaptive in pairs:
            for row in (baseline, adaptive):
                clean = dict(row)
                clean.pop('split')
                study.episode.validate(clean, row['seed'], scenario, row['adaptive'])
        for window in range(4):
            for source_pair in ('controller/controller', 'controller/external_supervisor',
                                'external_supervisor/controller', 'external_supervisor/external_supervisor'):
                selected = [(b, a) for baseline, adaptive in pairs
                            for b, a in zip(baseline['trace'], adaptive['trace'])
                            if window * 20 <= b['step'] < (window + 1) * 20
                            and b['action_source'] + '/' + a['action_source'] == source_pair]
                goal = sum(a['goal_error'] - b['goal_error'] for b, a in selected)
                prediction = sum(a['prediction_error'] - b['prediction_error'] for b, a in selected)
                groups.append({'scenario': scenario, 'start_step': window * 20,
                               'end_step_exclusive': (window + 1) * 20,
                               'baseline_adaptive_command_sources': source_pair,
                               'matched_steps': len(selected),
                               'goal_error_delta_sum': goal,
                               'prediction_error_delta_sum': prediction,
                               'goal_mean_delta_contribution': goal / (80 * len(seeds)),
                               'prediction_mean_delta_contribution': prediction / (80 * len(seeds)),
                               'prediction_better_goal_worse_steps': sum(
                                   a['prediction_error'] < b['prediction_error'] and
                                   a['goal_error'] > b['goal_error'] for b, a in selected)})
    mismatch = [scenario for scenario, arms in comparison['summaries'].items()
                if arms['adaptive']['mean_prediction_error'] < arms['baseline']['mean_prediction_error']
                and arms['adaptive']['mean_goal_error'] > arms['baseline']['mean_goal_error']]
    return {'status': 'diagnosed', 'comparison': comparison, 'groups': groups,
            'aggregate_objective_mismatch_regimes': mismatch,
            'validation_episodes_inspected': len(rows), 'matched_steps': 80 * len(rows) // 2,
            'new_plant_episodes': 0, 'holdout_rows_inspected_for_diagnosis': 0,
            'candidate_selected': False, 'deployed': False, 'goal_achieved': False,
            'next_action': ('register_objective_aligned_candidate_study' if mismatch else
                            'review_validation_regressions'),
            'interpretation': 'Post hoc descriptive diagnosis; command-source strata are not causal. No tuning, new acceptance gate, or general learning claim.'}


def _read_verified(predecessor, claims):
    path = Path(predecessor) / 'report.json'
    snapshot = path.read_bytes()
    study.validate_receipt(predecessor, claims)
    if path.read_bytes() != snapshot:
        raise ValueError('predecessor_changed_during_validation')
    report = json.loads(snapshot)
    # Reconciliation a second time below binds this snapshot against mutation.
    if report['recommendation'] != 'retain_baseline':
        raise ValueError('no_registered_rejection_followup')
    return report


def run_followup(directory, predecessor, study_claims, followup_claims):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    root = root.resolve()
    claims = Path(followup_claims).resolve()
    if claims == root or root in claims.parents:
        raise ValueError('shared_claims_must_be_outside_run')
    sources = _sources()
    report = _read_verified(predecessor, study_claims)
    digest = sha256(study._json(report).encode()).hexdigest()
    with sqlite3.connect(claims) as db:
        db.execute('CREATE TABLE IF NOT EXISTS adaptation_followups(predecessor_sha256 TEXT PRIMARY KEY, directory TEXT, status TEXT, evidence TEXT)')
        try:
            db.execute('INSERT INTO adaptation_followups VALUES (?,?,?,NULL)', (digest, str(root), 'claimed'))
        except sqlite3.IntegrityError as exc:
            raise ValueError('predecessor_followup_already_consumed') from exc
    try:
        result = diagnose(report)
        if study._json(_read_verified(predecessor, study_claims)) != study._json(report):
            raise ValueError('predecessor_changed')
        if _sources() != sources:
            raise ValueError('followup_source_drift')
        result.update(predecessor_sha256=digest, source_sha256=sources,
                      replay_protection='Operator-owned shared claim ledger; deletion or replacement is not prevented')
        encoded = study._json(result)
        (root / 'report.json').write_text(encoded + '\n')
        with sqlite3.connect(claims) as db:
            db.execute('UPDATE adaptation_followups SET status=?,evidence=? WHERE predecessor_sha256=?',
                       ('complete', encoded, digest))
        validate_receipt(root, predecessor, study_claims, claims)
        return result
    except BaseException:
        with sqlite3.connect(claims) as db:
            db.execute('UPDATE adaptation_followups SET status=? WHERE predecessor_sha256=?', ('failed_consumed', digest))
        raise


def validate_receipt(directory, predecessor, study_claims, followup_claims):
    root = Path(directory).resolve()
    report = _read_verified(predecessor, study_claims)
    digest = sha256(study._json(report).encode()).hexdigest()
    result = json.loads((root / 'report.json').read_text())
    expected = diagnose(report)
    expected.update(predecessor_sha256=digest, source_sha256=_sources(),
                    replay_protection='Operator-owned shared claim ledger; deletion or replacement is not prevented')
    with sqlite3.connect(Path(followup_claims).resolve().as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT directory,status,evidence FROM adaptation_followups WHERE predecessor_sha256=?', (digest,)).fetchone()
    if (study._json(expected) != study._json(result) or
            row != (str(root), 'complete', study._json(result))):
        raise ValueError('invalid_adaptation_followup_receipt')
    return True
