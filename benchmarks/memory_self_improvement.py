"""Preregistered CPU self-study of NERVE's current adaptive-memory policy.

The public synthetic holdout is reproducible, not externally sealed. No candidate
is activated and no model weights are trained. Run from repo with PYTHONPATH=src.
"""
import argparse
import json
import platform
from time import perf_counter
from pathlib import Path

from nerve_awim.memory_gateway.self_study import run_self_study
from nerve_awim.study_statistics_v16 import summarize_pairs


def run():
    started = perf_counter()
    result = run_self_study()
    pairs = [{'seed': row['seed'], 'format': 'json_email', 'task_id': row['task_id'],
              'no_memory': row['baseline_success'], 'with_memory': row['candidate_success'],
              'no_memory_error': row['baseline_error'], 'with_memory_error': row['candidate_error']}
             for row in result['paired_rows']]
    # Reuse the existing paired statistics engine; its legacy field names are
    # mapped here to CURRENT adaptive baseline and selected adaptive candidate.
    result['paired_statistics'] = summarize_pairs(pairs)
    result['statistics_arm_mapping'] = {'no_memory': 'current adaptive baseline (window3/relevance)',
                                        'with_memory': 'validation-selected candidate'}
    result['environment'] = {'python': platform.python_version(), 'platform': platform.platform()}
    result['total_wall_seconds'] = perf_counter() - started
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = run()
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n'
    if args.output:
        # An existing experiment report is never silently overwritten.
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    print(text, end='')


if __name__ == '__main__':
    main()
