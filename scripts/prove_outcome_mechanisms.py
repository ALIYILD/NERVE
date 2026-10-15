#!/usr/bin/env python3
"""Synthetic mechanism proof. Run only on the allocated Runpod host.

No inference, network, model fitting, production registry or signing capability.
The subprocess phases demonstrate real process restart over persistent state.
"""
import argparse
from hashlib import sha256
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import time

from nerve_awim.agent_learning_v12 import AgentTask, FeedbackAgentCoordinator, RegisteredStrategy
from nerve_awim.evolution_v01 import EvolutionMemory
from nerve_awim.auto_adaptation_goal import build
from nerve_awim.retained_skill_contract import select_retained_skill


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def strategies():
    return [RegisteredStrategy('lowercase', 'synthetic-normalize', lambda value: value.lower()),
            RegisteredStrategy('trim-lowercase', 'synthetic-normalize', lambda value: value.strip().lower())]


def coordinator(database):
    return FeedbackAgentCoordinator(memory=EvolutionMemory(database), agent_id='synthetic-proof',
                                    strategies=strategies(), max_workers=1)


def phase(name, root):
    database = root/'episodes.sqlite'
    if name == 'train':
        agent = coordinator(database)
        before = agent.select('synthetic-normalize')
        # Labels are separate expected fixtures; reward is computed from executed outputs.
        for i in range(8):
            payload, expected = f'  TRAIN-{i}@EXAMPLE.COM  ', f'train-{i}@example.com'
            for strategy in strategies():
                output = strategy.handler(payload)
                agent.feedback(context='synthetic-normalize', strategy_id=strategy.strategy_id,
                               reward=int(output == expected))
        return dict(initial_selection=before, final_selection=agent.select('synthetic-normalize'),
                    recorded_episodes=len(agent.memory.store.rated_history('synthetic-proof', 'synthetic-normalize')),
                    training_strategy_executions=16)
    if name == 'reuse':
        agent = coordinator(database)
        tasks = [AgentTask(f'novel-{i}', 'synthetic-normalize', f' NEW-{i}@EXAMPLE.ORG ') for i in range(8)]
        expected = [f'new-{i}@example.org' for i in range(8)]
        before = len(agent.memory.store.rated_history('synthetic-proof', 'synthetic-normalize'))
        outputs = agent.run(tasks)
        frozen = coordinator(root/'empty-control.sqlite').run(tasks)
        oracle = [strategies()[1].handler(task.payload) for task in tasks]
        after = len(agent.memory.store.rated_history('synthetic-proof', 'synthetic-normalize'))
        return dict(tasks=8, feedback_policy_hits=sum(o.value==e for o,e in zip(outputs,expected)),
                    frozen_no_memory_hits=sum(o.value==e for o,e in zip(frozen,expected)),
                    fixed_best_registered_hits=sum(o==e for o,e in zip(oracle,expected)),
                    executions_per_policy=8, all_used_feedback=all(o.used_feedback for o in outputs),
                    selected_strategy=agent.select('synthetic-normalize')[0],
                    test_did_not_write_feedback=before==after)
    if name == 'adapt-start':
        state = build(root/'adaptation').run(max_ticks=9)
        assert state['status'] == 'active'
        return dict(status=state['status'], checkpoint_sha256=sha256(canonical(state).encode()).hexdigest())
    if name == 'adapt-resume':
        state = build(root/'adaptation').run()
        assert state['status'] == 'complete'
        return dict(status=state['status'], receipt=state['tasks'][-1]['receipt'],
                    state_sha256=sha256(canonical(state).encode()).hexdigest())
    raise ValueError(name)


def retention_denial():
    incumbent = dict(skill_id='synthetic/proof', version='v0', config_hash='0'*64)
    record = dict(skill_id='synthetic/proof', version='v1')  # deliberately unsigned, no fake authority
    result = select_retained_skill(record, incumbent=incumbent, config_bytes=b'fixture', artifact_bytes={},
        manifest_hash='0'*64, model_digest='0'*64,
        verify_gate=lambda *args: False, verify_signature=lambda *args: False)
    assert result['selected'] == incumbent and not result['retained_skill_selected']
    assert not result['production_authorized']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--phase', choices=['train', 'reuse', 'adapt-start', 'adapt-resume'])
    parser.add_argument('--pod-id', default='lg0svvuenxvbno')
    parser.add_argument('--hourly-rate-usd', type=float, default=.59)
    args = parser.parse_args()
    if platform.system() != 'Linux':
        raise SystemExit('Remote Linux execution required; laptop execution refused')
    if args.phase:
        print(canonical(phase(args.phase, args.directory))); return
    root = args.directory
    root.mkdir(parents=True, exist_ok=False)
    gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], text=True).strip()
    if gpu != 'NVIDIA A40':
        raise SystemExit('Expected existing A40 pod; refusing alternate execution host')
    def source_manifest():
        paths = sorted(Path('src').rglob('*.py')) + [Path(__file__)]
        return {str(path):sha256(path.read_bytes()).hexdigest() for path in paths}
    source_before = source_manifest()
    registration = dict(protocol='nerve-synthetic-mechanisms-v1', pod_id=args.pod_id,
        training_items=8, training_strategies=2, novel_items=8, adaptation_protocol='auto-adapt-aba-v1',
        expected_feedback_hits=8, expected_no_memory_hits=0, expected_fixed_best_hits=8,
        expected_adaptive_hits_per_domain=28, expected_tasks_per_domain=36,
        expected_fixed_control_hits=[24,12], expected_switches_per_domain=2,
        additional_evaluation_calls_per_domain=32, expected_reversal_trial_hits=6,
        expected_reversal_trial_tasks=8, model_calls=0,
        source_sha256=source_before)
    (root/'registration.json').write_text(canonical(registration)+'\n')
    start = time.monotonic()
    def child(name):
        output = subprocess.check_output([sys.executable, __file__, '--directory', str(root), '--phase', name], text=True)
        return json.loads(output)
    train = child('train'); reuse = child('reuse')
    partial = child('adapt-start'); final = child('adapt-resume'); replay = child('adapt-resume')
    assert train['recorded_episodes'] == 16 and reuse['feedback_policy_hits'] == 8
    assert reuse['frozen_no_memory_hits'] == 0 and reuse['fixed_best_registered_hits'] == 8
    assert reuse['all_used_feedback'] and reuse['test_did_not_write_feedback']
    assert final == replay
    for result in final['receipt']['domains'].values():
        assert result['adaptive_hits']==28 and result['tasks']==36 and result['switches']==2
        assert sorted(result['fixed_controls'].values())==[12,24]
        assert result['additional_evaluation_calls']==32 and result['rollback_probe']['rollback_verified']
        assert result['rollback_probe']['trial_hits']==6 and result['rollback_probe']['trial_tasks']==8
        assert not result['production_authorized']
    assert source_manifest() == source_before, 'source_changed_during_run'
    wall = time.monotonic()-start
    report = dict(protocol=registration['protocol'], registration_sha256=sha256(canonical(registration).encode()).hexdigest(),
        pod_id=args.pod_id, pod_identity_source='Operator-verified live Runpod API and SSH mapping; pod does not export RUNPOD_POD_ID',
        gpu=gpu, source_unchanged_after_run=True, execution='CPU-only on existing GPU pod; one worker',
        model_digest=None, model_calls=0, model_digest_reason='No model is loaded or invoked by this proof.',
        wall_seconds=wall, allocated_pod_rate_usd_per_hour=args.hourly_rate_usd,
        allocated_cost_estimate_usd=wall/3600*args.hourly_rate_usd,
        cost_note='Shared existing pod wall-time allocation, not incremental invoice cost; rate supplied by operator.',
        feedback_learning=dict(training=train, novel_reuse=reuse), adaptation_start=partial,
        adaptation=final, byte_identical_new_process_restart=final==replay,
        unsigned_retention=retention_denial(), holdout_accessed=False, production_authorized=False,
        claims=['Trusted outcome-derived rewards change persisted registered-strategy selection.',
                'Selection is reused on novel synthetic tasks after a fresh process starts.',
                'A deterministic bounded controller detects synthetic drift, selects existing strategies, and rolls back failed canaries.'],
        nonclaims=['No new strategy invented; no model weights learned; no autonomous research.',
                   'No real-domain efficacy or generalization; no equal-total-compute superiority.',
                   'No signed retained skill, deployment, real registry mutation or holdout result.'])
    (root/'aggregate-report.json').write_text(canonical(report)+'\n')
    print(canonical(report))


if __name__ == '__main__':
    main()
