# Registered evidence-gated adaptation study

This study evaluates the opt-in evidence gate against matched controls on fresh
synthetic streams. It preserves the original safety, correctness and performance
acceptance rules. It does not tune the estimator after observing these streams.

Training seeds 41001–41008 compare eight arms in both stationary and drifting
regimes: frozen gain at horizon 1/3, existing adaptive consistent dynamics at
horizon 1/3, and evidence-gated adaptation at horizon 1/3 with retained/forgotten
observation windows on authorized recovery. Every arm receives the same exogenous
schedule at the same seed. Fixed candidate parameters are window 4, minimum 4,
error multiplier 3, minimum shift 0.03. Candidates see only sensor/action history.

Each candidate must pass unchanged recovery-study gates against frozen horizon 1,
its matched frozen horizon and its matched adaptive-consistent horizon. Gates
include no recorded envelope violation, no per-regime regression in active steps,
external supervision, prediction error or goal error, actual consumed learning
evidence, and strict summed goal gain. Parameter changes are reported separately
from consumed observations; neither alone establishes improved outcomes.

Training freezes one winner by summed goal gain versus frozen horizon 1 with
lexical tie-breaking. Only that winner and its unique matched controls enter
validation seeds 42001–42008. Only a validation pass can consume final seeds
43001–43016, once. Failure stops without trying the runner-up. Maximum 320 episodes
and 25,600 physical steps, child timeout 30 seconds and episode-execution budget
1,200 seconds. Setup, predecessor verification and final receipt reconciliation
are outside that execution-time budget.

The worker reconstructs the complete gated model from noisy timestamped sensor
pairs and executed actions. It checks observation windows, deduplication, variance,
thresholds, gain-change count and recovery resets at every step. Existing physical
trace validation remains independent of that reconstruction. Deeper-planning
sequence counts are actual enumeration counts, not assumed work savings.

The completed memory-guided coordinator is the required predecessor. The new
study verifies its receipt and journal read-only, revalidates the source study and
approved memory through the planner, and recomputes the diagnostic. It does not
invoke the coordinator's mutating run path. Shared dataset consumption, source
pins, pre-dispatch claims and frozen selection protect experimental integrity.
No candidate is automatically deployed or granted clinical decision authority.

## Reproduction

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_evidence_gated_episode.py -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_evidence_gated_study.py -v
PYTHONPATH=src .venv/bin/python scripts/run_evidence_gated_study.py \
  --directory /private/tmp/nerve-evidence-gated-study-v1 \
  --claims /private/tmp/nerve-evidence-gated-study-claims.sqlite \
  --coordinator-directory /private/tmp/nerve-memory-research-v1 \
  --coordinator-journal /private/tmp/nerve-memory-research-claims.sqlite
.venv/bin/python scripts/verify_galahad.py baseline
```

The run command is one-use. After completion, independently validate its receipt
without rerunning episodes:

```python
from nerve_awim.memory_gateway.evidence_gated_study import validate_receipt
validate_receipt('/private/tmp/nerve-evidence-gated-study-v1',
                 '/private/tmp/nerve-evidence-gated-study-claims.sqlite',
                 '/private/tmp/nerve-memory-research-v1',
                 '/private/tmp/nerve-memory-research-claims.sqlite')
```

Preserve shared claims; another directory is not permission to rerun the same
dataset. Unit tests use isolated protocol fixtures; worker development checks use
seed 8 outside the registered streams. Full trace validation proves consistency
with the registered implementation, not independent mathematical optimality or
clinical safety. All data are synthetic. No Galahad GPU, encrypted cache restore,
commercial licence, neural-weight training or clinical deployment is exercised.

## Actual result: retain baseline

The registered CPU run completed all **128 training episodes / 10,240 steps**.
It recorded 1,378 accepted fitting observations across adaptive arms, **39 actual
candidate gain changes**, and zero recorded envelope violations. No candidate
passed every comparator. Selection was frozen empty, and **validation and holdout
were not executed**. No model or controller was promoted.

Each row below is the mean across eight training seeds in the drift regime:

| Horizon-1 arm | Goal error | Prediction error |
|---|---:|---:|
| Frozen gain | 0.161360264 | 0.027228799 |
| Existing adaptive consistent | 0.212391552 | 0.028646391 |
| Gated retain | 0.164659258 | 0.026639524 |
| Gated forget | 0.164849185 | 0.027071410 |

Both gated horizon-1 arms passed unchanged gates against the existing adaptive
control, including per-regime prediction and goal non-regression. However, their
drift goal errors were worse than frozen gain by 0.003298995 and 0.003488921,
respectively. Stationary goal/prediction metrics for both gated horizon-1 arms
matched frozen gain exactly. The gate therefore addressed the measured stationary
noise regression in this training sample, but did not establish an eligible
improvement over the stronger baseline. Horizon-3 candidates also failed.
Training comparisons are not final or generalization results.

Actual candidate gain changes across 16 episodes per arm were retain-h1 8,
forget-h1 8, retain-h3 12 and forget-h3 11. Learning-evidence consumption is kept
separate from these counts. Evidence that an estimate changed does not prove the
change improved the control objective.

Environment: macOS 26.5.2 x86-64, Python 3.10.0, CPU synthetic plant. Recorded
aggregate episode elapsed times for 16 episodes each were frozen-h1 0.438566 s,
adaptive-consistent-h1 0.448056 s, gated-retain-h1 0.458190 s and gated-forget-h1
0.457169 s. Timing includes instrumentation, excludes child startup/coordinator
validation, and occurred while the regression suite was also running. It is
reported as observed work, not a speedup, isolated benchmark or deployment-cost
estimate. No GPU or energy measurement was made.

[Full recorded traces](evidence/evidence-gated-study-v1.json.gz) and
[summary, comparisons and source manifest](evidence/evidence-gated-study-summary.json).

Independent review verified the complete recorded receipt without running new
episodes. Full regression: **1,509 tests passed in 114.927 seconds**, zero
failures/errors. [Validation record](evidence/evidence-gated-study-validation.json).
