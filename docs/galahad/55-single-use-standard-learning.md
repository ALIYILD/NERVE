# Single-use evidence for the standard estimator

This cycle fixes an independently reproduced learning-accounting defect through
an opt-in versioned adapter. The existing standard estimator revisits historical
sensor pairs on every ingestion without recording which pairs already updated
the gain. Repeated identical evidence therefore causes additional EMA updates.

With gain 0.27, learning rate 0.5, retention 0.82, two positive unit actions and
velocity observations 0.1 and 0.3, the first usable pair produces gain 0.244.
Replaying the same second observation three times changes the legacy gain to
0.231, 0.2245 and 0.22125, despite providing no new transition evidence.

## Correction boundary

The new standard-gain hook retains the original EMA arithmetic and sample bounds,
but each usable transition can update the model only once within an epoch.
Invalid or incomplete evidence does not consume the transition. Delayed missing
pairs can become usable later. A later correction to an already consumed pair can
still correct the existing state filter, but does not count as another gain
training sample. This first-accepted-pair policy is explicit; it is not a general
solution for retracting or revising training data.

EMA remains dependent on the order of accepted evidence. No arbitrary delivery
order invariance is claimed. The existing observation counter still counts sensor
ingestions; this change establishes gain-update idempotence, not complete sensor
pipeline idempotence.

The retained transition set has a per-epoch budget. Exhaustion retains the current
gain rather than learning from more samples. Existing authorized recovery creates
a new local transition epoch and clears consumed local identifiers while retaining
the learned gain. Old global observations cannot masquerade as observations in
the new epoch. The adapter preserves the existing recovery authorization gates.

Existing versioned modules and source-pinned studies remain unchanged. The
correction is opt-in and does not establish better control performance, neural
weight training, production authentication or clinical readiness.

## Executed evidence

The [actual development artifact](evidence/single-use-learning-v1.json) records
three duplicate replays, a revised observation, delayed-pair acceptance, delivery
order dependence and two runtime recovery epochs. Its SHA-256 is
`873dac218d134f278a0a4d8660aba18b3e6ad356c5b847c1ef829c23eeadba83`.
The [summary](evidence/single-use-learning-summary.json) pins the relevant sources.

The corrected gain remains 0.244 after all three replays. Signed recovery retains
0.244 and clears the local consumed-transition set. New evidence in the second
epoch updates the gain once to 0.231. An invalid recovery identity is rejected.
This is same-process authorized recovery, not persistence across process restart.

The implementation reuses the existing optional gain-update hook,
`SensorOnlyController`, `IdentityBoundRecovery` and `NerveResearchRuntime`.
Host code opts in through `SingleUseStandardController` or
`SingleUseStandardRuntime` from `nerve_awim.single_use_standard`.
No network endpoint or agent promotion permission is added.

Seventeen focused tests and independent review passed. The full regression suite
passed **1,657 tests in 162.613 seconds**, with zero failures or errors. See the
[validation receipt](evidence/single-use-learning-validation.json). The environment
is the existing local Python virtual environment on macOS; these are CPU checks,
not GPU integration tests.

## Independent reproduction

From the repository root, choose a fresh output path; the demo refuses overwrite:

```sh
PYTHONPATH=src .venv/bin/python scripts/demo_single_use_learning.py --output /private/tmp/nerve-single-use-learning-reproduction.json
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_single_use*.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

These fixtures use synthetic observations and host identities. They require no GPU,
Galahad licence, model API or real patient data. No new registered evaluation
streams were consumed. GPU restoration and clinical deployment remain unverified.

## Next experiment boundary

Before comparing control performance, independently reconstruct learning
applications from sensor/action traces. The existing recovery study counter uses
`drift_model.processed`; it would misleadingly count zero updates for the legacy
standard estimator, which has no such model. A matched development comparison
must distinguish total EMA applications from unique evidence and hold filter,
planner, recovery and supervision constant. No performance improvement follows
from the duplicate-consumption correction alone.
