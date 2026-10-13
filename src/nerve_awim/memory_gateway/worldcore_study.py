"""One-shot public synthetic WorldCore study with durable evaluator claims.

Host-owned research only. Directory freshness prevents accidental local replay;
operator deletion/copying is not a sealed holdout or anti-tamper boundary.
"""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from threading import Lock

from ..autoresearch_v04 import evaluate, STEPS
from ..worldcore_recursion_v19 import WorldCoreResearchEvolution

VALIDATION_SEEDS = tuple(range(31001, 31009))
HOLDOUT_SEEDS = tuple(range(32001, 32009))
MUTATION_SEED = 20261013
MAX_CALLS = 12
ROOT = Path(__file__).resolve().parents[3]
SOURCES = tuple('src/nerve_awim/' + name + '.py' for name in (
    'worldcore_recursion_v19', 'autoresearch_v04', 'autoresearch_v05',
    'worldcore_v20', 'risk_v17', 'adaptive_calibration_v19', 'coverage_v18',
    'calibrated_v16', 'calibration_v15', 'integrated_v13', 'fusion_v12',
    'drift_v14', 'parallel_agents_v11', 'memory_gateway/worldcore_study',
)) + ('scripts/run_worldcore_study.py',)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hashes():
    return {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def manifest():
    return {'protocol': 'worldcore-fresh-v1', 'validation_seeds': VALIDATION_SEEDS,
            'holdout_seeds': HOLDOUT_SEEDS, 'mutation_seed': MUTATION_SEED,
            'generations': 3, 'offspring': 3, 'max_evaluator_calls': MAX_CALLS,
            'max_simulation_episodes': MAX_CALLS * 8, 'max_steps_per_episode': STEPS,
            'source_sha256': _hashes(), 'public_synthetic_nonsealed': True,
            'promotion_authorized': False}


def run_study(directory):
    """Execute once in a new directory; no retries or configurable evaluator."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    database = root / 'ledger.sqlite'
    protocol = manifest()
    (root / 'protocol.json').write_text(_json(protocol) + '\n')
    with sqlite3.connect(database) as db:
        db.executescript('''
            CREATE TABLE study (id INTEGER PRIMARY KEY CHECK(id=1), status TEXT,
                                protocol TEXT, selection TEXT, result TEXT);
            CREATE TABLE calls (ordinal INTEGER PRIMARY KEY, role TEXT,
                                proposal TEXT, seeds TEXT, source_sha256 TEXT,
                                status TEXT, metrics TEXT);
        ''')
        db.execute('INSERT INTO study VALUES (1, ?, ?, NULL, NULL)',
                   ('running', _json(protocol)))
    lock = Lock()

    def check_sources():
        if _hashes() != protocol['source_sha256']:
            raise RuntimeError('source_drift')

    def selection(chosen):
        check_sources()
        frozen = {**chosen, 'lineage_sha256': sha256(_json(chosen['lineage']).encode()).hexdigest()}
        with lock, sqlite3.connect(database) as db:
            if db.execute('SELECT selection FROM study').fetchone()[0] is not None:
                raise RuntimeError('selection_already_frozen')
            db.execute('UPDATE study SET selection=? WHERE id=1', (_json(frozen),))

    def claimed_evaluate(proposal, seeds):
        check_sources()
        with lock, sqlite3.connect(database) as db:
            frozen = db.execute('SELECT selection FROM study').fetchone()[0]
            count = db.execute('SELECT COUNT(*) FROM calls').fetchone()[0]
            if count >= MAX_CALLS:
                raise RuntimeError('evaluator_budget_exhausted')
            if seeds == VALIDATION_SEEDS and frozen is None:
                role = 'baseline_validation' if count == 0 else 'candidate_validation'
            elif seeds == HOLDOUT_SEEDS and frozen is not None:
                holds = db.execute("SELECT COUNT(*) FROM calls WHERE role LIKE '%holdout'").fetchone()[0]
                if holds >= 2:
                    raise RuntimeError('holdout_already_consumed')
                role = 'baseline_holdout' if holds == 0 else 'selected_holdout'
            else:
                raise RuntimeError('unregistered_evaluator_call')
            ordinal = count + 1
            db.execute('INSERT INTO calls VALUES (?, ?, ?, ?, ?, ?, NULL)',
                       (ordinal, role, _json(asdict(proposal)), _json(seeds),
                        _json(protocol['source_sha256']), 'claimed'))
        # Claim transaction commits before simulation, including concurrent workers.
        try:
            metrics = evaluate(proposal, seeds)
            check_sources()
            if not WorldCoreResearchEvolution._metrics_ok(metrics):
                raise ValueError('invalid_evaluator_metrics')
            with lock, sqlite3.connect(database) as db:
                db.execute('UPDATE calls SET status=?, metrics=? WHERE ordinal=?',
                           ('complete', _json(metrics), ordinal))
            return metrics
        except BaseException:
            with lock, sqlite3.connect(database) as db:
                db.execute('UPDATE calls SET status=? WHERE ordinal=?', ('failed', ordinal))
            raise

    try:
        result = WorldCoreResearchEvolution(
            generations=3, offspring=3, seed=MUTATION_SEED,
            validation_seeds=VALIDATION_SEEDS, holdout_seeds=HOLDOUT_SEEDS,
            evaluator=claimed_evaluate, on_selection=selection).run()
        check_sources()
        with sqlite3.connect(database) as db:
            calls = db.execute('SELECT ordinal, role, proposal, seeds, source_sha256, status, metrics FROM calls ORDER BY ordinal').fetchall()
            frozen = json.loads(db.execute('SELECT selection FROM study').fetchone()[0])
        rows = [dict(zip(('ordinal', 'role', 'proposal', 'seeds', 'source_sha256', 'status', 'metrics'),
                         (n, role, json.loads(p), json.loads(s), json.loads(h), status, json.loads(m))))
                for n, role, p, s, h, status, m in calls]
        report = {'status': 'complete', 'protocol': protocol, 'frozen_selection': frozen,
                  'result': result, 'calls': rows, 'evaluator_calls': len(rows),
                  'simulation_episodes': sum(len(row['seeds']) for row in rows),
                  'scope': 'Pure CPU synthetic simulation; no model training, device actuation, clinical use or deployment.'}
        with sqlite3.connect(database) as db:
            db.execute('UPDATE study SET status=?, result=? WHERE id=1', ('complete', _json(report)))
        (root / 'report.json').write_text(_json(report) + '\n')
        return report
    except BaseException as exc:
        with sqlite3.connect(database) as db:
            db.execute('UPDATE study SET status=?, result=? WHERE id=1',
                       ('failed', _json({'error_type': type(exc).__name__, 'claims_retained': True})))
        raise


def validate_receipt(directory, report, expected_protocol):
    """Reconcile a complete receipt and replay decisions using recorded metrics.

    This verifies bookkeeping and deterministic decision logic, not the truth of
    simulation measurements or operator-controlled filesystem integrity.
    Returns True or raises ValueError; never reruns simulator evaluations.
    """
    def require(condition):
        if not condition:
            raise ValueError('invalid_worldcore_receipt')

    root = Path(directory)
    try:
        require(_json(expected_protocol) == _json(manifest()))
        require(type(report) is dict and report.get('status') == 'complete')
        require(_json(report['protocol']) == _json(expected_protocol))
        require(_json(json.loads((root / 'protocol.json').read_text())) == _json(expected_protocol))
        require(_json(json.loads((root / 'report.json').read_text())) == _json(report))
        with sqlite3.connect((root / 'ledger.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
            studies = db.execute('SELECT id, status, protocol, selection, result FROM study').fetchall()
            raw_calls = db.execute('SELECT ordinal, role, proposal, seeds, source_sha256, status, metrics FROM calls ORDER BY ordinal').fetchall()
        require(len(studies) == 1)
        identity, status, protocol, frozen, persisted = studies[0]
        require(identity == 1 and status == 'complete')
        require(_json(json.loads(protocol)) == _json(expected_protocol))
        require(_json(json.loads(persisted)) == _json(report))
        require(_json(json.loads(frozen)) == _json(report['frozen_selection']))
        rows = [dict(zip(('ordinal', 'role', 'proposal', 'seeds', 'source_sha256', 'status', 'metrics'),
                         (n, role, json.loads(p), json.loads(s), json.loads(h), state, json.loads(m))))
                for n, role, p, s, h, state, m in raw_calls]
        require(_json(rows) == _json(report['calls']))
        require(3 <= len(rows) <= MAX_CALLS)
        require(type(report['evaluator_calls']) is int and report['evaluator_calls'] == len(rows))
        require(type(report['simulation_episodes']) is int and report['simulation_episodes'] == len(rows) * 8)
        require([row['ordinal'] for row in rows] == list(range(1, len(rows) + 1)))
        require([row['role'] for row in rows] == ['baseline_validation'] +
                ['candidate_validation'] * (len(rows) - 3) + ['baseline_holdout', 'selected_holdout'])
        indexed = {}
        for row in rows:
            require(row['status'] == 'complete')
            require(_json(row['source_sha256']) == _json(expected_protocol['source_sha256']))
            expected_seeds = HOLDOUT_SEEDS if row['role'].endswith('holdout') else VALIDATION_SEEDS
            require(_json(row['seeds']) == _json(expected_seeds))
            require(WorldCoreResearchEvolution._metrics_ok(row['metrics']))
            key = _json({'proposal': row['proposal'], 'seeds': row['seeds']})
            require(key not in indexed)
            indexed[key] = row
        frozen = report['frozen_selection']
        require(frozen['lineage_sha256'] == sha256(_json(frozen['lineage']).encode()).hexdigest())
        seen = set()
        selection_seen = []
        replay_lock = Lock()

        def replay_evaluator(proposal, seeds):
            key = _json({'proposal': asdict(proposal), 'seeds': seeds})
            with replay_lock:
                require(key in indexed and key not in seen)
                require(bool(selection_seen) == (seeds == HOLDOUT_SEEDS))
                seen.add(key)
                return json.loads(_json(indexed[key]['metrics']))

        def replay_selection(chosen):
            require(not selection_seen)
            expected = {**chosen, 'lineage_sha256': sha256(_json(chosen['lineage']).encode()).hexdigest()}
            require(_json(expected) == _json(frozen))
            selection_seen.append(True)

        # Repeat only trusted mutation/selection/gates, substituting all measured
        # values from the immutable receipt map. No fresh simulator work occurs.
        replayed = WorldCoreResearchEvolution(
            generations=3, offspring=3, seed=MUTATION_SEED,
            validation_seeds=VALIDATION_SEEDS, holdout_seeds=HOLDOUT_SEEDS,
            evaluator=replay_evaluator, on_selection=replay_selection).run()
        require(seen == set(indexed))
        require(_json(replayed) == _json(report['result']))
        require(_hashes() == expected_protocol['source_sha256'])
        return True
    except (KeyError, TypeError, OSError, sqlite3.Error, json.JSONDecodeError, RuntimeError) as exc:
        raise ValueError('invalid_worldcore_receipt') from exc
