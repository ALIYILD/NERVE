"""Finite, preregistered public synthetic policy research; never promotion.

A durable claim is consumed before any trial, including failed/crashed runs.
The host controls the database: this is replay prevention, not sealed custody.
"""
from hashlib import sha256
import json
from pathlib import Path
import random
import re
import sqlite3

from . import self_study

SCENARIOS = ('stationary', 'abrupt', 'recurrent', 'mixed')
SPLITS = (('train', (1001, 1002)), ('validation', (2001, 2002)),
          ('holdout', (3001, 3002, 3003, 3004, 3005)))
CANDIDATES = tuple((w, t, d) for w in (3, 5, 10)
                   for t in ('relevance', 'least_recent') for d in (None, 3))
BASELINE = (3, 'relevance', None)
MAX_GENERATIONS, CANDIDATES_PER_GENERATION, PATIENCE = 3, 4, 2
MAX_TRIAL_CALLS = 272


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode()).hexdigest()


def _key(config):
    return f'{config[0]}:{config[1]}:{config[2]}'


def _cases(seed, scenario, *, splits=None, domain="policy-loop-v2"):
    splits = SPLITS if splits is None else splits
    if type(seed) is not int or seed not in {s for _, seeds in splits for s in seeds} or scenario not in SCENARIOS:
        raise ValueError('preregistered fixture required')
    rng = random.Random(seed)
    base = bool(rng.randrange(2))
    change_point = rng.randint(8, 14)
    period, offset = rng.randint(3, 6), rng.randrange(6)
    offset %= period
    cases = []
    for index in range(25):
        trim = (base if scenario == 'stationary' else
                (base if index < change_point else not base) if scenario == 'abrupt' else
                (base if ((index + offset) // period) % 2 == 0 else not base)
                if scenario == 'recurrent' else (base if rng.randrange(4) != 0 else not base))
        identifier = _digest([domain, seed, scenario, index])[:24].upper()
        cases.append(({'document': json.dumps({'email': f'  {identifier}@EXAMPLE.TEST  '})}, trim))
    return tuple(cases)


def protocol_manifest():
    protocol = {'version': 2, 'evaluator_revision': 'policy-research-transform-v2',
        'candidates': [list(c) for c in CANDIDATES], 'baseline': list(BASELINE),
        'max_generations': MAX_GENERATIONS, 'candidates_per_generation': CANDIDATES_PER_GENERATION,
        'patience': PATIENCE, 'max_trial_calls': MAX_TRIAL_CALLS,
        'feedback_executions': 20, 'frozen_probe_executions': 5,
        'scenarios': list(SCENARIOS), 'splits': {s: list(seeds) for s, seeds in SPLITS},
        'seeded_regimes': {'base': 'uniform boolean', 'abrupt_change_point': [8, 14], 'recurrent_period': [3, 6], 'recurrent_offset': 'randrange(6) modulo period', 'mixed_base_probability': 0.75},
        'evaluator_source_sha256': {name: sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in ('policy_research_loop.py', 'self_study.py', 'learning.py', 'automation.py', '../adaptive_memory.py', '../agent_bridge_v13.py', 'gateway.py', 'policy.py', 'contracts.py', 'session.py', 'lifecycle.py', '../memory_v18.py', '../memory_retrieval_v18.py')},
        'dataset_sha256': _digest([(seed, scenario, _cases(seed, scenario))
            for _, seeds in SPLITS for seed in seeds for scenario in SCENARIOS]),
        'selection': 'strict validation gain; aggregate training and every validation scenario nonregression against incumbent and baseline',
        'holdout': 'one final selected/baseline/fixed-lower/fixed-trim comparison; no tuning afterward',
        'candidate_order': 'window, tie-break, decay Cartesian order; baseline cached',
        'public_synthetic_nonsealed': True, 'promotion_authorized': False}
    return {**protocol, 'protocol_sha256': _digest(protocol)}


def _evaluate(seed, scenario, config, fixed=None):
    return self_study._execute_trial(_cases(seed, scenario), seed, scenario,
        window=None if fixed else config[0], fixed=fixed, tie_break=config[1],
        decay_half_life=config[2], evaluator_revision='policy-research-transform-v2')


def _validate(row, seed, scenario, fixed=None, *, config=None):
    if not isinstance(row, dict) or row.get('seed') != seed or row.get('scenario') != scenario:
        raise ValueError('invalid evaluator identity')
    outcomes = row.get('probe_outcomes')
    if not isinstance(outcomes, list) or len(outcomes) != 5 or any(type(v) is not bool for v in outcomes):
        raise ValueError('invalid evaluator probes')
    counts = {'executions': 25, 'feedback_executions': 20, 'probe_executions': 5,
              'feedback_writes': 0 if fixed else 20, 'probe_feedback_writes': 0}
    if any(type(row.get(key)) is not int or row[key] != expected for key, expected in counts.items()):
        raise ValueError('evaluator execution budget or feedback gate failed')
    if (type(row.get('probe_hits')) is not int or row['probe_hits'] != sum(outcomes)
        or row.get('executions') != 25 or row.get('probe_feedback_writes') != 0
        or row.get('frozen_probe_state_unchanged') is not True):
        raise ValueError('evaluator correctness gate failed')
    # Force JSON-safe bounded evidence before accepting any measurement.
    if len(json.dumps(row, allow_nan=False)) > 32768:
        raise ValueError('oversized evaluator evidence')
    return row


def _totals(rows):
    return {scenario: sum(r['probe_hits'] for r in rows if r['scenario'] == scenario)
            for scenario in SCENARIOS}


def _claim(path, run_id, manifest):
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE IF NOT EXISTS policy_research_runs_v2 (run_id TEXT PRIMARY KEY, protocol_sha256 TEXT NOT NULL, manifest TEXT NOT NULL, status TEXT NOT NULL, report TEXT)')
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS policy_research_protocol_once_v2 ON policy_research_runs_v2(protocol_sha256)')
        con.execute('CREATE TABLE IF NOT EXISTS policy_research_cycles_v2 (run_id TEXT NOT NULL, generation INTEGER NOT NULL, evidence TEXT NOT NULL, PRIMARY KEY(run_id,generation))')
        con.execute('CREATE TABLE IF NOT EXISTS policy_research_datasets_v2 (dataset_sha256 TEXT PRIMARY KEY, run_id TEXT NOT NULL)')
        try:
            con.execute('INSERT INTO policy_research_runs_v2 VALUES (?,?,?,?,NULL)',
                        (run_id, manifest['protocol_sha256'], json.dumps(manifest), 'claimed'))
            con.execute('INSERT INTO policy_research_datasets_v2 VALUES (?,?)', (manifest['dataset_sha256'], run_id))
        except sqlite3.IntegrityError as exc:
            raise ValueError('research run, protocol or dataset already consumed; no resume or replay') from exc


def run_policy_research(path, run_id):
    """Execute a frozen finite experiment; return a recommendation, never deploy."""
    return _run(path, run_id, _evaluate)


def _run(path, run_id, evaluator, *, manifest=None, validator=None):
    if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', run_id):
        raise ValueError('invalid run identifier')
    path = Path(path)
    manifest = protocol_manifest() if manifest is None else manifest
    candidates = tuple(tuple(c) for c in manifest['candidates'])
    baseline_config = tuple(manifest['baseline'])
    splits = tuple((name, tuple(manifest['splits'][name]))
                   for name in ('train', 'validation', 'holdout'))
    _claim(path, run_id, manifest)
    validator = _validate if validator is None else validator
    calls = 0
    cache, cycles = {}, []
    def trial(seed, scenario, config, fixed=None):
        nonlocal calls
        if calls >= manifest['max_trial_calls']:
            raise RuntimeError('trial budget exhausted')
        calls += 1
        return validator(evaluator(seed, scenario, config, fixed), seed, scenario, fixed, config=config)
    def candidate(config):
        key = _key(config)
        if key not in cache:
            cache[key] = {split: [trial(seed, scenario, config)
                for seed in seeds for scenario in SCENARIOS] for split, seeds in splits[:2]}
        return cache[key]
    try:
        baseline = candidate(baseline_config)
        selected, stalled = baseline_config, 0
        stop = 'generation_budget'
        for generation in range(manifest['max_generations']):
            previous, decisions = selected, []
            for config in candidates[generation * manifest['candidates_per_generation']:(generation + 1) * manifest['candidates_per_generation']]:
                result, incumbent = candidate(config), candidate(selected)
                train = sum(_totals(result['train']).values())
                val = _totals(result['validation'])
                reasons = []
                if sum(val.values()) <= sum(_totals(incumbent['validation']).values()):
                    reasons.append('no_strict_validation_gain')
                for reference, data in (('incumbent', incumbent), ('baseline', baseline)):
                    if train < sum(_totals(data['train']).values()):
                        reasons.append(reference + '_training_regression')
                    for scenario, hits in _totals(data['validation']).items():
                        if val[scenario] < hits:
                            reasons.append(reference + '_validation_regression:' + scenario)
                if not reasons:
                    selected = config
                decisions.append({'candidate': list(config), 'accepted_provisionally': not reasons,
                    'reasons': reasons, 'training_hits': train, 'validation_hits': val})
            stalled = stalled + 1 if selected == previous else 0
            evidence = {'generation': generation + 1, 'decisions': decisions,
                        'selected': list(selected), 'trial_calls': calls, 'stalled_generations': stalled}
            cycles.append(evidence)
            with sqlite3.connect(path) as con:
                con.execute('INSERT INTO policy_research_cycles_v2 VALUES (?,?,?)',
                            (run_id, generation + 1, json.dumps(evidence)))
            if stalled >= manifest['patience']:
                stop = 'patience_exhausted'
                break
        selection = {'protocol_sha256': manifest['protocol_sha256'], 'selected': list(selected),
                     'cycles_sha256': _digest(cycles)}
        # Persist frozen selection before instantiating any holdout trial.
        with sqlite3.connect(path) as con:
            con.execute('UPDATE policy_research_runs_v2 SET status=?,report=? WHERE run_id=?',
                        ('holdout_claimed', json.dumps(selection), run_id))
        holdout = {}
        for name, config, fixed in (('selected', selected, None), ('baseline', baseline_config, None),
                                    ('fixed_lower', baseline_config, 'lower-only'), ('fixed_trim', baseline_config, 'trim-lower')):
            if name == 'baseline' and selected == baseline_config:
                holdout[name] = holdout['selected']
            else:
                holdout[name] = [trial(seed, scenario, config, fixed)
                    for seed in splits[2][1] for scenario in SCENARIOS]
        chosen, control = _totals(holdout['selected']), _totals(holdout['baseline'])
        deltas = {s: chosen[s] - control[s] for s in SCENARIOS}
        recommend = selected != baseline_config and sum(deltas.values()) > 0 and min(deltas.values()) >= 0
        report = {'run_id': run_id, 'protocol': manifest, 'cycles': cycles,
            'candidate_results': cache, 'selected': list(selected), 'stop_reason': stop,
            'selection_sha256': _digest(selection), 'selection_frozen_before_holdout': True,
            'holdout': holdout, 'holdout_scenario_deltas': deltas,
            'recommendation': 'candidate_for_review' if recommend else 'retain_baseline',
            'trial_calls': calls, 'tool_executions': calls * 25,
            'promotion_authorized': False, 'deployed': False, 'model_weights_trained': False,
            'scope': 'Public synthetic strategy-selection fixture; not scientific discovery or model training.',
            'cost_usd': None, 'replay_protection': 'operator-owned SQLite; not independent holdout custody'}
        with sqlite3.connect(path) as con:
            con.execute('UPDATE policy_research_runs_v2 SET status=?,report=? WHERE run_id=?',
                        ('complete', json.dumps(report, allow_nan=False), run_id))
        return report
    except BaseException:
        with sqlite3.connect(path) as con:
            con.execute('UPDATE policy_research_runs_v2 SET status=?,report=? WHERE run_id=?',
                        ('failed_consumed', json.dumps({'trial_calls': calls, 'error': 'evaluation_aborted'}), run_id))
        raise
