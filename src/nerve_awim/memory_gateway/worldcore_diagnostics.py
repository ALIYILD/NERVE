"""Bounded mechanism diagnosis of the registered WorldCore outage protocol.

This measures the existing sensor-unavailable guard, not a plant trajectory or
candidate improvement. The plant completion bound is a source-derived inference.
No evaluation seed, holdout, policy promotion or external actuator is used.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from ..autoresearch_v04 import Proposal
from ..worldcore_v20 import WorldCoreV2
from . import worldcore_study

ROOT = worldcore_study.ROOT
SOURCES = worldcore_study.SOURCES + (
    'src/nerve_awim/memory_gateway/worldcore_diagnostics.py',)
LIMITS = tuple(range(2, 13))
RISKS = (0.0, 0.25, 2.0)
MAX_CASES = 33
_EXPECTED_FUNCTIONS = {
    'episode': 'ff53b6f66e8cf7b7931ea2a50fdc7a574d604f30311cea3f356d35bf64fe0861',
    '__post_init__': '33b761d989ba1ba4d9915702b96f98060e16bd588f001e9f35412007a81de1c4',
}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hashes():
    return {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def manifest():
    return {'protocol': 'worldcore-outage-diagnostic-v3',
            'max_missing_values': LIMITS, 'risk_aversion_values': RISKS,
            'max_cases': MAX_CASES, 'max_miss_and_choose_pairs': 231,
            'source_sha256': _hashes(), 'simulation_episodes': 0,
            'holdout_calls': 0, 'promotion_authorized': False}


def _legacy_ast_dump(node):
    """Render the registered Python 3.10 AST schema on newer interpreters.

    Only an empty type_params field (added in 3.12) is omitted. Nonempty
    generics and any other new fields remain visible and fail the fingerprint.
    Optional None fields are omitted and empty lists retained, as in 3.10.
    """
    if isinstance(node, ast.AST):
        fields = []
        for name, value in ast.iter_fields(node):
            if value is None and getattr(type(node), name, ...) is None:
                continue
            if name == 'type_params' and value == []:
                continue
            fields.append(name + '=' + _legacy_ast_dump(value))
        return type(node).__name__ + '(' + ', '.join(fields) + ')'
    if isinstance(node, list):
        return '[' + ', '.join(_legacy_ast_dump(value) for value in node) + ']'
    return repr(node)


def _source_contract():
    """Recognize only the inspected evaluator, rather than guess its semantics.

    Whole-function AST fingerprints make additional scheduling/control changes
    fail closed too. Formatting/comments do not alter this semantic contract.
    """
    tree = ast.parse((ROOT / 'src/nerve_awim/autoresearch_v04.py').read_text())
    for name, expected in _EXPECTED_FUNCTIONS.items():
        matches = [node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(matches) != 1 or sha256(_legacy_ast_dump(matches[0]).encode()).hexdigest() != expected:
            raise RuntimeError('unknown_evaluator_structure')
    controller_tree = ast.parse((ROOT / 'src/nerve_awim/worldcore_v20.py').read_text())
    controllers = [node for node in controller_tree.body
                   if isinstance(node, ast.ClassDef) and node.name == 'WorldCoreV2']
    if (len(controllers) != 1 or sha256(_legacy_ast_dump(controllers[0]).encode()).hexdigest()
            != 'd1277c35b5fe7e4b84bea4c9c724225c2f280f8bcb57d6f5f4bbbb16105406c8'):
        raise RuntimeError('unknown_controller_structure')
    assignments = {node.targets[0].id: node.value for node in tree.body
                   if isinstance(node, ast.Assign) and len(node.targets) == 1
                   and isinstance(node.targets[0], ast.Name)}
    steps = assignments.get('STEPS')
    if not isinstance(steps, ast.Constant) or type(steps.value) is not int or steps.value != 80:
        raise RuntimeError('unknown_step_budget')
    gates = ast.parse((ROOT / 'src/nerve_awim/autoresearch_v05.py').read_text())
    values = {node.targets[0].id: node.value for node in gates.body
              if isinstance(node, ast.Assign) and len(node.targets) == 1
              and isinstance(node.targets[0], ast.Name)}
    for name, expected in (('MIN_COMPLETION', 0.95), ('MAX_ABORT_FRACTION', 0.0),
                           ('MAX_VIOLATIONS', 0.0)):
        value = values.get(name)
        if not isinstance(value, ast.Constant) or type(value.value) is not float or value.value != expected:
            raise RuntimeError('unknown_absolute_gates')
    return {'forced_dropout_origin_steps': [35, 49], 'delivery_delay_steps': 2,
            'latest_pre_outage_delivery_step': 36,
            'earliest_post_outage_delivery_step': 52,
            'guaranteed_consecutive_missing_steps': 15,
            'max_allowed_missing_tolerance': 12, 'episode_step_budget': 80,
            'absolute_min_completion': 0.95,
            'absolute_max_abort_fraction': 0.0}


def _case(max_missing, risk_aversion):
    if (type(max_missing) is not int or max_missing not in LIMITS
            or type(risk_aversion) not in (int, float) or risk_aversion not in RISKS):
        raise ValueError('unregistered_diagnostic_case')
    Proposal('mechanism-diagnostic', max_missing, risk_aversion)
    controller = WorldCoreV2(max_missing=max_missing, risk_aversion=risk_aversion)
    for missing in range(1, max_missing + 1):
        controller.miss()
        try:
            controller.choose()
        except RuntimeError as exc:
            if str(exc) != 'sensor unavailable: external safety supervision required':
                raise RuntimeError('unexpected_guard_failure') from None
            if missing != max_missing:
                raise RuntimeError('unexpected_guard_boundary')
            return {'max_missing': max_missing, 'risk_aversion': risk_aversion,
                    'first_sensor_unavailable_count': missing,
                    'successful_choose_calls': missing - 1,
                    'miss_calls': missing, 'choose_calls': missing,
                    'plant_actions': 0}
    raise RuntimeError('sensor_guard_did_not_stop')


def run_diagnostic(directory):
    """One-shot local diagnosis. Existing paths are refused; failures consumed."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    database = root / 'ledger.sqlite'
    with sqlite3.connect(database) as db:
        db.executescript('''
            CREATE TABLE diagnostic (id INTEGER PRIMARY KEY CHECK(id=1),
                status TEXT, protocol TEXT, report TEXT);
            CREATE TABLE cases (ordinal INTEGER PRIMARY KEY, max_missing INTEGER,
                risk_aversion REAL, status TEXT, evidence TEXT);
        ''')
        db.execute("INSERT INTO diagnostic VALUES (1, 'running', NULL, NULL)")
    ordinal = None
    try:
        protocol = manifest()
        with sqlite3.connect(database) as db:
            db.execute('UPDATE diagnostic SET protocol=?', (_json(protocol),))
        (root / 'protocol.json').write_text(_json(protocol) + '\n')

        def check_sources():
            if _hashes() != protocol['source_sha256']:
                raise RuntimeError('source_drift')

        contract = _source_contract()
        check_sources()
        rows = []
        for limit in LIMITS:
            for risk in RISKS:
                check_sources()
                ordinal = len(rows) + 1
                if ordinal > MAX_CASES:
                    raise RuntimeError('diagnostic_budget_exhausted')
                with sqlite3.connect(database) as db:
                    db.execute('INSERT INTO cases VALUES (?, ?, ?, ?, NULL)',
                               (ordinal, limit, risk, 'claimed'))
                evidence = _case(limit, risk)
                check_sources()
                row = {'ordinal': ordinal, 'status': 'complete', **evidence}
                with sqlite3.connect(database) as db:
                    db.execute('UPDATE cases SET status=?, evidence=? WHERE ordinal=?',
                               ('complete', _json(row), ordinal))
                rows.append(row)
                ordinal = None
        check_sources()
        report = {'status': 'complete', 'protocol': protocol,
                  'source_contract': contract, 'cases': rows,
                  'mechanism_cases': len(rows),
                  'measured_miss_calls': sum(row['miss_calls'] for row in rows),
                  'measured_choose_calls': sum(row['choose_calls'] for row in rows),
                  'simulation_episodes': 0, 'holdout_calls': 0,
                  'structural_inference': {
                      'latest_abort_step': 48, 'maximum_completed_steps': 48,
                      'maximum_completion': 48 / 80,
                      'absolute_completion_gate_satisfiable': False,
                      'absolute_abort_gate_satisfiable': False,
                      'scope': 'All registered max_missing 2..12 and risk_aversion 0..2 under the inspected evaluator; random dropouts or infeasibility may abort earlier.'},
                  'recommendation': 'stop_unmodified_parameter_search',
                  'policy_promoted': False, 'model_weights_trained': False,
                  'limitations': '33 guard mechanism measurements, not full plant executions. Completion bound inferred from fixed packet schedule and verified guard. Risk continuum follows the guard preceding risk scoring. No safe physical fallback demonstrated.'}
        with sqlite3.connect(database) as db:
            db.execute('UPDATE diagnostic SET status=?, report=?', ('complete', _json(report)))
        (root / 'report.json').write_text(_json(report) + '\n')
        return report
    except BaseException as exc:
        failure = {'status': 'failed', 'error_type': type(exc).__name__,
                   'claims_retained': True, 'retry_authorized': False}
        with sqlite3.connect(database) as db:
            if ordinal is not None:
                db.execute("UPDATE cases SET status='failed' WHERE ordinal=?", (ordinal,))
            db.execute('UPDATE diagnostic SET status=?, report=?', ('failed', _json(failure)))
        (root / 'error.json').write_text(_json(failure) + '\n')
        raise


def validate_receipt(directory, report):
    """Reconcile stored mechanism evidence without executing any case again.

    Checks local bookkeeping and the registered structural inference. This is
    not independent custody or proof against an operator rewriting all evidence.
    """
    def require(condition):
        if not condition:
            raise ValueError('invalid_diagnostic_receipt')

    root = Path(directory)
    try:
        expected = manifest()
        require(type(report) is dict and report.get('status') == 'complete')
        require(_json(report['protocol']) == _json(expected))
        require(_json(report['source_contract']) == _json(_source_contract()))
        require(_json(json.loads((root / 'protocol.json').read_text())) == _json(expected))
        require(_json(json.loads((root / 'report.json').read_text())) == _json(report))
        with sqlite3.connect((root / 'ledger.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
            records = db.execute('SELECT id, status, protocol, report FROM diagnostic').fetchall()
            cases = db.execute('SELECT ordinal, max_missing, risk_aversion, status, evidence FROM cases ORDER BY ordinal').fetchall()
        require(len(records) == 1)
        identity, status, protocol, persisted = records[0]
        require(identity == 1 and status == 'complete')
        require(_json(json.loads(protocol)) == _json(expected))
        require(_json(json.loads(persisted)) == _json(report))
        require(type(report['cases']) is list and len(report['cases']) == MAX_CASES)
        require(len(cases) == MAX_CASES)
        expected_parameters = [(limit, risk) for limit in LIMITS for risk in RISKS]
        for index, ((limit, risk), stored, row) in enumerate(zip(expected_parameters, cases, report['cases']), 1):
            ordinal, stored_limit, stored_risk, case_status, evidence = stored
            require(ordinal == index and stored_limit == limit and stored_risk == risk and case_status == 'complete')
            expected_row = {'ordinal': index, 'status': 'complete', 'max_missing': limit,
                            'risk_aversion': risk, 'first_sensor_unavailable_count': limit,
                            'successful_choose_calls': limit - 1, 'miss_calls': limit,
                            'choose_calls': limit, 'plant_actions': 0}
            require(_json(row) == _json(expected_row))
            require(_json(json.loads(evidence)) == _json(expected_row))
        for name, value in (('mechanism_cases', MAX_CASES), ('measured_miss_calls', 231),
                            ('measured_choose_calls', 231), ('simulation_episodes', 0),
                            ('holdout_calls', 0), ('policy_promoted', False),
                            ('model_weights_trained', False),
                            ('recommendation', 'stop_unmodified_parameter_search')):
            require(_json(report[name]) == _json(value))
        inference = report['structural_inference']
        for name, value in (('latest_abort_step', 48), ('maximum_completed_steps', 48),
                            ('maximum_completion', .6),
                            ('absolute_completion_gate_satisfiable', False),
                            ('absolute_abort_gate_satisfiable', False)):
            require(_json(inference[name]) == _json(value))
        require(_hashes() == expected['source_sha256'])
        return True
    except (KeyError, TypeError, OSError, sqlite3.Error, json.JSONDecodeError, RuntimeError) as exc:
        raise ValueError('invalid_diagnostic_receipt') from exc
