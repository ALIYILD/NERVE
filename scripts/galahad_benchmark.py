"""CPU gateway overhead and bounded research. No inference performance claims."""
import argparse
import json
import platform
import statistics
import time

from nerve_awim.memory_gateway.contracts import MemoryRequest
from nerve_awim.memory_gateway.evaluation import GatewayMemoryObjective, run_gateway_research


def benchmark(samples=30):
    if type(samples) is not int or not 5 <= samples <= 1000:
        raise ValueError('samples must be 5..1000')
    objective = GatewayMemoryObjective()
    try:
        request = MemoryRequest(objective.scope, 'fixture', limit=20)
        arms = {
            'no_memory_dispatch_only': lambda: (),
            'existing_verified_text': lambda: objective.ledger.retrieve(objective.actor,
                context=objective.scope.context, query='fixture', limit=20),
            'gateway_null_kv_prefill': lambda: objective.gateway.retrieve(objective.actor, request).records,
        }
        results = {}
        for name, operation in arms.items():
            timings = []
            for _ in range(samples):
                started = time.perf_counter_ns()
                records = operation()
                timings.append((time.perf_counter_ns() - started) / 1e6)
            ordered = sorted(timings)
            results[name] = {'samples': samples, 'records_per_call': len(records),
                'first_call_ms': timings[0], 'subsequent_median_ms': statistics.median(timings[1:]),
                'p50_ms': statistics.median(timings), 'p95_ms': ordered[int((samples - 1) * .95)]}
        return {
            'environment': {'python': platform.python_version(), 'platform': platform.platform()},
            'methodology': 'Sequential local wall-clock calls; 8 synthetic records; same scope/query/limit. First call is not an OS cold-cache guarantee.',
            'limitations': 'No model inference. No-memory arm measures dispatch only and has no retrieval capability. No speedup, energy or cost claim.',
            'results': results,
            'unsupported': {'ordinary_runtime_prefix_cache': None, 'galahad_restore': None,
                'prefill_ms': None, 'ttft_ms': None, 'gpu_memory_bytes': None, 'gpu_energy_joules': None,
                'measured_cost_usd': None, 'restore_after_restart': None, 'token_counts': None},
            'research': run_gateway_research(),
        }
    finally:
        objective.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.samples), indent=2, sort_keys=True))
