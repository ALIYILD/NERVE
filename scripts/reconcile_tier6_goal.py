"""One dev-only orchestration goal delegating evaluation to Galahad's v3 gate."""
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
PLAN = '01c5346e707c54689f73e64a0b25238a76864f628d5e51c2b770e16d140c8179'
BANK = 'e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6'
ROSTER = '9fcedd8027a4bbace580f5752e5aeee6f653d75e7cf5d022feac683375acc089'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def registration(galahad, research):
    plan = galahad / 'docs/galahad/plans/nerve-self-learning-loops-36-45.md'
    bank = research / 'task-bank-v1'
    study = research / 'scientific-candidate-v3-study'
    protocol = json.loads((study / 'preregistration.json').read_text())
    if digest(plan) != PLAN or digest(bank/'manifest.json') != BANK or protocol['dataset_sha256'] != ROSTER:
        raise ValueError('plan_bank_or_roster_identity_mismatch')
    if protocol['paths']['bank_manifest_sha256'] != BANK or Path(protocol['paths']['bank_directory']).resolve() != bank:
        raise ValueError('registered_bank_mismatch')
    if len(protocol['roster']) != 100 or any(not r['task_id'].startswith('dev-') for r in protocol['roster']):
        raise ValueError('development_only_roster_required')
    return {'goal': 'tier6-v3-dev-selection-reconciliation', 'galahad_root': str(galahad),
        'plan_sha256': PLAN, 'bank_manifest_sha256': BANK, 'dev_roster_sha256': ROSTER,
        'development_sha256': digest(bank/'dev.json'), 'split': 'dev',
        'study_directory': str(study), 'expected_digest': protocol['expected_digest'],
        'journal': protocol['journal'], 'paths': protocol['paths'],
        'preregistration_sha256': digest(study/'preregistration.json'),
        'report_sha256': digest(study/'report.json'),
        'controls': ['always_abstain', 'random', 'baseline'],
        'incumbent': 'compact_with_abstain', 'candidate': 'candidate_v3',
        'target_floor': protocol['acceptance'], 'new_model_calls_budget': 0,
        'holdout_access_authorized': False, 'promotion_authorized': False,
        'production_activation_authorized': False}


def gate_worker(binding):
    """Validate the existing terminal claim with read-only SQLite and open guards."""
    bank = Path(binding['paths']['bank_directory']).resolve()
    research = bank.parent
    before = {}
    busy = False
    denied = []

    def snapshot(path):
        nonlocal busy
        if busy or path in before or not path.is_file():
            return
        busy = True
        try:
            before[path] = (digest(path), path.stat().st_mtime_ns)
        finally:
            busy = False

    def audit(event, args):
        if event in ('socket.__new__', 'socket.connect', 'subprocess.Popen', 'os.system'):
            denied.append(event)
            raise PermissionError('no_network_or_dispatch_in_dev_verification')
        if event != 'open' or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        if not path.is_relative_to(research):
            return
        if 'holdout' in str(path).lower() or path.suffix == '.seed':
            denied.append('holdout_or_seed_open')
            raise PermissionError('development_only')
        flags = args[2] if len(args) > 2 else 0
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            if path.name != 'supervisor.lock' or not path.is_file():
                denied.append('evidence_write')
                raise PermissionError('read_only_canonical_evidence')
        snapshot(path)

    sys.addaudithook(audit)
    original_connect = sqlite3.connect
    copies = []

    def readonly_connect(database, *args, **kwargs):
        raw = str(database)
        path = Path(unquote(urlparse(raw).path)) if raw.startswith('file:') else Path(raw)
        path = path.resolve()
        if not path.is_relative_to(research) or 'holdout' in str(path).lower() or not path.is_file():
            raise PermissionError('existing_development_database_only')
        snapshot(path)
        # Legacy verification calls issue idempotent schema initialization.
        # Permit that only in a transient copy, never the canonical database.
        source = original_connect(path.as_uri()+'?mode=ro', uri=True)
        kwargs.pop('uri', None)
        connection = original_connect(':memory:', *args, **kwargs)
        source.backup(connection)
        source.close()
        copies.append((connection, tuple(connection.iterdump())))
        return connection

    sqlite3.connect = readonly_connect
    sys.path.insert(0, str(Path(binding['galahad_root'])/'src'))
    from nerve_awim.memory_gateway import scientific_candidate_v3_study as gate
    if not Path(gate.__file__).resolve().is_relative_to(Path(binding['galahad_root'])):
        raise ValueError('wrong_galahad_gate_import')
    # Only the canonical verifier: no orchestrator scoring, run, or new study claim.
    checked = gate.validate_receipt(binding['study_directory'], binding['expected_digest'],
                                    binding['journal'], **binding['paths'])
    if checked['status'] != 'complete' or checked['protocol']['dataset_sha256'] != ROSTER:
        raise ValueError('completed_bound_development_study_required')
    if any(checked[k] is not False for k in ('holdout_accessed', 'promotion_authorized', 'efficacy_established')):
        raise ValueError('forbidden_authority_or_scope')
    unchanged = all((digest(path), path.stat().st_mtime_ns) == previous for path, previous in list(before.items()))
    logical_unchanged = all(tuple(connection.iterdump()) == initial for connection, initial in copies)
    if not unchanged or not logical_unchanged or denied:
        raise ValueError('read_only_verification_boundary_failed')
    summary = checked['summary']
    return {'verified': True, 'evaluator': 'Galahad scientific_candidate_v3_study.validate_receipt',
        'gate_verdict': summary['verdict'], 'candidate_selected_for_review': summary['verdict'] == 'candidate_requires_review',
        'generalization_verdict': summary['generalization_verdict'],
        'gate_summary': summary, 'new_model_calls': 0, 'holdout_accessed': False,
        'promotion_authorized': False, 'production_activation_authorized': False,
        'canonical_files_unchanged': unchanged, 'canonical_files_checked': len(before),
        'sqlite_copies_logically_unchanged': logical_unchanged, 'sqlite_connections_checked': len(copies),
        'boundary_violations': denied, 'study_report_sha256': digest(Path(binding['study_directory'])/'report.json')}


def build_goal(state, binding, evaluate):
    spec = importlib.util.spec_from_file_location('nerve_goal_supervisor', ROOT/'src/nerve_awim/goal_orchestrator.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    encoded = json.dumps(binding, sort_keys=True, indent=2)+'\n'
    identity = sha256(encoded.encode()).hexdigest()
    state.mkdir(parents=True, exist_ok=True)
    record = state/'registration.json'
    if record.exists():
        if record.read_text() != encoded:
            raise ValueError('goal_binding_changed')
    else:
        with record.open('x') as stream:
            stream.write(encoded)
    goal = module.GoalOrchestrator(state, handlers={'galahad-evaluate': lambda _: evaluate()},
        validators={'galahad-evaluate': lambda r: (r['verified'] is True and r['candidate_selected_for_review'] is True
            and r['new_model_calls'] == 0 and r['holdout_accessed'] is False
            and r['promotion_authorized'] is False and r['production_activation_authorized'] is False)})
    goal_id = binding['goal']+':'+identity
    if goal.path.exists():
        if goal.inspect()['goal_id'] != goal_id:
            raise ValueError('goal_identity_changed')
    else:
        goal.create(goal_id=goal_id, target='Galahad dev gate: '+binding['target_floor'],
                    tasks=[{'id': 'evaluate', 'handler': 'galahad-evaluate'}])
    return goal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--galahad-root', type=Path)
    parser.add_argument('--research-root', type=Path)
    parser.add_argument('--state', type=Path)
    parser.add_argument('--worker', type=Path)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(gate_worker(json.loads(args.worker.read_text())), indent=2))
        return
    if not all((args.galahad_root, args.research_root, args.state)):
        parser.error('galahad-root, research-root and state required')
    binding = registration(args.galahad_root.resolve(), args.research_root.resolve())
    def evaluate():
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', str(args.state/'registration.json')],
                                   capture_output=True, text=True, timeout=180, check=True)
        return json.loads(completed.stdout)
    result = build_goal(args.state, binding, evaluate).run()
    print(json.dumps(result, indent=2))
    if result['status'] != 'complete':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
