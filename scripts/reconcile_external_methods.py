"""Orchestrate the Galahad external-methods staged evaluator in a separate process."""
import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(galahad, state, receipt, development):
    galahad, state = Path(galahad).resolve(), Path(state).resolve()
    script = galahad/'scripts/run_external_methods.py'
    sources = sorted((galahad/'src/nerve_awim/external_methods').glob('*.py')) + [script, galahad/'configs/external-methods-protected.json']
    binding = {'source_sha256': {str(p.relative_to(galahad)): sha256(p.read_bytes()).hexdigest() for p in sources},
               'receipt_sha256': sha256(Path(receipt).read_bytes()).hexdigest(),
               'development_sha256': sha256(Path(development).read_bytes()).hexdigest(),
               'holdout_authorized': False, 'promotion_authorized': False}
    encoded = json.dumps(binding, sort_keys=True, indent=2) + '\n'
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    registration = state/'external-methods-registration.json'
    if registration.exists():
        if registration.read_text() != encoded: raise ValueError('orchestrator_binding_changed')
    else: registration.write_text(encoded)
    def evaluate(task):
        if any(sha256((galahad/p).read_bytes()).hexdigest() != h for p,h in binding['source_sha256'].items()):
            raise ValueError('evaluator_sources_changed')
        if sha256(Path(receipt).read_bytes()).hexdigest() != binding['receipt_sha256'] or sha256(Path(development).read_bytes()).hexdigest() != binding['development_sha256']:
            raise ValueError('evaluator_inputs_changed')
        result = subprocess.run([sys.executable, str(script), 'audit-v3', '--receipt', str(receipt),
            '--development', str(development), '--output', str(state/'audit')], capture_output=True, text=True, check=True, timeout=180)
        return json.loads(result.stdout)
    spec = importlib.util.spec_from_file_location('external_methods_goal', ROOT/'src/nerve_awim/goal_orchestrator.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    goal = module.GoalOrchestrator(state, handlers={'external-methods-audit': evaluate},
        validators={'external-methods-audit': lambda r: (r.get('status') == 'development_audit_complete'
            and r.get('new_model_calls') == 0 and r.get('holdout_accessed') is False and r.get('promotion_authorized') is False)})
    identity = 'external-methods-staged:' + sha256(encoded.encode()).hexdigest()
    if goal.path.exists():
        if goal.inspect()['goal_id'] != identity: raise ValueError('goal_identity_changed')
    else:
        goal.create(goal_id=identity, target='Complete retrospective external-methods development audit; no promotion',
                    tasks=[{'id': 'audit', 'handler': 'external-methods-audit'}])
    return goal.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('galahad', 'state', 'receipt', 'development'): parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    result = run(args.galahad, args.state, args.receipt, args.development)
    print(json.dumps(result, sort_keys=True, indent=2))
    if result['status'] != 'complete': raise SystemExit(1)
