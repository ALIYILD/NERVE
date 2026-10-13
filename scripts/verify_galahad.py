#!/usr/bin/env python3
"""Bounded local verification entrypoint; never installs or deploys anything."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'cpu': ('test_memory_gateway.py', 'test_galahad_provider.py',
            'test_memory_gateway_evaluation.py', 'test_memory_service.py',
            'test_memory_lifecycle.py', 'test_memory_holdout.py', 'test_memory_runtime.py',
            'test_memory_agent_wiring.py', 'test_memory_gateway_mcp.py', 'test_memory_policy.py',
                 'test_memory_inference.py', 'test_memory_operations.py', 'test_galahad_gpu_smoke.py', 'test_memory_learning.py', 'test_memory_learning_demo.py', 'test_memory_automation.py', 'test_memory_autoadapt_demo.py', 'test_memory_exploration.py', 'test_memory_self_study.py', 'test_memory_decay.py', 'test_policy_research_loop.py', 'test_discounted_memory.py', 'test_discount_research.py', 'test_online_adaptation_study.py', 'test_configurable_online_trial.py', 'test_online_optimisation.py', 'test_research_orchestrator.py', 'test_worldcore_study.py', 'test_recovery_adaptation.py', 'test_recovery_adaptation_study.py', 'test_adaptation_followup.py', 'test_consistent_dynamics.py', 'test_dynamics_factorial_episode.py', 'test_dynamics_factorial_study.py', 'test_identification_diagnostic.py', 'test_research_supervisor.py', 'test_evidence_window_dynamics.py', 'test_evidence_window_episode.py', 'test_evidence_window_study.py', 'test_research_outcome_memory.py', 'test_research_followup.py', 'test_worldcore_diagnostics.py', 'test_local_memory_benchmark.py', 'test_cpu_memory_benchmark.py', 'test_memory_grounding.py', 'test_memory_grounding_v2.py', 'test_grounded_registry_benchmark.py', 'test_grounded_registry_benchmark_v2.py', 'test_research_campaign.py', 'test_restart_learning_study.py', 'test_inference_diagnostics.py', 'test_inference_cpu_profile.py', 'test_local_memory_readiness.py'),
    'security': ('test_memory_gateway.py', 'test_memory_service.py', 'test_galahad_provider.py',
                 'test_memory_lifecycle.py', 'test_memory_holdout.py', 'test_memory_runtime.py',
                 'test_memory_agent_wiring.py', 'test_memory_gateway_mcp.py', 'test_memory_policy.py',
                 'test_memory_inference.py', 'test_memory_operations.py', 'test_galahad_gpu_smoke.py', 'test_memory_learning.py', 'test_memory_learning_demo.py', 'test_memory_automation.py', 'test_memory_autoadapt_demo.py', 'test_memory_exploration.py', 'test_memory_self_study.py', 'test_memory_decay.py', 'test_policy_research_loop.py', 'test_discounted_memory.py', 'test_discount_research.py', 'test_online_adaptation_study.py', 'test_configurable_online_trial.py', 'test_online_optimisation.py', 'test_research_orchestrator.py', 'test_worldcore_study.py', 'test_recovery_adaptation.py', 'test_recovery_adaptation_study.py', 'test_adaptation_followup.py', 'test_consistent_dynamics.py', 'test_dynamics_factorial_episode.py', 'test_dynamics_factorial_study.py', 'test_identification_diagnostic.py', 'test_research_supervisor.py', 'test_evidence_window_dynamics.py', 'test_evidence_window_episode.py', 'test_evidence_window_study.py', 'test_research_outcome_memory.py', 'test_research_followup.py', 'test_worldcore_diagnostics.py', 'test_local_memory_benchmark.py', 'test_cpu_memory_benchmark.py', 'test_memory_grounding.py', 'test_memory_grounding_v2.py', 'test_grounded_registry_benchmark.py', 'test_grounded_registry_benchmark_v2.py', 'test_research_campaign.py', 'test_restart_learning_study.py', 'test_inference_diagnostics.py', 'test_inference_cpu_profile.py', 'test_local_memory_readiness.py'),
    'faults': ('test_memory_gateway.py', 'test_galahad_provider.py', 'test_memory_lifecycle.py', 'test_memory_policy.py', 'test_memory_operations.py'),
    'api': ('test_memory_service.py', 'test_memory_runtime.py', 'test_memory_inference.py', 'test_inference_diagnostics.py', 'test_inference_cpu_profile.py'),
    'baseline': ('test*.py',),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gate', choices=tuple(GROUPS) + ('readiness',))
    parser.add_argument('--evidence', nargs='*', default=[])
    args = parser.parse_args()
    if args.gate == 'readiness':
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        return subprocess.run([sys.executable, str(ROOT / 'scripts/memory_operations.py'),
                               'readiness', '--evidence', *args.evidence],
                              cwd=ROOT, env=env, timeout=30).returncode
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    failed = False
    for pattern in GROUPS[args.gate]:
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                 '-p', pattern, '-v'], cwd=ROOT, env=env, timeout=300)
        failed = failed or result.returncode != 0
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
