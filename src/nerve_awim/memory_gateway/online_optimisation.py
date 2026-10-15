"""Finite prospective policy selection using the existing research coordinator.

Policies learn from preceding outcomes inside each trial. Selection uses only
training/validation streams; final stream outcomes never change the selection.
Public synthetic research, not independently sealed evaluation or deployment.
"""
from hashlib import sha256
import multiprocessing
from pathlib import Path

from . import online_adaptation_study as online
from . import policy_research_loop as loop


BASELINE = (3, 'relevance', None)
CANDIDATES = (BASELINE,) + tuple((window, 'relevance', discount)
    for window in (3, 5, 10) for discount in (3, 10))
SPLITS = (('train', tuple(range(22001, 22005))),
          ('validation', tuple(range(23001, 23005))),
          ('holdout', tuple(range(24001, 24009))))


def protocol_manifest():
    sources = dict(online.protocol_manifest()['source_sha256'])
    root = Path(__file__).parent
    for name in ('online_optimisation.py', '../../../scripts/optimise_online_memory.py'):
        sources[name] = sha256((root/name).read_bytes()).hexdigest()
    protocol = {
        'version': 'online-policy-optimisation-v1',
        'candidates': [list(c) for c in CANDIDATES], 'baseline': list(BASELINE),
        'candidate_fields': ['window', 'tie_break', 'discount_half_life'],
        'splits': {name: list(seeds) for name, seeds in SPLITS},
        'scenarios': list(online.SCENARIOS),
        'max_generations': 2, 'candidates_per_generation': 4, 'patience': 2,
        'max_trial_calls': 352, 'score_field': 'hits', 'executions_per_trial': 32,
        'max_pipeline_episodes': 11264, 'max_primitive_tool_invocations': 22528,
        'child_timeout_seconds': 60,
        'source_sha256': sources,
        'dataset_sha256': loop._digest([(seed, scenario, online._cases(seed, scenario))
            for _, seeds in SPLITS for seed in seeds for scenario in online.SCENARIOS]),
        'evaluation': '32 test-then-feedback episodes per adaptive trial; fixed controls write no feedback',
        'selection': 'strict validation gain; training total and every validation regime nonregression against baseline and incumbent',
        'holdout': 'selected configuration frozen before final streams; online updates within each stream only; no subsequent tuning',
        'candidate_rationale': 'Slower evidence discount than the overnight candidate; assess retention alongside adaptation without changing the acceptance gate.',
        'public_synthetic_nonsealed': True, 'promotion_authorized': False,
    }
    return {**protocol, 'protocol_sha256': loop._digest(protocol)}


def _check_sources(manifest):
    root = Path(__file__).parent
    current = {name: sha256((root/name).read_bytes()).hexdigest()
               for name in manifest['source_sha256']}
    if current != manifest['source_sha256']:
        raise ValueError('optimisation source drift')


def _child(connection, seed, scenario, config, fixed):
    try:
        row = online._configured_trial(seed, scenario, online.OnlinePolicy(*config), fixed)
        connection.send(('ok', row))
    except BaseException:
        connection.send(('error', None))
    finally:
        connection.close()


def _execute(seed, scenario, config, fixed):
    context = multiprocessing.get_context('spawn')
    reader, writer = context.Pipe(duplex=False)
    child = context.Process(target=_child, args=(writer, seed, scenario, config, fixed))
    try:
        child.start()
        writer.close()
        if not reader.poll(60):
            raise TimeoutError('optimisation trial timeout')
        status, row = reader.recv()
        if status != 'ok':
            raise RuntimeError('optimisation trial failed')
        return row
    finally:
        if child.pid is not None:
            if child.is_alive():
                child.terminate()
            child.join(1)
            if child.is_alive():
                child.kill()
                child.join(1)
        reader.close()
        writer.close()


def _validate(row, seed, scenario, fixed=None, *, config):
    return online._validate_configured(row, seed, scenario, online.OnlinePolicy(*config), fixed)


def run_online_optimisation(database, run_id):
    return _run(database, run_id, _execute)


def _run(database, run_id, executor):
    manifest = protocol_manifest()

    def evaluate(seed, scenario, config, fixed):
        _check_sources(manifest)
        result = executor(seed, scenario, config, fixed)
        _check_sources(manifest)
        return result

    return loop._run(database, run_id, evaluate, manifest=manifest, validator=_validate,
                     final_guard=lambda: _check_sources(manifest))
