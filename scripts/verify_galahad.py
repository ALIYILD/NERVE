#!/usr/bin/env python3
"""Bounded local verification entrypoint; never installs or deploys anything."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import os
import signal

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'cpu': ('test_memory_gateway.py', 'test_galahad_provider.py',
            'test_memory_gateway_evaluation.py', 'test_memory_service.py',
            'test_memory_lifecycle.py', 'test_memory_holdout.py', 'test_memory_runtime.py',
            'test_memory_agent_wiring.py', 'test_memory_gateway_mcp.py', 'test_memory_policy.py',
                 'test_memory_inference.py', 'test_memory_operations.py', 'test_galahad_gpu_smoke.py', 'test_memory_learning.py', 'test_memory_learning_demo.py', 'test_memory_automation.py', 'test_memory_autoadapt_demo.py', 'test_memory_exploration.py', 'test_memory_self_study.py', 'test_memory_decay.py', 'test_policy_research_loop.py', 'test_discounted_memory.py', 'test_discount_research.py', 'test_online_adaptation_study.py', 'test_configurable_online_trial.py', 'test_online_optimisation.py', 'test_research_orchestrator.py', 'test_worldcore_study.py', 'test_recovery_adaptation.py', 'test_recovery_adaptation_study.py', 'test_adaptation_followup.py', 'test_consistent_dynamics.py', 'test_dynamics_factorial_episode.py', 'test_dynamics_factorial_study.py', 'test_identification_diagnostic.py', 'test_research_supervisor.py', 'test_evidence_window_dynamics.py', 'test_evidence_gated_dynamics.py', 'test_recovery_epoch_dynamics.py', 'test_single_use_standard.py', 'test_single_use_learning_demo.py', 'test_standard_learning_audit.py', 'test_standard_learning_demo.py', 'test_standard_learning_diagnostic.py', 'test_prequential_gain.py', 'test_prequential_gain_demo.py', 'test_prequential_timing_diagnostic.py', 'test_prequential_research_coordinator.py', 'test_scientific_measurement_tasks.py', 'test_scientific_model_learning.py', 'test_scientific_interface_tasks.py', 'test_scientific_task_interface.py', 'test_scientific_interface_study.py', 'test_scientific_interface_validation_tasks.py', 'test_scientific_interface_validation.py', 'test_scientific_research_coordinator.py', 'test_scientific_structured_tasks.py', 'test_scientific_structured_inference.py', 'test_scientific_structured_preflight.py', 'test_scientific_task_bank.py', 'test_experience_store.py', 'test_scientific_episode_import.py', 'test_scientific_candidates.py', 'test_scientific_candidate_registration.py', 'test_scientific_negative_evidence.py', 'test_scientific_candidate_screening.py', 'test_scientific_candidate_execution.py', 'test_scientific_candidate_route_audit.py', 'test_scientific_candidate_transport.py', 'test_scientific_candidate_transport_smoke.py', 'test_scientific_candidate_format_study.py', 'test_scientific_format_research_coordinator.py', 'test_experience_store_v2.py', 'test_scientific_format_episode_import.py', 'test_scientific_format_feedback.py', 'test_recovery_epoch_demo.py', 'test_recovery_gain_diagnostic.py', 'test_actual_action_observer.py', 'test_actual_action_observer_demo.py', 'test_observer_reanalysis.py', 'test_phase_forecast.py', 'test_forecast_runtime.py', 'test_online_forecast_demo.py', 'test_forecast_outcome_memory.py', 'test_forecast_research_coordinator.py', 'test_phase_forecast_episode.py', 'test_phase_forecast_study.py', 'test_prediction_error_audit.py', 'test_evidence_window_episode.py', 'test_evidence_window_study.py', 'test_evidence_gated_episode.py', 'test_evidence_gated_study.py', 'test_research_outcome_memory.py', 'test_research_memory_planner.py', 'test_evidence_rejection_diagnostic.py', 'test_memory_research_coordinator.py', 'test_research_followup.py', 'test_worldcore_diagnostics.py', 'test_local_memory_benchmark.py', 'test_cpu_memory_benchmark.py', 'test_memory_grounding.py', 'test_memory_grounding_v2.py', 'test_grounded_registry_benchmark.py', 'test_grounded_registry_benchmark_v2.py', 'test_research_campaign.py', 'test_restart_learning_study.py', 'test_inference_diagnostics.py', 'test_inference_cpu_profile.py', 'test_local_memory_readiness.py'),
    'security': ('test_memory_gateway.py', 'test_memory_service.py', 'test_galahad_provider.py',
                 'test_memory_lifecycle.py', 'test_memory_holdout.py', 'test_memory_runtime.py',
                 'test_memory_agent_wiring.py', 'test_memory_gateway_mcp.py', 'test_memory_policy.py',
                 'test_memory_inference.py', 'test_memory_operations.py', 'test_galahad_gpu_smoke.py', 'test_memory_learning.py', 'test_memory_learning_demo.py', 'test_memory_automation.py', 'test_memory_autoadapt_demo.py', 'test_memory_exploration.py', 'test_memory_self_study.py', 'test_memory_decay.py', 'test_policy_research_loop.py', 'test_discounted_memory.py', 'test_discount_research.py', 'test_online_adaptation_study.py', 'test_configurable_online_trial.py', 'test_online_optimisation.py', 'test_research_orchestrator.py', 'test_worldcore_study.py', 'test_recovery_adaptation.py', 'test_recovery_adaptation_study.py', 'test_adaptation_followup.py', 'test_consistent_dynamics.py', 'test_dynamics_factorial_episode.py', 'test_dynamics_factorial_study.py', 'test_identification_diagnostic.py', 'test_research_supervisor.py', 'test_evidence_window_dynamics.py', 'test_evidence_gated_dynamics.py', 'test_recovery_epoch_dynamics.py', 'test_single_use_standard.py', 'test_single_use_learning_demo.py', 'test_standard_learning_audit.py', 'test_standard_learning_demo.py', 'test_standard_learning_diagnostic.py', 'test_prequential_gain.py', 'test_prequential_gain_demo.py', 'test_prequential_timing_diagnostic.py', 'test_prequential_research_coordinator.py', 'test_scientific_measurement_tasks.py', 'test_scientific_model_learning.py', 'test_scientific_interface_tasks.py', 'test_scientific_task_interface.py', 'test_scientific_interface_study.py', 'test_scientific_interface_validation_tasks.py', 'test_scientific_interface_validation.py', 'test_scientific_research_coordinator.py', 'test_scientific_structured_tasks.py', 'test_scientific_structured_inference.py', 'test_scientific_structured_preflight.py', 'test_scientific_task_bank.py', 'test_experience_store.py', 'test_scientific_episode_import.py', 'test_scientific_candidates.py', 'test_scientific_candidate_registration.py', 'test_scientific_negative_evidence.py', 'test_scientific_candidate_screening.py', 'test_scientific_candidate_execution.py', 'test_scientific_candidate_route_audit.py', 'test_scientific_candidate_transport.py', 'test_scientific_candidate_transport_smoke.py', 'test_scientific_candidate_format_study.py', 'test_scientific_format_research_coordinator.py', 'test_experience_store_v2.py', 'test_scientific_format_episode_import.py', 'test_scientific_format_feedback.py', 'test_recovery_epoch_demo.py', 'test_recovery_gain_diagnostic.py', 'test_actual_action_observer.py', 'test_actual_action_observer_demo.py', 'test_observer_reanalysis.py', 'test_phase_forecast.py', 'test_forecast_runtime.py', 'test_online_forecast_demo.py', 'test_forecast_outcome_memory.py', 'test_forecast_research_coordinator.py', 'test_phase_forecast_episode.py', 'test_phase_forecast_study.py', 'test_prediction_error_audit.py', 'test_evidence_window_episode.py', 'test_evidence_window_study.py', 'test_evidence_gated_episode.py', 'test_evidence_gated_study.py', 'test_research_outcome_memory.py', 'test_research_memory_planner.py', 'test_evidence_rejection_diagnostic.py', 'test_memory_research_coordinator.py', 'test_research_followup.py', 'test_worldcore_diagnostics.py', 'test_local_memory_benchmark.py', 'test_cpu_memory_benchmark.py', 'test_memory_grounding.py', 'test_memory_grounding_v2.py', 'test_grounded_registry_benchmark.py', 'test_grounded_registry_benchmark_v2.py', 'test_research_campaign.py', 'test_restart_learning_study.py', 'test_inference_diagnostics.py', 'test_inference_cpu_profile.py', 'test_local_memory_readiness.py'),
    'faults': ('test_memory_gateway.py', 'test_galahad_provider.py', 'test_memory_lifecycle.py', 'test_memory_policy.py', 'test_memory_operations.py'),
    'api': ('test_memory_service.py', 'test_memory_runtime.py', 'test_memory_inference.py', 'test_inference_diagnostics.py', 'test_inference_cpu_profile.py'),
    'baseline': ('test*.py',),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gate', choices=tuple(GROUPS) + ('readiness','profile','fast','slow'))
    parser.add_argument('--evidence', nargs='*', default=[])
    parser.add_argument('--timings', help='Required JSON timing report for profile/fast/slow')
    parser.add_argument('--tier-manifest', default=str(ROOT/'tests/suite_tiers.json'))
    parser.add_argument('--timeout-seconds', type=int, default=None,
                        help='Per test process limit, 1..1800 seconds (default 300)')
    args = parser.parse_args()
    if args.timeout_seconds is not None and not 1 <= args.timeout_seconds <= 1800:
        parser.error('--timeout-seconds must be between 1 and 1800')
    if args.gate in ('profile','fast','slow'):
        if not args.timings:parser.error('--timings required for timed gates')
        if args.gate=='profile':default_timeout=1800
        elif args.gate=='fast':default_timeout=180
        else:
            manifest=json.loads(Path(args.tier_manifest).read_text())
            default_timeout=manifest['slow_timeout_seconds']
            if type(default_timeout) is not int or not 1<=default_timeout<=1800:parser.error('invalid measured slow timeout')
        timeout=args.timeout_seconds or default_timeout
        if args.gate=='fast' and timeout>180:parser.error('fast gate deadline cannot exceed 180 seconds')
        env=dict(os.environ,PYTHONPATH=os.pathsep.join((str(ROOT/'src'),str(ROOT))))
        command=[sys.executable,str(ROOT/'scripts/timed_test_runner.py'),args.gate,
                 '--timings',args.timings,'--manifest',args.tier_manifest]
        # A process group also contains multiprocessing/subprocess descendants;
        # timeout terminates the entire gate, avoiding orphaned test workloads.
        process=subprocess.Popen(command,cwd=ROOT,env=env,start_new_session=True)
        try:return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
            print(f'{args.gate} gate exceeded {timeout}s wall deadline',file=sys.stderr)
            return 124
    if args.gate == 'readiness':
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        return subprocess.run([sys.executable, str(ROOT / 'scripts/memory_operations.py'),
                               'readiness', '--evidence', *args.evidence],
                              cwd=ROOT, env=env, timeout=30).returncode
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    failed = False
    for pattern in GROUPS[args.gate]:
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                 '-p', pattern, '-v'], cwd=ROOT, env=env, timeout=args.timeout_seconds or 300)
        failed = failed or result.returncode != 0
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
