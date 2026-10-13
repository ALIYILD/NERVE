"""Run the frozen online policy-selection experiment once; never deploy."""
import argparse
import json
from pathlib import Path

from nerve_awim.memory_gateway.online_optimisation import run_online_optimisation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    database, output = args.database.resolve(), args.output.resolve()
    if output in {database, *(Path(str(database)+suffix) for suffix in ('-journal', '-wal', '-shm'))}:
        parser.error('output must differ from database and SQLite auxiliary paths')
    with output.open('x') as stream:
        report = run_online_optimisation(database, args.run_id)
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in
        ('selected', 'recommendation', 'trial_calls', 'pipeline_episodes', 'holdout_scenario_deltas')}))


if __name__ == '__main__':
    main()
