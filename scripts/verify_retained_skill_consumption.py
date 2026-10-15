#!/usr/bin/env python3
"""Verify actual signed retention artifacts through the pure NERVE consumer.

No signer or deployment path. The explicit trusted adapter supplies canonical
study verification and an independently authorized public-key verifier.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from nerve_awim.goal_orchestrator import GoalOrchestrator
from nerve_awim.retained_skill_contract import select_retained_skill


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def load(adapter_path, registry):
    spec = importlib.util.spec_from_file_location('trusted_retention_adapter', adapter_path)
    adapter = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = adapter
    spec.loader.exec_module(adapter)
    inputs = adapter.load_selection_inputs(registry)
    required = {'record', 'incumbent', 'config_bytes', 'artifact_bytes', 'manifest_hash',
                'model_digest', 'verify_gate', 'verify_signature'}
    if set(inputs) != required or not callable(inputs['verify_gate']) or not callable(inputs['verify_signature']):
        raise ValueError('exact_trusted_adapter_contract_required')
    return inputs


def select(inputs):
    return select_retained_skill(**inputs)


def altered(inputs):
    return {key: (value if callable(value) else deepcopy(value)) for key, value in inputs.items()}


def run_checks(inputs):
    positive = select(inputs)
    assert positive['retained_skill_selected'] and not positive['production_authorized'], 'real_signed_selection_failed'
    assert positive['selected']['version'] == inputs['record']['version']
    checks = {'actual_signed_artifacts_selected': True}
    def refused(name, changed):
        result = select(changed)
        assert result['retained_skill_selected'] is False, name
        assert result['selected'] == changed['incumbent'], name
        assert result['production_authorized'] is False, name
        checks[name] = True
    for name in ('dev_study', 'holdout_study', 'task_bank_manifest'):
        changed = altered(inputs)
        uri = changed['record']['evidence_bundle'][name]['uri']
        changed['artifact_bytes'][uri] += b'\nTAMPERED'
        refused('tampered_'+name, changed)
    for name, signer in [('unsigned', None), ('empty_signature', {'key_id':inputs['record']['signed_by']['key_id'], 'signature':''}),
                         ('unauthorized_signer', {'key_id':'not-authorized', 'signature':inputs['record']['signed_by']['signature']}),
                         ('invalid_signature', {'key_id':inputs['record']['signed_by']['key_id'], 'signature':'invalid'})]:
        changed = altered(inputs); changed['record']['signed_by'] = signer
        refused(name, changed)
    changed = altered(inputs); changed['config_bytes'] += b'TAMPERED'; refused('config_bytes_changed', changed)
    changed = altered(inputs); changed['model_digest'] = '0'*64; refused('host_model_mismatch', changed)
    changed = altered(inputs); changed['manifest_hash'] = '0'*64; refused('host_bank_mismatch', changed)
    changed = altered(inputs); changed['incumbent']['version'] += '-other'; refused('predecessor_mismatch', changed)
    changed = altered(inputs); changed['record']['version'] += '-modified'; refused('signed_version_changed', changed)
    # Gate rejection is exercised at the consumer boundary; it is not evidence
    # that a fabricated gate callback is the real adapter used by the positive path.
    changed = altered(inputs); changed['verify_gate'] = lambda *args: False; refused('negative_gate_result', changed)
    changed = altered(inputs); changed['verify_signature'] = lambda *args: False; refused('revoked_authority_result', changed)
    return positive, checks


def orchestrate(inputs, directory):
    goal = GoalOrchestrator(directory,
        handlers={'select': lambda context: select(inputs)},
        validators={'select': lambda receipt: receipt['retained_skill_selected'] is True})
    if not goal.path.exists():
        goal.create(goal_id='actual-retained-skill-consumer-v1', target='Select the authorized retained record without activation',
                    tasks=[{'id':'select', 'handler':'select'}])
    state = goal.run()
    assert state['status'] == 'complete'
    return {'status':state['status'], 'receipt':state['tasks'][0]['receipt'],
            'state_sha256':sha256(canonical(state).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--restart-state', type=Path)
    args = parser.parse_args()
    inputs = load(args.adapter.resolve(), args.registry.resolve())
    if args.restart_state:
        print(canonical({'fresh_selection':select(inputs), 'goal':orchestrate(inputs,args.restart_state)}));return
    started = time.monotonic()
    positive, checks = run_checks(inputs)
    with tempfile.TemporaryDirectory(prefix='nerve-retention-consumer-') as state:
        first = orchestrate(inputs, state)
        output = subprocess.check_output([sys.executable, __file__, '--adapter', str(args.adapter.resolve()),
            '--registry', str(args.registry.resolve()), '--restart-state', state], text=True)
        restarted = json.loads(output)
        assert restarted == {'fresh_selection':positive, 'goal':first}, 'process_restart_mismatch'
    checks['fresh_process_reverifies_and_matches'] = True
    report = dict(protocol='actual-retained-skill-consumer-v1', selected=positive,
        checks=checks, checks_passed=len(checks), wall_seconds=time.monotonic()-started,
        record_sha256=sha256(canonical(inputs['record']).encode()).hexdigest(),
        config_sha256=sha256(inputs['config_bytes']).hexdigest(), model_digest=inputs['model_digest'],
        bank_manifest_sha256=inputs['manifest_hash'],
        adapter_sha256=sha256(args.adapter.read_bytes()).hexdigest(),
        consumer_sha256=sha256(Path('src/nerve_awim/retained_skill_contract.py').read_bytes()).hexdigest(),
        artifact_sha256={name:sha256(inputs['artifact_bytes'][inputs['record']['evidence_bundle'][name]['uri']]).hexdigest()
                         for name in ('dev_study','holdout_study','task_bank_manifest')},
        source='Actual signed retained record and canonical study artifacts; no fixture signer on positive path.',
        model_calls=0, signing_calls=0, production_authorized=False,
        limitations=['Selection is not runtime activation, new learning, or a new holdout evaluation.',
                    'Public-key authorization and canonical gate replay are provided by the explicit trusted host adapter.',
                    'Negative gate/revocation callbacks test consumer behavior; they do not replace positive-path real verifiers.'])
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(canonical(report)+'\n')
    print(canonical(report))


if __name__ == '__main__':
    main()
