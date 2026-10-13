"""Registered, one-shot research DAG. Completion is not general self-learning.

Operator-owned receipts provide consistency checks, not sealed attestation.
A rejected policy completes a research task without authorizing promotion.
"""
from hashlib import sha256
import json
import multiprocessing
from pathlib import Path
import sqlite3

from . import online_optimisation as online
from . import policy_research_loop as loop
from . import worldcore_study as worldcore


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _same(a, b):
    if _json(a) != _json(b):
        raise ValueError('receipt_mismatch')


def verify_online(database, output, run_id):
    """Read only: validate registered protocol, all trials and final decision."""
    protocol = online.protocol_manifest()
    report = json.loads(Path(output).read_text())
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT protocol_sha256,manifest,status,report FROM policy_research_runs_v2 WHERE run_id=?', (run_id,)).fetchone()
        if row is None or row[2] != 'complete':
            raise ValueError('predecessor_not_complete')
        _same(row[0], protocol['protocol_sha256'])
        _same(json.loads(row[1]), protocol)
        _same(json.loads(row[3]), report)
        _same(report['protocol'], protocol)
        _same(report['run_id'], run_id)
        _same(db.execute('SELECT run_id FROM policy_research_datasets_v2 WHERE dataset_sha256=?', (protocol['dataset_sha256'],)).fetchone(), (run_id,))
        journal = db.execute('SELECT trial_index,seed,scenario,config,fixed_strategy,status,evidence FROM policy_research_trials_v2 WHERE run_id=? ORDER BY trial_index', (run_id,)).fetchall()
        cycles = [json.loads(r[0]) for r in db.execute('SELECT evidence FROM policy_research_cycles_v2 WHERE run_id=? ORDER BY generation', (run_id,))]
    _same(cycles, report['cycles'])
    expected = []
    def rows(values, split, config, fixed=None, append=True):
        identities = [(s, r) for s in protocol['splits'][split] for r in protocol['scenarios']]
        if len(values) != len(identities):
            raise ValueError('trial_count_mismatch')
        for value, (seed, scenario) in zip(values, identities):
            online._validate(value, seed, scenario, fixed, config=config)
            if append:
                expected.append((seed, scenario, list(config), fixed, value))
    candidates = report['candidate_results']
    _same(sorted(candidates), sorted(loop._key(c) for c in online.CANDIDATES))
    for config in online.CANDIDATES:
        item = candidates[loop._key(config)]
        _same(sorted(item), ['train', 'validation'])
        for split in ('train', 'validation'):
            rows(item[split], split, config)
    # Recompute selection from training/validation only, never final outcomes.
    selected = online.BASELINE
    totals = lambda values: loop._totals(values, 'hits')
    replayed_cycles, stalled = [], 0
    for generation in range(2):
        previous, decisions = selected, []
        for config in online.CANDIDATES[generation*4:(generation+1)*4]:
            candidate = candidates[loop._key(config)]
            incumbent = candidates[loop._key(selected)]
            baseline = candidates[loop._key(online.BASELINE)]
            train = sum(totals(candidate['train']).values())
            val = totals(candidate['validation'])
            reasons = []
            if sum(val.values()) <= sum(totals(incumbent['validation']).values()):
                reasons.append('no_strict_validation_gain')
            for name, reference in (('incumbent', incumbent), ('baseline', baseline)):
                if train < sum(totals(reference['train']).values()):
                    reasons.append(name + '_training_regression')
                for scenario, hits in totals(reference['validation']).items():
                    if val[scenario] < hits:
                        reasons.append(name + '_validation_regression:' + scenario)
            if not reasons:
                selected = config
            decisions.append({'candidate': list(config), 'accepted_provisionally': not reasons,
                              'reasons': reasons, 'training_hits': train, 'validation_hits': val})
        stalled = stalled + 1 if selected == previous else 0
        replayed_cycles.append({'generation': generation+1, 'decisions': decisions,
                                'selected': list(selected), 'trial_calls': 128 if generation == 0 else 224,
                                'stalled_generations': stalled})
    _same(cycles, replayed_cycles)
    _same(report['stop_reason'], 'patience_exhausted' if stalled >= 2 else 'generation_budget')
    _same(report['selected'], list(selected))
    _same(report['selection_sha256'], loop._digest({'protocol_sha256': protocol['protocol_sha256'], 'selected': list(selected), 'cycles_sha256': loop._digest(cycles)}))
    holdout = report['holdout']
    _same(sorted(holdout), ['baseline', 'fixed_lower', 'fixed_trim', 'selected'])
    for name, config, fixed in (('selected', selected, None), ('baseline', online.BASELINE, None), ('fixed_lower', online.BASELINE, 'lower-only'), ('fixed_trim', online.BASELINE, 'trim-lower')):
        duplicate = name == 'baseline' and selected == online.BASELINE
        rows(holdout[name], 'holdout', config, fixed, append=not duplicate)
        if duplicate:
            _same(holdout[name], holdout['selected'])
    if len(journal) != len(expected) or len(journal) > protocol['max_trial_calls']:
        raise ValueError('journal_count_mismatch')
    for index, (stored, expected_row) in enumerate(zip(journal, expected), 1):
        n, seed, scenario, config, fixed, status, evidence = stored
        _same((n, status), (index, 'complete'))
        _same((seed, scenario, json.loads(config), fixed, json.loads(evidence)), expected_row)
    chosen, control = totals(holdout['selected']), totals(holdout['baseline'])
    deltas = {s: chosen[s] - control[s] for s in protocol['scenarios']}
    recommend = selected != online.BASELINE and sum(deltas.values()) > 0 and min(deltas.values()) >= 0
    _same(report['holdout_scenario_deltas'], deltas)
    _same(report['recommendation'], 'candidate_for_review' if recommend else 'retain_baseline')
    for key, value in {'trial_calls': len(expected), 'pipeline_episodes': len(expected)*32, 'tool_executions': len(expected)*32, 'primitive_tool_invocations': len(expected)*64, 'executions_per_trial': 32, 'score_field': 'hits', 'selection_frozen_before_holdout': True, 'promotion_authorized': False, 'deployed': False, 'model_weights_trained': False}.items():
        _same(report[key], value)
    _same(online.protocol_manifest(), protocol)
    return {'status': 'completed_candidate_for_review' if recommend else 'completed_rejected', 'run_id': run_id, 'report_sha256': sha256(_json(report).encode()).hexdigest(), 'protocol_sha256': protocol['protocol_sha256'], 'trial_calls': len(expected), 'recommendation': report['recommendation']}


def _sources():
    sources = worldcore._hashes()
    for relative in ('src/nerve_awim/memory_gateway/research_orchestrator.py', 'scripts/run_research_orchestrator.py'):
        sources[relative] = sha256((worldcore.ROOT / relative).read_bytes()).hexdigest()
    return sources


def _child(directory):
    worldcore.run_study(directory)


def _execute(directory):
    process = multiprocessing.get_context('spawn').Process(target=_child, args=(directory,))
    try:
        process.start()
        process.join(120)
        if process.is_alive():
            raise TimeoutError('worldcore_timeout')
        if process.exitcode != 0:
            raise RuntimeError('worldcore_failed')
        return json.loads((Path(directory) / 'report.json').read_text())
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(1)
            if process.is_alive():
                process.kill()
                process.join(1)


def run_orchestrator(directory, online_database, online_output, online_run_id):
    return _run(directory, online_database, online_output, online_run_id, _execute)


def _run(directory, online_database, online_output, online_run_id, execute):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    database = root / 'orchestrator.sqlite'
    sources = _sources()
    protocol = worldcore.manifest()
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE nodes (name TEXT PRIMARY KEY, status TEXT, evidence TEXT)')
        db.execute('INSERT INTO nodes VALUES (?, ?, NULL)', ('online_receipt', 'claimed'))
    node = 'online_receipt'
    try:
        receipt = verify_online(online_database, online_output, online_run_id)
        with sqlite3.connect(database) as db:
            db.execute('UPDATE nodes SET status=?, evidence=? WHERE name=?', (receipt['status'], _json(receipt), node))
        _same(_sources(), sources)
        node = 'worldcore'
        with sqlite3.connect(database) as db:
            db.execute('INSERT INTO nodes VALUES (?, ?, NULL)', (node, 'claimed'))
        result = execute(root / 'worldcore')
        _same(_sources(), sources)
        _same(result['protocol'], protocol)
        _same(result['status'], 'complete')
        if result['result']['status'] not in ('candidate_for_human_review', 'no_deployable_improvement'):
            raise ValueError('unknown_child_result')
        worldcore.validate_receipt(root / 'worldcore', result, protocol)
        report = {'status': 'registered_graph_complete', 'online': receipt, 'worldcore': result, 'source_sha256': sources, 'deployed': False, 'model_weights_trained': False, 'goal_achieved': False, 'scope': 'Two registered synthetic research tracks; no general self-improvement claim. Existing roots cannot resume or replay.'}
        with sqlite3.connect(database) as db:
            db.execute('UPDATE nodes SET status=?,evidence=? WHERE name=?', ('complete', _json(result), node))
        (root / 'report.json').write_text(_json(report) + '\n')
        return report
    except BaseException as exc:
        with sqlite3.connect(database) as db:
            db.execute('UPDATE nodes SET status=?,evidence=? WHERE name=?', ('failed_consumed', _json({'error_type': type(exc).__name__}), node))
        (root / 'failure.json').write_text(_json({'status': 'failed_consumed', 'node': node, 'error_type': type(exc).__name__}) + '\n')
        raise
