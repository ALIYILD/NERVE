"""Real-runner artifact transport check for the bounded retrieval experiment.

This harness only operates on synthetic research data. It is not the scheduled
checkpoint source and never promotes its CI artifacts to scheduled history.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from nerve_awim.recursive_evolution_v19 import SyntheticMemoryObjective
from nerve_awim.research_checkpoint_v19 import load_checkpoint

ROOT = Path(__file__).resolve().parents[1]


def _experiment(directory, *, resume=None, seed):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(ROOT / 'scripts/recursive_research_v19.py'),
               '--checkpoint-out', str(directory / 'evolution.json'),
               '--seed', str(seed), '--generations', '6']
    if resume is not None:
        command.extend(['--resume', str(resume)])
    process = subprocess.run(command, cwd=ROOT, check=True, capture_output=True,
                             text=True, timeout=60,
                             env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')})
    report = json.loads(process.stdout)
    (directory / 'report.json').write_text(process.stdout, encoding='utf-8')
    return report


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def seed(directory):
    directory = Path(directory).resolve()
    report = _experiment(directory, seed=1)
    _require(report['completed_runs'] == 1 and not report['resumed_from_checkpoint'],
             'seed must start with a fresh research history')
    _require(report['remaining_candidates'] > 0, 'seed must leave new work for resume')
    state = load_checkpoint(directory / 'evolution.json')
    _require(state.completed_runs == 1, 'seed checkpoint was not written')
    digest = sha256((directory / 'evolution.json').read_bytes()).hexdigest()
    return {'checkpoint_sha256': digest, 'known_population_size': len(state.population),
            'completed_runs': 1}


def verify(input_directory, output_directory, expected_sha256):
    source = Path(input_directory).resolve()
    destination = Path(output_directory).resolve()
    _require(source != destination, 'verification must preserve the downloaded evidence')
    _require(re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is not None,
             'a producer checkpoint digest is required')
    checkpoint = source / 'evolution.json'
    # A missing artifact is an error, never permission to start from zero.
    digest = sha256(checkpoint.read_bytes()).hexdigest()
    _require(digest == expected_sha256, 'downloaded checkpoint differs from producer')
    prior = load_checkpoint(checkpoint)
    _require(prior.completed_runs == 1 and prior.population and prior.reset_reason is None,
             'downloaded checkpoint is not the expected compatible seed state')
    report = _experiment(destination, resume=checkpoint, seed=2)
    _require(report['resumed_from_checkpoint'], 'second runner did not resume')
    _require(report['checkpoint_reset_reason'] is None, 'unexpected evaluator reset')
    _require(report['completed_runs'] == 2, 'run history was not retained')
    _require(report['baseline'] == {
        'token_weight': prior.selected.token_weight,
        'trigram_weight': prior.selected.trigram_weight,
    }, 'resumed search did not start from the previous selected recipe')
    after = load_checkpoint(destination / 'evolution.json')
    _require(set(prior.population) < set(after.population), 'archive did not grow')
    new_count = len(after.population) - len(prior.population)
    _require(report['candidates_evaluated'] == new_count,
             'previous candidates were counted again')
    _require(after.cumulative_candidates == prior.cumulative_candidates + new_count,
             'cumulative evaluation count was not retained')
    objective = SyntheticMemoryObjective()
    try:
        fresh = objective.evaluate(prior.selected, 'validation')
    finally:
        objective.close()
    _require(report['baseline_validation']['accuracy'] == fresh.accuracy,
             'resumed baseline was not freshly evaluated')
    _require(report['report_only_holdout']['cross_tenant_leaks'] == 0,
             'resumed holdout scope check failed')
    _require(sha256(checkpoint.read_bytes()).hexdigest() == digest,
             'verification modified the downloaded checkpoint')
    evidence = {
        'status': 'artifact_resume_verified',
        'checkpoint_sha256': digest,
        'evaluator_fingerprint': report['evaluator_fingerprint'],
        'resumed_from_checkpoint': True,
        'completed_runs': report['completed_runs'],
        'population_before': len(prior.population),
        'population_after': len(after.population),
        'new_candidates_evaluated': new_count,
        'cumulative_candidates': after.cumulative_candidates,
        'remaining_candidates': report['remaining_candidates'],
        'cross_tenant_leaks': report['report_only_holdout']['cross_tenant_leaks'],
        'scope': 'CI artifact transfer between jobs; not scheduled-run discovery',
    }
    (destination / 'verification.json').write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('seed')
    start.add_argument('--directory', required=True)
    resume = commands.add_parser('verify')
    resume.add_argument('--input-directory', required=True)
    resume.add_argument('--output-directory', required=True)
    resume.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'seed':
        result = seed(args.directory)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as handle:
                handle.write('checkpoint-sha256=' + result['checkpoint_sha256'] + '\n')
    else:
        result = verify(args.input_directory, args.output_directory, args.expected_sha256)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
