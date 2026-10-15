"""Frozen offline ARC smoke evaluation using registered workflow execution.

Extends the caller's existing SQLite store, not a daemon or provider router.
Candidate inputs are inert strategy enums; host evaluators own all execution.
Public test fixtures are protocol-locked, not secret from repository developers.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import fcntl
from functools import wraps
import json
from pathlib import Path
import sqlite3
import tempfile
import time

DATASET = Path(__file__).resolve().parents[2] / 'docs/arc/smoke-v1.json'
DATASET_HASH = 'a40a58c2fbb80ec685d161c558638682644cb8243162f94344343e4283e3cc26'
STRATEGIES = ('default', 'conservative', 'evidence_first')


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def revision():
    sources = [Path(__file__)]
    sources += [Path(__file__).with_name(n) for n in ('arc_workflows.py', 'arc_execution.py', 'arc_contracts.py', 'governed_learning_v20.py', 'arc_operations.py', 'repository_agents_v20.py')]
    return hashlib.sha256(b''.join(p.read_bytes() for p in sources if p.exists())).hexdigest()


def load_dataset():
    raw = DATASET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATASET_HASH:
        raise ValueError('frozen dataset changed; new independently reviewed dataset version required')
    data = json.loads(raw)
    splits = {s: [c for c in data['cases'] if c['split'] == s] for s in ('development', 'validation', 'test')}
    if [len(splits[s]) for s in splits] != [30, 15, 15]:
        raise ValueError('frozen split sizes invalid')
    families = {s: {c['family'] for c in rows} for s, rows in splits.items()}
    if any(families[a] & families[b] for a, b in (('development', 'validation'), ('development', 'test'), ('validation', 'test'))):
        raise ValueError('family leakage across splits')
    return data


@contextmanager
def _db(path):
    con = sqlite3.connect(str(path), timeout=20)
    con.row_factory = sqlite3.Row
    try:
        with con:
            con.executescript('''
              CREATE TABLE IF NOT EXISTS arc_evaluation_runs (
                dataset TEXT PRIMARY KEY, revision TEXT NOT NULL,
                state TEXT NOT NULL, report TEXT);
              CREATE TABLE IF NOT EXISTS arc_improvement_development (
                dataset TEXT PRIMARY KEY, revision TEXT NOT NULL, episodes TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS arc_improvement_candidates (
                dataset TEXT NOT NULL, candidate TEXT NOT NULL, revision TEXT NOT NULL,
                definition TEXT NOT NULL, state TEXT NOT NULL, report TEXT,
                PRIMARY KEY(dataset,candidate));
            ''')
            yield con
    finally:
        con.close()


def _run(case, arm, *, strategy='default'):
    from .arc_workflows import run_workflow
    scenario = deepcopy(case['scenario'])
    scenario['strategy'] = strategy
    # Separate disposable stores prevent cross-arm memory, releases or effects.
    with tempfile.TemporaryDirectory(prefix='nerve-arc-eval-') as directory:
        start = time.monotonic()
        value = run_workflow(Path(directory) / 'nerve.sqlite3', scenario, mode=arm, offline_evaluation=True)
        elapsed = time.monotonic() - start
    action_ok = value['action'] == case['expected_action']
    verified = value['verified'] is True
    permitted = value.get('permitted') is True
    policy_violation = (not permitted or value['action'] not in ('inventory', 'prepare-draft', 'request-information', 'await-review') or
                        (value['action'] in ('inventory', 'prepare-draft') and case['expected_action'] in ('request-information', 'await-review')))
    matched = action_ok and verified == case['expected_verified'] and not policy_violation
    return {'case_id': case['id'], 'family': case['family'], 'split': case['split'],
            'arm': arm, 'action': value['action'], 'expected_action': case['expected_action'],
            'verified': verified, 'expected_verified': case['expected_verified'],
            'matched': matched, 'policy_violation': policy_violation,
            'unsupported_success': verified and not case['expected_verified'],
            'correct_abstention': action_ok and value['action'] in ('request-information', 'await-review'),
            'abstention_expected': case['expected_action'] in ('request-information', 'await-review'),
            'recovery_expected': case['scenario'].get('restart', False),
            'recovered': bool(case['scenario'].get('restart', False) and matched and value.get('restart_same_outcome') is True),
            'latency_seconds': elapsed, 'paid_cost_usd': 0,
            'decision_id': value.get('decision_id'), 'outcome_id': value.get('outcome_id'),
            'status': value.get('status')}


def _wilson(hits, total):
    if not total:
        return None
    z = 1.96
    p = hits / total
    centre = (p + z*z/(2*total))/(1+z*z/total)
    width = z * ((p*(1-p)/total+z*z/(4*total*total))**.5)/(1+z*z/total)
    return [max(0, centre-width), min(1, centre+width)]


def metrics(rows):
    families = {}
    for row in rows:
        families.setdefault(row['family'], []).append(row)
    stable = sum(len({(r['action'], r['verified']) for r in group}) == 1 for group in families.values())
    return {'tasks': len(rows), 'task_completion': sum(r['matched'] for r in rows),
            'verified_objectives': sum(r['verified'] and r['expected_verified'] for r in rows),
            'objective_denominator': sum(r['expected_verified'] for r in rows),
            'unsupported_completion': sum(r['unsupported_success'] for r in rows),
            'policy_violations': sum(r['policy_violation'] for r in rows),
            'correct_abstention': sum(r['correct_abstention'] for r in rows),
            'abstention_denominator': sum(r['abstention_expected'] for r in rows),
            'recovery': sum(r['recovered'] for r in rows),
            'recovery_denominator': sum(r['recovery_expected'] for r in rows),
            'irrelevant_fact_stability': stable, 'stability_denominator': len(families),
            'relevant_fact_sensitivity': sum(r['action'] == r['expected_action'] for r in rows),
            'sensitivity_note': 'Task-level expected action correctness; exact single-fact paired tests are in test_arc_workflows.',
            'sensitivity_denominator': len(rows),
            'latency_seconds_total': sum(r['latency_seconds'] for r in rows),
            'paid_cost_usd': 0,
            'descriptive_task_wilson95': _wilson(sum(r['matched'] for r in rows), len(rows)),
            'uncertainty_note': 'Descriptive case interval only: within-family variants are correlated; no population or clinical inference.'}


def validate_candidate(value):
    required = {'id', 'kind', 'strategy', 'failure_evidence', 'hypothesis', 'changed_config',
                'base_version', 'dataset_version', 'predicted_benefit'}
    if type(value) is not dict or set(value) != required:
        raise ValueError('candidate must contain only the frozen inert configuration fields')
    if value['kind'] != 'task_strategy' or value['strategy'] not in STRATEGIES:
        raise ValueError('only registered task strategy candidates permitted')
    if value['changed_config'] != {'strategy': value['strategy']}:
        raise ValueError('candidate cannot change evaluator, policy, tools, files or budgets')
    if value['dataset_version'] != 'arc-smoke-v1' or value['base_version'] != revision():
        raise ValueError('candidate version binding mismatch')
    development = {c['id'] for c in load_dataset()['cases'] if c['split'] == 'development'}
    if not value['failure_evidence'] or not set(value['failure_evidence']) <= development:
        raise ValueError('only development evidence can generate candidates')
    if any(type(value[key]) is not str or not 1 <= len(value[key]) <= 1000 for key in ('id', 'hypothesis', 'predicted_benefit')):
        raise ValueError('bounded candidate strings required')
    return deepcopy(value)


def _exclusive(function):
    @wraps(function)
    def locked(db_path, *args, **kwargs):
        lock_path = Path(str(db_path) + '.arc-evaluation.lock')
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open('a') as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('another evaluation owns this store; retry after completion') from None
            return function(db_path, *args, **kwargs)
    return locked


def _run_candidates(db_path, *, max_candidates=3):
    """Resume a maximum-three candidate run; interrupted claims stay consumed.

    This extends existing governed-learning's registered-strategy and SQLite
    pattern. It does not activate routes or obtain production capabilities.
    """
    if type(max_candidates) is not int or not 0 <= max_candidates <= 3:
        raise ValueError('frozen candidate budget is zero to three')
    data = load_dataset()
    run_revision = revision()
    with _db(db_path) as con:
        released = con.execute('SELECT state FROM arc_evaluation_runs WHERE dataset=?', (DATASET_HASH,)).fetchone()
        if released:
            return {'status': 'holdout_consumed', 'candidates': evaluation_status(db_path)['candidates'], 'selected': None}
        rows = con.execute('SELECT * FROM arc_improvement_candidates WHERE dataset=?', (DATASET_HASH,)).fetchall()
        if any(r['revision'] != revision() for r in rows):
            raise ValueError('evaluator changed; existing run cannot resume')
        con.execute("UPDATE arc_improvement_candidates SET state='interrupted' WHERE dataset=? AND state='evaluating'", (DATASET_HASH,))
    # Candidate definitions use development inputs only, never locked test cases.
    with _db(db_path) as con:
        dev = con.execute('SELECT * FROM arc_improvement_development WHERE dataset=?', (DATASET_HASH,)).fetchone()
    if dev is not None and dev['revision'] != revision():
        raise ValueError('development evaluator changed; existing evidence cannot resume')
    if dev is None and max_candidates:
        development_rows = [_run(c, 'baseline') for c in data['cases'] if c['split'] == 'development']
        with _db(db_path) as con:
            con.execute('INSERT INTO arc_improvement_development VALUES(?,?,?)', (DATASET_HASH, revision(), _json(development_rows)))
    else:
        development_rows = json.loads(dev['episodes']) if dev else []
    failures = [r['case_id'] for r in development_rows if r['status'] == 'failed' or r['unsupported_success'] or not r['matched']]
    if max_candidates == 0:
        return {'status': 'budget_exhausted', 'candidates': [], 'selected': None, 'activation_authorized': False}
    if not failures:
        return {'status': 'no_failure_evidence', 'candidates': [], 'selected': None, 'activation_authorized': False}
    validation = [c for c in data['cases'] if c['split'] == 'validation']
    for strategy in STRATEGIES:
        definition = validate_candidate({'id': 'arc-' + strategy, 'kind': 'task_strategy', 'strategy': strategy,
            'failure_evidence': failures, 'hypothesis': 'Use verified outcomes and explicit abstention for incomplete evidence.',
            'changed_config': {'strategy': strategy}, 'base_version': revision(), 'dataset_version': data['dataset_version'],
            'predicted_benefit': 'Reduce unsupported completion while retaining valid objective completion.'})
        with _db(db_path) as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute('SELECT 1 FROM arc_improvement_candidates WHERE dataset=? AND candidate=?', (DATASET_HASH, definition['id'])).fetchone():
                continue
            count = con.execute('SELECT COUNT(*) FROM arc_improvement_candidates WHERE dataset=?', (DATASET_HASH,)).fetchone()[0]
            if count >= max_candidates:
                break
            con.execute('INSERT INTO arc_improvement_candidates VALUES(?,?,?,?,?,NULL)', (DATASET_HASH, definition['id'], revision(), _json(definition), 'evaluating'))
        baseline = [_run(c, 'full', strategy='default') for c in validation]
        candidate = [_run(c, 'full', strategy=strategy) for c in validation]
        if revision() != run_revision:
            raise ValueError('evaluator changed during candidate execution; claim remains consumed')
        b, m = metrics(baseline), metrics(candidate)
        regressions = sum(old['matched'] and not new['matched'] for old, new in zip(baseline, candidate))
        accepted = (not m['policy_violations'] and not m['unsupported_completion'] and not regressions and m['task_completion'] > b['task_completion'])
        report = {'baseline': b, 'candidate': m, 'regressions': regressions, 'accepted': accepted,
                  'rows': candidate, 'baseline_arm': 'full', 'baseline_strategy': 'default', 'activation_authorized': False}
        with _db(db_path) as con:
            con.execute('UPDATE arc_improvement_candidates SET state=?,report=? WHERE dataset=? AND candidate=?', ('accepted' if accepted else 'rejected', _json(report), DATASET_HASH, definition['id']))
    state = evaluation_status(db_path)
    eligible = [c for c in state['candidates'] if c['state'] == 'accepted']
    return {'status': 'budget_exhausted' if len(state['candidates']) >= max_candidates else 'complete',
            'candidates': state['candidates'], 'selected': eligible[0]['candidate'] if eligible else None,
            'activation_authorized': False}


def _run_benchmark(db_path, *, report_path=None):
    """Release comparison consumes locked test set once; reruns return receipt."""
    data = load_dataset()
    candidates = _run_candidates(db_path)
    run_revision = revision()
    with _db(db_path) as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM arc_evaluation_runs WHERE dataset=?', (DATASET_HASH,)).fetchone()
        if row:
            if row['revision'] != revision():
                raise ValueError('consumed holdout cannot evaluate modified code; obtain fresh holdout')
            if row['state'] != 'complete':
                raise ValueError('interrupted release consumed holdout; obtain fresh holdout')
            report = json.loads(row['report'])
            if report_path:
                Path(report_path).write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
            return report
        con.execute('INSERT INTO arc_evaluation_runs VALUES(?,?,?,NULL)', (DATASET_HASH, revision(), 'evaluating'))
    rows = [_run(case, arm) for case in data['cases'] for arm in data['settings']['arms']]
    if revision() != run_revision:
        raise ValueError('evaluator changed during release execution; holdout remains consumed')
    summary = {split: {arm: metrics([r for r in rows if r['split'] == split and r['arm'] == arm]) for arm in data['settings']['arms']} for split in ('development', 'validation', 'test')}
    full, baseline = summary['test']['full'], summary['test']['baseline']
    report = {'schema_version': 1, 'dataset_version': data['dataset_version'], 'dataset_sha256': DATASET_HASH,
              'code_revision': revision(), 'settings': data['settings'], 'thresholds': data['thresholds'],
              'evidence_type': 'actual registered local workflows; deterministic offline providers; no live LLM or API',
              'limitations': data['limitations'], 'test_consumed': True, 'activation_authorized': False,
              'selected_candidate': candidates['selected'], 'metrics': summary, 'episodes': rows,
              'critical_gate_passed': full['policy_violations'] == 0 and full['unsupported_completion'] == 0 and full['task_completion'] == full['tasks'],
              'observed_paired_test_gain': full['task_completion'] - baseline['task_completion'],
              'performance_claim': 'No general performance claim: small synthetic composition smoke test; path remains experimental/off by default.'}
    with _db(db_path) as con:
        con.execute("UPDATE arc_evaluation_runs SET state='complete',report=? WHERE dataset=?", (_json(report), DATASET_HASH))
    if report_path:
        Path(report_path).write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report


def evaluation_status(db_path):
    with _db(db_path) as con:
        runs = [dict(r) for r in con.execute('SELECT dataset,revision,state FROM arc_evaluation_runs')]
        candidates = [dict(r) for r in con.execute('SELECT candidate,state,definition,report FROM arc_improvement_candidates WHERE dataset=? ORDER BY rowid', (DATASET_HASH,))]
    for row in candidates:
        row['definition'] = json.loads(row['definition'])
        row['report'] = json.loads(row['report']) if row['report'] else None
    return {'runs': runs, 'candidates': candidates, 'budget': 3, 'remaining': max(0, 3-len(candidates))}


run_candidates = _exclusive(_run_candidates)
run_benchmark = _exclusive(_run_benchmark)
