"""Offline CCE commissioning demo. Never installs models or calls a provider."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from time import perf_counter

from .agent_learning_v12 import RegisteredStrategy
from .cue_engine import Cue, ModelProfile, CueRegistry, CueRouter, inspect_tokenization
from .cue_evaluation import DatasetManifest, ModelParity, EvaluationReport
from .cue_experiment import ExperimentTask, ProviderReceipt, JudgeReceipt, run_experiment
from .cue_learning import GovernedCueCoordinator
from .governed_learning_v20 import GovernedLearning, LearningAuthority
from .memory_v18 import MemoryAuthority, TrustedMemoryLedger


def demo():
    authority = LearningAuthority()
    actors = {r: authority.issue('cce-demo', 'research', r)
              for r in ('trainer', 'evaluator', 'operator', 'runtime', 'auditor')}
    profile = ModelProfile('fixture', 'arithmetic', 'v1', 'utf8-fixture', 'v1',
                           ('instruction',), 'arithmetic-fixture-v1')
    cue = Cue('check-arithmetic', 1, 'Check each arithmetic operation.', 'instruction',
              profile.key, ('research',), 'offline-demo-not-a-published-model')
    manifest = DatasetManifest(('discovery-1',), ('selection-1',),
                               tuple('holdout-'+str(i) for i in range(30)))
    config = ModelParity(profile.provider, profile.model, profile.revision,
        profile.tokenizer, profile.tokenizer_revision, sha256(b'arithmetic-fixture-v1').hexdigest(),
        sha256(b'no-sampling').hexdigest(), 0., 128, sha256(b'no-extra-context').hexdigest(), profile.key)
    tasks = tuple(ExperimentTask(t, f'add {i} {i+1}', str(2*i+1)) for i, t in enumerate(manifest.holdout))
    def fixture(request):
        _, left, right = request.instruction.split()
        return ProviderReceipt(str(int(left) + int(right)), 1., request.model, 0.,
            request.task_id + '-' + request.arm, synthetic=True,
            cue_digest=request.cue_digest, arm=request.arm)
    with tempfile.TemporaryDirectory(prefix='nerve-cce-demo-') as folder:
        engine = GovernedLearning(Path(folder) / 'learning.sqlite', authority=authority,
            strategies=[RegisteredStrategy('baseline', 'research', lambda value: value)],
            judge=lambda task, value: True, contract_revision='cce-demo-v1',
            baseline_routes={'research': 'baseline'})
        engine.bootstrap(actors['operator'])
        coordinator = GovernedCueCoordinator(engine, enabled=True)
        candidate = coordinator.propose(actors['trainer'], cue, profile, 'research', manifest,
            generator_id='fixture-generator', model_config=config)
        report = run_experiment(candidate, cue, manifest, tasks, config, fixture,
            lambda *, output, expected: JudgeReceipt(output == expected, True),
            max_calls=60, max_cost_usd=.06, per_call_cost_cap_usd=.001, permission_granted=True)
        evaluation = coordinator.evaluate(actors['evaluator'], candidate, report.pairs,
                                         evaluator_id='deterministic-judge')
        selection = coordinator.select(actors['runtime'], profile, 'research', permission_granted=True)
        memory_authority = MemoryAuthority()
        memory_actor = memory_authority.issue('cce-demo', 'research')
        ledger = TrustedMemoryLedger(engine.path, memory_authority)
        memory_id = coordinator.export_memory(actors['auditor'], candidate, ledger, memory_actor)
        # Timing the decision mechanism only, not inference or live model speed.
        router = CueRouter(CueRegistry())
        samples = []
        for _ in range(1000):
            start = perf_counter()
            router.select(profile, 'research')
            samples.append((perf_counter() - start) * 1000)
        samples.sort()
        return {'schema': 'nerve-cce-demo-v1', 'scope': 'offline synthetic commissioning only',
            'provider_calls': 0, 'fixture_calls': 60, 'paper_reproduced': False,
            'live_deployment': False, 'evaluation': evaluation,
            'selection': selection.telemetry(), 'memory_status': ledger.status(memory_actor, memory_id).status,
            'tokenization': inspect_tokenization(cue, profile, lambda text: list(text.encode())),
            'router_timing': {'iterations': 1000, 'median_ms': samples[500], 'p95_ms': samples[949],
                              'scope': 'local disabled router only; no provider latency or improvement claim'},
            'source_sha256': {p.name: sha256(p.read_bytes()).hexdigest()
                              for p in sorted(Path(__file__).parent.glob('cue_*.py'))}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('demo', help='Run a bounded offline study that cannot activate a cue')
    run.add_argument('--output', type=Path)
    inspect = sub.add_parser('inspect-report', help='Validate a scored report and print aggregate metrics')
    inspect.add_argument('path', type=Path)
    dataset = sub.add_parser('inspect-dataset', help='Validate a frozen local dataset without exposing answers')
    dataset.add_argument('path', type=Path)
    for command in ('local-inspect', 'local-smoke'):
        local = sub.add_parser(command, help='Inspect or smoke-test an installed, digest-bound local Ollama model')
        local.add_argument('--model', required=True)
        local.add_argument('--digest', required=True, help='Expected installed manifest SHA256')
        local.add_argument('--output', type=Path)
        if command == 'local-smoke':
            local.add_argument('--allow-local-inference', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'demo':
        result = demo()
    elif args.command == 'inspect-dataset':
        from .cue_dataset import load_dataset
        result = load_dataset(args.path).telemetry()
    elif args.command in ('local-inspect', 'local-smoke'):
        from .cue_ollama import OllamaCueAdapter
        from .cue_local import run_local_smoke
        execute = args.command == 'local-smoke'
        if execute and not args.allow_local_inference:
            parser.error('local-smoke requires --allow-local-inference for four bounded local calls')
        adapter = OllamaCueAdapter(args.model, args.digest, enabled=execute, permission_granted=execute,
            max_calls=4, max_output_tokens=32)
        result = run_local_smoke(adapter) if execute else adapter.inspect()
    else:
        if args.path.stat().st_size > 10000000:
            parser.error('report exceeds 10 MB')
        report = EvaluationReport.from_dict(json.loads(args.path.read_text()))
        result = {'digest': report.digest, 'metrics': report.metrics, 'promotion_authorized': False}
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n'
    if getattr(args, 'output', None):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
        print(str(args.output))
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
