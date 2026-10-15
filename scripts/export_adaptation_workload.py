"""Export an explicitly synthetic example of the offline workload contract."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nerve_awim.adaptation_workload import validate
from nerve_awim.auto_adaptation_goal import DOMAINS, dataset


def example(domain):
    value = {'schema': 'nerve-adaptation-workload-v1', 'goal_id': 'synthetic-external-replay',
        'domain': domain, 'scope': domain+'-offline-replay',
        'provenance': {'source_ref': 'NERVE synthetic A-B-A fixture',
                       'labeler_ref': 'deterministic fixture oracle', 'data_kind': 'synthetic'},
        'target': {'min_gain': .1, 'min_monitor_accuracy': 1., 'min_switches': 2, 'max_evaluation_calls': 32},
        'phases': [{split: dataset(domain, phase, split, 8 if split == 'monitor' else 4)
                    for split in ('observe', 'selection', 'retained', 'monitor')} for phase in range(3)]}
    return validate(value)[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', choices=tuple(DOMAINS), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.output.open('x') as stream:
        stream.write(json.dumps(example(args.domain), indent=2)+'\n')
