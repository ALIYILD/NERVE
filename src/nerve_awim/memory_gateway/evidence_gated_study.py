"""Registered observation-evidence adaptation research loop; no automatic deployment."""
from hashlib import sha256
import json
import multiprocessing
from pathlib import Path
import sqlite3
import time

from . import memory_research_coordinator as coordinator
from dataclasses import asdict
import tempfile
from ..memory_v18 import MemoryAuthority, TrustedMemoryLedger
from .gateway import MemoryGateway
from .contracts import MemoryScope
from . import recovery_adaptation_study as recovery
from . import evidence_gated_episode as worker

SPLITS = {'train': tuple(range(41001, 41009)),
          'validation': tuple(range(42001, 42009)),
          'holdout': tuple(range(43001, 43017))}
ARMS = ('frozen_h1', 'frozen_h3', 'adaptive_consistent_h1', 'adaptive_consistent_h3',
        'gated_retain_h1', 'gated_retain_h3', 'gated_forget_h1', 'gated_forget_h3')
CANDIDATES = ARMS[4:]
SCENARIOS = recovery.SCENARIOS
SOURCES = tuple(dict.fromkeys(coordinator.SOURCES + (
    'src/nerve_awim/memory_v18.py',
    'src/nerve_awim/memory_retrieval_v18.py',
    'src/nerve_awim/memory_gateway/gateway.py',
    'src/nerve_awim/memory_gateway/contracts.py',
    'src/nerve_awim/memory_gateway/policy.py',
    'src/nerve_awim/memory_gateway/lifecycle.py',
    'src/nerve_awim/evidence_gated_dynamics.py',
    'src/nerve_awim/memory_gateway/evidence_gated_episode.py',
    'src/nerve_awim/memory_gateway/evidence_gated_study.py',
    'scripts/run_evidence_gated_study.py')))


def _sources():
    return {name: sha256((recovery.ROOT/name).read_bytes()).hexdigest() for name in SOURCES}


def manifest():
    return {'protocol': 'evidence-gated-study-v1', 'splits': SPLITS, 'arms': ARMS,
            'scenarios': SCENARIOS, 'max_episodes': 320, 'max_plant_steps': 25600,
            'child_timeout_seconds': 30, 'elapsed_budget_seconds': 1200,
            'source_sha256': _sources(), 'plant': recovery.manifest()['plant'],
            'controller': recovery.manifest()['controller'],
            'selection': 'Train only; unchanged recovery gates against frozen_h1, matched frozen horizon and matched adaptive consistent horizon; highest summed goal gain against frozen_h1, then lexical arm name',
            'validation': 'Selected candidate and unique frozen and adaptive controls only; no second candidate after failure',
            'holdout': 'Once after validation passes; selected candidate and identical controls',
            'cost': 'Observed episode wall time and actual enumerated longer-horizon sequences; no timing acceptance threshold or speedup claim',
            'evidence_window': 4, 'minimum_observations': 4,
            'error_multiplier': 3.0, 'minimum_shift': .03,
            'acceptance': recovery.manifest()['acceptance'],
            'promotion_authorized': False, 'candidate_space_frozen': True}


def controls(arm):
    if arm not in CANDIDATES:
        raise ValueError('invalid_candidate')
    horizon = 'h3' if arm.endswith('h3') else 'h1'
    return tuple(dict.fromkeys(('frozen_h1', 'frozen_' + horizon, 'adaptive_consistent_' + horizon)))


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


def _verified_predecessor(directory, journal):
    """Verify coordinator evidence without invoking its mutating run method.

    Memory is opened read-only and backed up to a private temporary snapshot:
    legacy gateway constructors initialize tables, so never open the source with
    those constructors. Scope is a fixed host-owned synthetic research identity.
    """
    root = Path(directory).resolve()
    artifact = root/'report.json'
    before = artifact.read_bytes()
    report = json.loads(before)
    config = report['protocol']
    scope = MemoryScope('synthetic-research', 'scientific-coordinator', 'verified-experiments')
    def require(condition):
        if not condition:
            raise ValueError('invalid_memory_coordinator_predecessor')
    require(config['scope'] == asdict(scope))
    require(config['directory'] == str(root))
    require(config['source_sha256'] == coordinator._sources())
    with tempfile.TemporaryDirectory(prefix='nerve-memory-check-') as temporary:
        memory = Path(config['memory_database']).resolve()
        snapshot = Path(temporary)/'snapshot.sqlite'
        with sqlite3.connect(memory.as_uri()+'?mode=ro', uri=True) as source:
            with sqlite3.connect(snapshot) as target:
                source.backup(target)
        authority = MemoryAuthority()
        reader = authority.issue(scope.tenant_id, scope.agent_id, permissions=('read',))
        gateway = MemoryGateway(TrustedMemoryLedger(snapshot, authority))
        plan = coordinator.ResearchMemoryPlanner(gateway).plan(
            reader, scope, config['study_directory'], config['study_claims'],
            config['supervisor_directory'])
    require(plan.action == 'diagnose_rejection_and_register_new_hypothesis')
    expected_config = {'protocol': coordinator.PROTOCOL, 'scope': asdict(scope),
        'memory_database': str(memory), 'memory_id': plan.memory_id,
        'receipt_sha256': plan.receipt_sha256,
        'study_directory': str(Path(config['study_directory']).resolve()),
        'study_claims': str(Path(config['study_claims']).resolve()),
        'supervisor_directory': str(Path(config['supervisor_directory']).resolve()),
        'directory': str(root), 'source_sha256': coordinator._sources(), 'max_nodes': 1}
    require(recovery._json(config) == recovery._json(expected_config))
    original = coordinator._read_study(config['study_directory'], plan.receipt_sha256)
    result = coordinator.diagnostic.diagnose(original)
    require(result['next_action'] == 'register_prediction_calibration_study')
    expected = {'status': 'new_registered_experiment_required', 'protocol': expected_config,
        'plan': plan.to_dict(), 'diagnostic': result, 'new_episodes': 0,
        'promotion_authorized': False, 'model_weights_trained': False,
        'goal_achieved': False, 'next_action': result['next_action']}
    encoded = recovery._json(expected)+'\n'
    require(before == encoded.encode())
    key = sha256(recovery._json([coordinator.PROTOCOL, asdict(scope), plan.receipt_sha256]).encode()).hexdigest()
    with sqlite3.connect(Path(journal).resolve().as_uri()+'?mode=ro', uri=True) as db:
        rows = db.execute('SELECT config,status,digest FROM memory_research_runs_v1 WHERE identity=?', (key,)).fetchall()
    digest = sha256(before).hexdigest()
    require(rows == [(recovery._json(config), 'complete', digest)])
    require(artifact.read_bytes() == before)
    require(coordinator._sources() == config['source_sha256'])
    return sha256(recovery._json({'report_sha256': digest, 'identity': key,
        'journal': str(Path(journal).resolve()), 'row': rows[0]}).encode()).hexdigest()


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
                    'longer_horizon_sequences': sum(r['planning_sequences'] for r in subset),
                    'accepted_observations': sum(r['episode']['learning_updates'] for r in subset),
                    'gain_changes': (sum(r['learning_evidence'][-1]['gain_changes']
                                         for r in subset) if arm in CANDIDATES else None)}
    return result


def run_study(directory, claims, coordinator_directory, coordinator_journal):
    return _run(directory, claims, coordinator_directory, coordinator_journal, _execute)


def _run(directory, claims, coordinator_directory, coordinator_journal, execute):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    root = root.resolve()
    claims = Path(claims).resolve()
    if root == claims or root in claims.parents:
        raise ValueError('shared_claims_must_be_outside_run')
    protocol = manifest()
    digest = _dataset(protocol)
    predecessor = _verified_predecessor(coordinator_directory, coordinator_journal)
    with sqlite3.connect(claims) as db:
        db.execute('CREATE TABLE IF NOT EXISTS evidence_gated_studies(dataset TEXT PRIMARY KEY,directory TEXT,status TEXT,protocol TEXT)')
        try:
            db.execute('INSERT INTO evidence_gated_studies VALUES (?,?,?,?)',
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
        if _verified_predecessor(coordinator_directory, coordinator_journal) != predecessor:
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
            db.execute('UPDATE evidence_gated_studies SET status=? WHERE dataset=?', ('complete', digest))
        validate_receipt(root, claims, coordinator_directory, coordinator_journal)
        return report
    except BaseException:
        with sqlite3.connect(ledger) as db:
            db.execute("UPDATE trials SET status='failed_consumed' WHERE status='claimed'")
            db.execute("UPDATE state SET status='failed_consumed'")
        with sqlite3.connect(claims) as db:
            db.execute("UPDATE evidence_gated_studies SET status='failed_consumed' WHERE dataset=?", (digest,))
        raise


def validate_receipt(directory, claims, coordinator_directory, coordinator_journal):
    root = Path(directory).resolve()
    report = json.loads((root/'report.json').read_text())
    protocol = manifest()
    def require(condition):
        if not condition: raise ValueError('invalid_evidence_gated_receipt')
    require(recovery._json(report['protocol']) == recovery._json(protocol))
    require(recovery._json(json.loads((root/'protocol.json').read_text())) == recovery._json(protocol))
    require(report['predecessor_sha256'] == _verified_predecessor(coordinator_directory, coordinator_journal))
    with sqlite3.connect((root/'ledger.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        state_rows = db.execute('SELECT id,status,evidence FROM state').fetchall()
        frozen_rows = db.execute('SELECT id,evidence FROM selection').fetchall()
        journal = db.execute('SELECT ordinal,split,seed,scenario,arm,status,evidence FROM trials ORDER BY ordinal').fetchall()
    require(state_rows == [(1, 'complete', recovery._json(report))])
    selection, stages = _assessment(report['rows'])
    require(frozen_rows == [(1, recovery._json(selection))])
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
        claim = db.execute('SELECT directory,status,protocol FROM evidence_gated_studies WHERE dataset=?', (digest,)).fetchone()
    require(claim == (str(root), 'complete', recovery._json(protocol)))
    require(_sources() == protocol['source_sha256'])
    return True
