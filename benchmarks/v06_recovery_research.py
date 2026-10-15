"""Research-only recovery evaluation over existing simulated state transitions."""
from nerve_awim.recovery_v21 import SupervisedWorldCore


def trial(approved):
    model = SupervisedWorldCore(max_missing=2, recovery_samples=2)
    model.miss()
    model.miss()
    suspended = model.decide().action is None
    model.observe_recovery(2, observed_now=2, position=0.1, velocity=0.1)
    model.observe_recovery(3, observed_now=3, position=0.2, velocity=0.2)
    awaiting = model.phase == "awaiting_approval" and model.decide().action is None
    accepted = model.approve_recovery(approved)
    resumed = model.decide().action is not None
    return {'suspended': suspended, 'awaiting': awaiting, 'accepted': accepted, 'resumed': resumed}


def benchmark():
    positive = trial(True)
    negative = trial(False)
    return {'positive': positive, 'negative': negative,
            'passed': positive['suspended'] and positive['awaiting'] and positive['resumed']
            and negative['suspended'] and negative['awaiting'] and not negative['resumed']}


if __name__ == '__main__':
    import json
    report = benchmark()
    print(json.dumps(report, indent=2))
    if not report['passed']:
        raise SystemExit(1)
