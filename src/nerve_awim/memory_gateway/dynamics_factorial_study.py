"""Registered diagnosis-to-factorial research loop; no automatic deployment."""
from hashlib import sha256
import json
import multiprocessing
from pathlib import Path
import sqlite3
import time

from . import adaptation_followup as followup
from . import recovery_adaptation_study as recovery
from . import dynamics_factorial_episode as worker

SPLITS = {'train': tuple(range(35001, 35009)),
          'validation': tuple(range(36001, 36009)),
          'holdout': tuple(range(37001, 37017))}
ARMS = ('frozen_h1', 'frozen_h3', 'adaptive_legacy_h1', 'adaptive_legacy_h3',
        'adaptive_consistent_h1', 'adaptive_consistent_h3')
CANDIDATES = ARMS[2:]
SCENARIOS = recovery.SCENARIOS
SOURCES = tuple(dict.fromkeys(recovery.SOURCES + followup.SOURCES + (
    'src/nerve_awim/consistent_dynamics.py',
    'src/nerve_awim/memory_gateway/dynamics_factorial_episode.py',
    'src/nerve_awim/memory_gateway/dynamics_factorial_study.py',
    'scripts/run_dynamics_factorial.py')))


def _sources():
    return {name: sha256((recovery.ROOT/name).read_bytes()).hexdigest() for name in SOURCES}


def manifest():
    return {'protocol': 'dynamics-factorial-v1', 'splits': SPLITS, 'arms': ARMS,
            'scenarios': SCENARIOS, 'max_episodes': 240, 'max_plant_steps': 19200,
            'child_timeout_seconds': 30, 'elapsed_budget_seconds': 900,
            'source_sha256': _sources(), 'plant': recovery.manifest()['plant'],
            'controller': recovery.manifest()['controller'],
            'selection': 'Train only; unchanged recovery gates against frozen_h1 and matched frozen horizon; highest summed goal gain against frozen_h1, then lexical arm name',
            'validation': 'Selected candidate and unique frozen controls only; no second candidate after failure',
            'holdout': 'Once after validation passes; selected candidate and identical controls',
            'cost': 'Observed episode wall time and actual enumerated longer-horizon sequences; no timing acceptance threshold or speedup claim',
            'promotion_authorized': False, 'candidate_space_frozen': True}


def controls(arm):
    if arm not in CANDIDATES:
        raise ValueError('invalid_candidate')
    return tuple(dict.fromkeys(('frozen_h1', 'frozen_h3' if arm.endswith('h3') else 'frozen_h1')))


def compare(rows, candidate):
    results = {}
    for control in controls(candidate):
        paired = []
        for row in rows:
            if row['arm'] not in (candidate, control):
                continue
            item = dict(row['episode'])
            item['adaptive'] = row['arm'] == candidate
            paired.append(item)
        results[control] = recovery.compare(paired)
    return {'passed': all(r['passed'] for r in results.values()), 'controls': results}


def select(rows):
    evaluations = {arm: compare(rows, arm) for arm in CANDIDATES}
    eligible = [arm for arm in CANDIDATES if evaluations[arm]['passed']]
    winner = min(eligible, key=lambda arm: (
        -evaluations[arm]['controls']['frozen_h1']['sum_regime_goal_gain'], arm)) if eligible else None
    return {'candidate': winner, 'evaluations': evaluations, 'selection_frozen': True}


def _verified_predecessor(paths):
    directory, predecessor, study_claims, followup_claims = paths
    path = Path(directory)/'report.json'
    before = path.read_bytes()
    followup.validate_receipt(directory, predecessor, study_claims, followup_claims)
    if path.read_bytes() != before:
        raise ValueError('predecessor_changed')
    report = json.loads(before)
    if report['next_action'] != 'register_objective_aligned_candidate_study':
        raise ValueError('no_registered_next_study')
    return sha256(before).hexdigest()


def _child(connection, seed, scenario, arm):
    try:
        connection.send(('ok', worker.execute(seed, scenario, arm)))
    except BaseException:
        connection.send(('failed', None))
    finally:
        connection.close()


def _execute(seed, scenario, arm, timeout=30):
    context = multiprocessing.get_context('spawn')
    reader, writer = context.Pipe(duplex=False)
    child = context.Process(target=_child, args=(writer, seed, scenario, arm))
    try:
        child.start(); writer.close()
        if not reader.poll(timeout):
            raise TimeoutError('episode_timeout')
        status, row = reader.recv()
        if status != 'ok':
            raise RuntimeError('episode_failed')
        return row
    finally:
        if child.pid is not None:
            if child.is_alive(): child.terminate()
            child.join(1)
            if child.is_alive(): child.kill(); child.join(1)
        reader.close(); writer.close()


def _dataset(protocol):
    return sha256(recovery._json({key: protocol[key] for key in ('splits', 'scenarios', 'plant')}).encode()).hexdigest()


def _assessment(rows):
    training = [r for r in rows if r['split'] == 'train']
    selection = select(training)
    stages = {}
    if selection['candidate']:
        for split in ('validation', 'holdout'):
            subset = [r for r in rows if r['split'] == split]
            if subset:
                stages[split] = compare(subset, selection['candidate'])
    return selection, stages


def work_summary(rows):
    """Observed episode time excludes process startup and coordinator validation."""
    result = {}
    for split in SPLITS:
        for arm in ARMS:
            subset = [r for r in rows if r['split'] == split and r['arm'] == arm]
            if subset:
                result[split + ':' + arm] = {
                    'episodes': len(subset),
                    'episode_elapsed_seconds': sum(r['elapsed_seconds'] for r in subset),
                    'longer_horizon_sequences': sum(r['planning_sequences'] for r in subset)}
    return result


def run_study(directory, claims, predecessor_paths):
    return _run(directory, claims, predecessor_paths, _execute)


def _run(directory, claims, predecessor_paths, execute):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    root = root.resolve()
    claims = Path(claims).resolve()
    if root == claims or root in claims.parents:
        raise ValueError('shared_claims_must_be_outside_run')
    protocol = manifest()
    digest = _dataset(protocol)
    predecessor = _verified_predecessor(predecessor_paths)
    with sqlite3.connect(claims) as db:
        db.execute('CREATE TABLE IF NOT EXISTS dynamics_studies(dataset TEXT PRIMARY KEY,directory TEXT,status TEXT,protocol TEXT)')
        try:
            db.execute('INSERT INTO dynamics_studies VALUES (?,?,?,?)',
                       (digest, str(root), 'claimed', recovery._json(protocol)))
        except sqlite3.IntegrityError as exc:
            raise ValueError('dataset_already_consumed') from exc
    ledger = root/'ledger.sqlite'
    with sqlite3.connect(ledger) as db:
        db.executescript('CREATE TABLE trials(ordinal INTEGER PRIMARY KEY,split TEXT,seed INTEGER,scenario TEXT,arm TEXT,status TEXT,evidence TEXT); CREATE TABLE state(id INTEGER PRIMARY KEY,status TEXT,evidence TEXT); CREATE TABLE selection(id INTEGER PRIMARY KEY,evidence TEXT);')
        db.execute('INSERT INTO state VALUES (1,?,NULL)', ('claimed',))
    (root/'protocol.json').write_text(recovery._json(protocol)+'\n')
    rows = []
    start = time.monotonic()
    try:
        selection = None
        stages = {}
        for split, seeds in SPLITS.items():
            arms = ARMS if split == 'train' else controls(selection['candidate']) + (selection['candidate'],)
            for seed in seeds:
                for scenario in SCENARIOS:
                    for arm in arms:
                        remaining = protocol['elapsed_budget_seconds'] - (time.monotonic()-start)
                        if remaining <= 0 or len(rows) >= protocol['max_episodes']:
                            raise RuntimeError('study_budget_exhausted')
                        if _sources() != protocol['source_sha256']:
                            raise ValueError('source_drift')
                        ordinal = len(rows)+1
                        with sqlite3.connect(ledger) as db:
                            db.execute('INSERT INTO trials VALUES (?,?,?,?,?,?,NULL)',
                                       (ordinal, split, seed, scenario, arm, 'claimed'))
                        row = execute(seed, scenario, arm, min(30, remaining))
                        worker.validate(row, seed, scenario, arm)
                        if time.monotonic()-start > protocol['elapsed_budget_seconds']:
                            raise RuntimeError('study_budget_exhausted')
                        if _sources() != protocol['source_sha256']:
                            raise ValueError('source_drift')
                        with sqlite3.connect(ledger) as db:
                            db.execute('UPDATE trials SET status=?,evidence=? WHERE ordinal=?',
                                       ('complete', recovery._json(row), ordinal))
                        rows.append({'split': split, **row})
            if split == 'train':
                selection = select(rows)
                with sqlite3.connect(ledger) as db:
                    db.execute('INSERT INTO selection VALUES (1,?)', (recovery._json(selection),))
                    db.execute('UPDATE state SET status=?,evidence=?',
                               ('selection_frozen', recovery._json(selection)))
                if selection['candidate'] is None:
                    break
            else:
                stages[split] = compare([r for r in rows if r['split'] == split], selection['candidate'])
                if not stages[split]['passed']:
                    break
        if _verified_predecessor(predecessor_paths) != predecessor:
            raise ValueError('predecessor_changed')
        if _sources() != protocol['source_sha256']:
            raise ValueError('source_drift')
        report = {'status': 'complete', 'protocol': protocol, 'predecessor_sha256': predecessor,
                  'dataset_sha256': digest, 'selection': selection, 'stages': stages,
                  'rows': rows, 'episodes': len(rows), 'plant_steps': len(rows)*80,
                  'measured_work': work_summary(rows),
                  'holdout_consumed': 'holdout' in stages,
                  'recommendation': 'candidate_for_review' if stages.get('holdout', {}).get('passed') else 'retain_baseline',
                  'deployed': False, 'model_weights_trained': False, 'goal_achieved': False}
        encoded = recovery._json(report)
        (root/'report.json').write_text(encoded+'\n')
        with sqlite3.connect(ledger) as db:
            db.execute('UPDATE state SET status=?,evidence=?', ('complete', encoded))
        with sqlite3.connect(claims) as db:
            db.execute('UPDATE dynamics_studies SET status=? WHERE dataset=?', ('complete', digest))
        validate_receipt(root, claims, predecessor_paths)
        return report
    except BaseException:
        with sqlite3.connect(ledger) as db:
            db.execute("UPDATE trials SET status='failed_consumed' WHERE status='claimed'")
            db.execute("UPDATE state SET status='failed_consumed'")
        with sqlite3.connect(claims) as db:
            db.execute("UPDATE dynamics_studies SET status='failed_consumed' WHERE dataset=?", (digest,))
        raise


def validate_receipt(directory, claims, predecessor_paths):
    root = Path(directory).resolve()
    report = json.loads((root/'report.json').read_text())
    protocol = manifest()
    def require(condition):
        if not condition: raise ValueError('invalid_factorial_receipt')
    require(recovery._json(report['protocol']) == recovery._json(protocol))
    require(recovery._json(json.loads((root/'protocol.json').read_text())) == recovery._json(protocol))
    require(report['predecessor_sha256'] == _verified_predecessor(predecessor_paths))
    with sqlite3.connect((root/'ledger.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        state = db.execute('SELECT status,evidence FROM state WHERE id=1').fetchone()
        frozen = db.execute('SELECT evidence FROM selection WHERE id=1').fetchone()
        journal = db.execute('SELECT ordinal,split,seed,scenario,arm,status,evidence FROM trials ORDER BY ordinal').fetchall()
    require(state == ('complete', recovery._json(report)))
    selection, stages = _assessment(report['rows'])
    require(frozen == (recovery._json(selection),))
    require(recovery._json(selection) == recovery._json(report['selection']))
    require(recovery._json(stages) == recovery._json(report['stages']))
    require(recovery._json(work_summary(report['rows'])) == recovery._json(report['measured_work']))
    expected = []
    for split, seeds in SPLITS.items():
        if split != 'train' and selection['candidate'] is None: break
        if split == 'holdout' and not stages.get('validation', {}).get('passed'): break
        arms = ARMS if split == 'train' else controls(selection['candidate'])+(selection['candidate'],)
        expected.extend((split, seed, scenario, arm) for seed in seeds for scenario in SCENARIOS for arm in arms)
    require(len(expected) == len(journal) == len(report['rows']))
    for ordinal, (identity, stored, row) in enumerate(zip(expected, journal, report['rows']), 1):
        split, seed, scenario, arm = identity
        require(stored[:6] == (ordinal, split, seed, scenario, arm, 'complete'))
        clean = dict(row)
        require(clean.pop('split') == split)
        worker.validate(clean, seed, scenario, arm)
        require(recovery._json(clean) == stored[6])
    require(recovery._json(report['episodes']) == recovery._json(len(expected)))
    require(recovery._json(report['plant_steps']) == recovery._json(80*len(expected)))
    require(report['holdout_consumed'] is ('holdout' in stages))
    recommendation = 'candidate_for_review' if stages.get('holdout', {}).get('passed') else 'retain_baseline'
    require(report['recommendation'] == recommendation and report['status'] == 'complete')
    require(all(report[k] is False for k in ('deployed','model_weights_trained','goal_achieved')))
    digest = _dataset(protocol)
    require(report['dataset_sha256'] == digest)
    with sqlite3.connect(Path(claims).resolve().as_uri()+'?mode=ro', uri=True) as db:
        claim = db.execute('SELECT directory,status,protocol FROM dynamics_studies WHERE dataset=?', (digest,)).fetchone()
    require(claim == (str(root), 'complete', recovery._json(protocol)))
    require(_sources() == protocol['source_sha256'])
    return True
