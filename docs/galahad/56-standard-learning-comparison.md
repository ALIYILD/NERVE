# Audited standard-learning comparison

This development experiment tests the single-use correction against two matched
controls. Every arm uses the original standard estimator configuration, filter,
planner and signed recovery machinery; the adaptive learning rate is 0.08.
The frozen control uses rate zero. Only the corrected arm deduplicates usable
transition evidence. No existing source-pinned module is modified.

## Measurement boundary

The original episode counter derives updates from an optional drift-model set.
That counter cannot describe legacy standard learning: the standard estimator
has no drift model and revisits eligible historical pairs at each observation.
The independent audit reconstructs those EMA applications from the recorded
sensor readings and controller actions. Total applications and unique transition
evidence are separate quantities. Simulator truth is used only for outcome
scoring, never to reconstruct the learned gain.

Each authorized recovery starts a new local action/observation epoch and retains
gain. The audit must reproduce every pre-observation gain and post-observation
gain, including the final value, across those boundaries.

## Development protocol

The fixed roster is development seed 9, stationary and drift plants, and frozen,
legacy, and single-use arms: six 80-step episodes. These are paired development
fixtures, not independent prospective evaluation. The parent executes each fixed
case in an isolated subprocess with a timeout, validates the original episode
contract and independently audits learning before comparing outcomes.

The corrected arm must not regress goal error, prediction error, violations or
supervision burden against either matched baseline. An aggregate strict goal
improvement is also required to advance. Development failure retains baselines;
success would authorize only a separately registered experiment. Neither outcome
promotes control changes, trains neural weights or authorizes clinical use.

## Actual result

The screen returned `retain_baseline_and_diagnose`. The candidate improved on
legacy learning in both regimes, but failed the stationary prediction-error
comparison against frozen learning. The fixed gates were retained.

| Regime | Arm | Mean goal error | Mean prediction error | EMA applications / unique evidence |
|---|---|---:|---:|---:|
| Stationary | Frozen | 0.143761226 | 0.006637115 | 0 / 0 |
| Stationary | Legacy | 0.143709948 | 0.007563498 | 198 / 12 |
| Stationary | Single-use | 0.141335585 | 0.006863716 | 13 / 13 |
| Drift | Frozen | 0.160138309 | 0.023441317 | 0 / 0 |
| Drift | Legacy | 0.175803464 | 0.031539105 | 168 / 9 |
| Drift | Single-use | 0.160138309 | 0.022385495 | 10 / 10 |

All six episodes had zero defined violations, 65 controller steps, 15 externally
supervised steps and one authorized recovery. Different unique-evidence counts
reflect different action trajectories; equal-information exposure is not claimed.
Frozen has zero learned transitions, not zero observations. Original trace
`learning_updates` remains optional-hook telemetry and is not the audited
application count.

Stationary prediction error regressed by 0.0002266003747074712 versus frozen.
Drift prediction error improved by 0.0010558216427606383 versus frozen, with equal
goal error. Those gains do not cancel the failed stationary gate. No fresh
training, validation or holdout streams were consumed; seed 9 was already a
reused development fixture, and these six cases establish no population result.

The stationary excess prediction error lies entirely in the 65 controller steps:
paired summed error delta 0.018128029976597865, versus zero across the 15
externally supervised steps. Actions differ in nine steps. This descriptive
decomposition localizes the next investigation; it does not isolate a causal
effect of gain estimation from changed control trajectories.

## Evidence and reproduction

The [full compressed artifact](evidence/standard-learning-development-v1.json.gz)
contains all 480 trace steps, reconstructed learning applications and 21 source
pins. The uncompressed SHA-256 is
`b355daa55c950df760ef5bc920fd0a0c3e6bc520c4c2269902a366309cfd6739`.
The [summary](evidence/standard-learning-development-summary.json) contains the
paired gates, counts and metrics. Independent review revalidated every physical
trace, every learning audit, all source pins and the rejection without executing
new episodes.

From the repository root, use a fresh output filename:

```sh
PYTHONPATH=src .venv/bin/python scripts/demo_standard_learning.py --output /private/tmp/nerve-standard-learning-reproduction.json
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_standard_learning*.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

The development driver allows 30 seconds per child and 180 seconds overall.
Reported child elapsed time includes simulation and audit; it is not an inference
latency or speedup benchmark. Seventeen focused tests passed, including actual
isolated-child execution and tampered-evidence rejection. Full regression passed **1,674 tests in 184.023 seconds**, with zero failures or
errors. See the [validation receipt](evidence/standard-learning-development-validation.json).
The environment was Python 3.10.0 on macOS x86-64 in the existing virtual environment.

This is locally executed CPU simulation using synthetic host identities. It adds
an experiment and independent measurement, not automatic controller promotion,
model-weight training, GPU restoration or clinical deployment. The next research
step is diagnosis of the remaining stationary prediction regression before any
fresh registered comparison of a revised candidate.
