"""Execute the fixed, prospective synthetic online adaptation study once."""
import argparse
import json
from pathlib import Path
import platform
from time import perf_counter
from nerve_awim.memory_gateway.online_adaptation_study import run_online_adaptation_study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.database.resolve() == args.output.resolve():
        parser.error('database and output must differ')
    with args.output.open('x', encoding='utf-8') as stream:
        started = perf_counter()
        report = run_online_adaptation_study(args.database, args.run_id)
        report['environment'] = {'python': platform.python_version(), 'platform': platform.platform()}
        report['total_wall_seconds'] = perf_counter()-started
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('recommendation', 'arm_hits', 'scenario_deltas', 'tool_executions')}))


if __name__ == '__main__':
    main()
