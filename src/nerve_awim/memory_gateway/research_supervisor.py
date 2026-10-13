"""Restartable finite research graph with receipt adoption and no blind retry."""
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from . import recovery_adaptation_study as recovery
from . import adaptation_followup as followup
from . import dynamics_factorial_study as factorial
from . import identification_diagnostic as identification

NODES = ('recovery', 'adaptation_diagnosis', 'factorial', 'identification_diagnosis')
PATH_KEYS = ('recovery', 'recovery_claims', 'diagnosis', 'diagnosis_claims', 'factorial', 'factorial_claims')
SOURCES = tuple(dict.fromkeys(factorial.SOURCES + (
    'src/nerve_awim/memory_gateway/identification_diagnostic.py',
    'src/nerve_awim/memory_gateway/research_supervisor.py',
    'scripts/run_research_supervisor.py')))


def _sources():
    return {name: sha256((recovery.ROOT/name).read_bytes()).hexdigest() for name in SOURCES}


def _paths(root, supplied):
    if type(supplied) is not dict or set(supplied) != set(PATH_KEYS):
        raise ValueError('invalid_registered_paths')
    if any(not isinstance(v, (str, Path)) or not str(v) for v in supplied.values()):
        raise ValueError('invalid_registered_path')
    result = {key: str(Path(value).resolve()) for key, value in supplied.items()}
    if len(set(result.values())) != len(result):
        raise ValueError('overlapping_registered_paths')
    return result


def _predecessors(paths):
    return (paths['diagnosis'], paths['recovery'], paths['recovery_claims'], paths['diagnosis_claims'])


def _artifact(root, paths, node):
    directory = {'recovery': paths['recovery'], 'adaptation_diagnosis': paths['diagnosis'],
                 'factorial': paths['factorial'], 'identification_diagnosis': str(root/'identification')}[node]
    return Path(directory)/'report.json'


def _validate(root, paths, node):
    artifact = _artifact(root, paths, node)
    before = artifact.read_bytes()
    if node == 'recovery':
        recovery.validate_receipt(paths['recovery'], paths['recovery_claims'])
    elif node == 'adaptation_diagnosis':
        followup.validate_receipt(*_predecessors(paths))
    elif node == 'factorial':
        factorial.validate_receipt(paths['factorial'], paths['factorial_claims'], _predecessors(paths))
    elif node == 'identification_diagnosis':
        parent, digest = _validate(root, paths, 'factorial')
        expected = identification.diagnose(parent)
        expected['predecessor_sha256'] = digest
        expected['source_sha256'] = _sources()
        if recovery._json(json.loads(before)) != recovery._json(expected):
            raise ValueError('invalid_identification_receipt')
    else:
        raise ValueError('unregistered_node')
    if artifact.read_bytes() != before:
        raise ValueError('artifact_changed_during_validation')
    return json.loads(before), sha256(before).hexdigest()


def _execute(root, paths, node):
    if node == 'recovery':
        recovery.run_study(paths['recovery'], paths['recovery_claims'])
    elif node == 'adaptation_diagnosis':
        followup.run_followup(paths['diagnosis'], paths['recovery'], paths['recovery_claims'], paths['diagnosis_claims'])
    elif node == 'factorial':
        factorial.run_study(paths['factorial'], paths['factorial_claims'], _predecessors(paths))
    elif node == 'identification_diagnosis':
        parent, digest = _validate(root, paths, 'factorial')
        result = identification.diagnose(parent)
        result['predecessor_sha256'] = digest
        result['source_sha256'] = _sources()
        directory = root/'identification'
        directory.mkdir(exist_ok=False)
        (directory/'report.json').write_text(recovery._json(result)+'\n')
    else:
        raise ValueError('unregistered_node')


def _stop_after(node, result):
    if node in ('recovery', 'factorial') and result['recommendation'] != 'retain_baseline':
        return 'candidate_requires_independent_review'
    if node == 'adaptation_diagnosis' and result['next_action'] != 'register_objective_aligned_candidate_study':
        return 'new_registered_experiment_required'
    if node == 'identification_diagnosis':
        return 'new_registered_experiment_required'
    return None


@contextmanager
def _exclusive(root):
    with (root/'supervisor.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('supervisor_already_running') from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def run(directory, paths):
    root = Path(directory)
    if root.is_symlink():
        raise ValueError('symlink_supervisor_root')
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    registered = _paths(root, paths)
    protocol = {'version': 'research-supervisor-v1', 'paths': registered, 'nodes': NODES,
                'max_nodes': 4, 'source_sha256': _sources(), 'promotion_authorized': False}
    with _exclusive(root):
        return _run_locked(root, registered, protocol)


def _run_locked(root, paths, protocol):
    ledger = root/'supervisor.sqlite'
    with sqlite3.connect(ledger) as db:
        db.executescript('CREATE TABLE IF NOT EXISTS config(id INTEGER PRIMARY KEY,evidence TEXT); CREATE TABLE IF NOT EXISTS nodes(name TEXT PRIMARY KEY,status TEXT,digest TEXT,origin TEXT,error TEXT);')
        previous = db.execute('SELECT evidence FROM config WHERE id=1').fetchone()
        if previous is None:
            db.execute('INSERT INTO config VALUES (1,?)', (recovery._json(protocol),))
        elif previous != (recovery._json(protocol),):
            raise ValueError('supervisor_protocol_changed')
    completed = []
    terminal = None
    for node in NODES:
        if _sources() != protocol['source_sha256']:
            raise ValueError('supervisor_source_drift')
        artifact = _artifact(root, paths, node)
        with sqlite3.connect(ledger) as db:
            existing = db.execute('SELECT status,digest,origin,error FROM nodes WHERE name=?', (node,)).fetchone()
            if existing is None:
                origin = 'adopted' if artifact.parent.exists() else 'executed'
                db.execute('INSERT INTO nodes VALUES (?,?,NULL,?,NULL)', (node, 'claimed', origin))
            else:
                origin = existing[2]
        if existing and existing[0] == 'failed_consumed':
            raise RuntimeError('node_failed_consumed:'+node)
        try:
            if existing and (existing[0] not in ('claimed', 'complete') or
                             existing[2] not in ('adopted', 'executed')):
                raise ValueError('invalid_node_journal_state')
            # Existing/claimed work is only reconciled. A partial directory or
            # missing receipt is never permission to dispatch another experiment.
            if existing is None and origin == 'executed':
                _execute(root, paths, node)
            result, digest = _validate(root, paths, node)
            if existing and existing[0] == 'complete' and existing[1] != digest:
                raise ValueError('completed_node_changed')
            if _sources() != protocol['source_sha256']:
                raise ValueError('supervisor_source_drift')
            with sqlite3.connect(ledger) as db:
                db.execute('UPDATE nodes SET status=?,digest=?,error=NULL WHERE name=?', ('complete', digest, node))
            completed.append({'node': node, 'status': 'complete', 'origin': origin, 'artifact_sha256': digest})
            terminal = _stop_after(node, result)
            if terminal:
                break
        except BaseException as exc:
            with sqlite3.connect(ledger) as db:
                db.execute('UPDATE nodes SET status=?,error=? WHERE name=?', ('failed_consumed', type(exc).__name__, node))
            (root/'report.json').write_text(recovery._json({
                'status': 'failed_consumed', 'failed_node': node, 'completed_nodes': completed,
                'error_type': type(exc).__name__, 'deployed': False, 'goal_achieved': False})+'\n')
            raise
    report = {'status': terminal, 'protocol': protocol, 'completed_nodes': completed,
              'automatic_retry': False, 'deployed': False, 'model_weights_trained': False,
              'goal_achieved': False, 'next_action': result.get('next_action', terminal)}
    (root/'report.json').write_text(recovery._json(report)+'\n')
    return report
