"""Run the preregistered v3 discounted-evidence experiment once."""
import argparse
import json
import platform
from pathlib import Path
from time import perf_counter
from nerve_awim.memory_gateway.discount_research import run_discount_research
from nerve_awim.study_statistics_v16 import summarize_pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.database.resolve():
        parser.error('report and experiment database must be separate')
    # Reserve report before consuming experiment, refusing overwrite.
    with args.output.open('x', encoding='utf-8') as stream:
        started = perf_counter()
        report = run_discount_research(args.database, args.run_id)
        report['environment'] = {'python':platform.python_version(),'platform':platform.platform()}
        report['total_wall_seconds'] = perf_counter() - started
        pairs = []
        for chosen, baseline in zip(report['holdout']['selected'], report['holdout']['baseline']):
            for index,(a,b) in enumerate(zip(chosen['probe_outcomes'],baseline['probe_outcomes'])):
                pairs.append({'seed':chosen['seed'],'format':'json_email',
                    'task_id':f"{chosen['seed']}-{chosen['scenario']}-{index}",
                    'with_memory':a,'no_memory':b,'with_memory_error':False,'no_memory_error':False})
        report['paired_statistics'] = summarize_pairs(pairs)
        report['statistics_arm_mapping'] = {'no_memory':'current baseline','with_memory':'loop-selected candidate'}
        report['holdout_summary'] = {name: {
            'probe_hits': sum(row['probe_hits'] for row in rows),
            'probe_executions': sum(row['probe_executions'] for row in rows),
            'feedback_hits': sum(sum(row['feedback_outcomes']) for row in rows),
            'feedback_executions': sum(row['feedback_executions'] for row in rows),
        } for name, rows in report['holdout'].items()}
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    print(json.dumps({key:report[key] for key in ('selected','recommendation','stop_reason','trial_calls','tool_executions','holdout_summary')}))


if __name__ == '__main__':
    main()
