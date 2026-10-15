# Observer replay on recorded training trajectories

The action observer is now evaluated on the completed evidence-gated study's
noisy stationary/drifting training traces. This is a fixed, retrospective
prediction comparison. It runs no new plant episodes, changes no actions, fits no
new parameters, and does not consume validation or holdout outcomes.

`observer_reanalysis.run` verifies the complete source study and predecessor
receipts before analysis. It requires the exact 128-episode training roster,
revalidates each worker trace, and checks source/report hashes around execution.
All eight arms receive the same observer configuration and sensor eligibility
rule. There is no result-dependent selection of arms, seeds or time windows.

## Information and comparison boundaries

The observer receives a projection containing only global step, actual action,
the recorded contemporaneous model gain and accepted noisy sensor measurements.
It assimilates past sensor data before recording the current factual action.
Complete forecast sequences are generated before true velocities are read for
scoring. True position, true gain, true velocity, goal error and prediction error
are excluded from the observer input projection. No model or controller is given
future measurements or held-out answers.

The synthetic replay reporter is trusted only because `run` validated the saved
research receipt; its fixture token is not production authentication. Observer
inputs are factual action history, not generated commands. All action trajectories
remain the originals. Consequently a reduction in shadow prediction error cannot
be represented as improved control performance or an eligible learned policy.

This comparison changes the observer's continuity, recovery handling and
historical-gain replay relative to the legacy forecast. It does not isolate the
causal effect of any one of those changes. Summaries include every arm, regime and
controller/external-supervisor stratum, plus the complete per-step forecasts.
Numerical differences use observer minus legacy error, so negative is lower MAE.
A future prospective control study must give the same observation capabilities to
both frozen and adaptive controls and retain its predeclared acceptance gates.

## Reproduction

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_observer_reanalysis.py -v
PYTHONPATH=src .venv/bin/python scripts/analyze_actual_action_observer.py \
  --study /private/tmp/nerve-evidence-gated-study-v1 \
  --claims /private/tmp/nerve-evidence-gated-study-claims.sqlite \
  --coordinator-directory /private/tmp/nerve-memory-research-v1 \
  --coordinator-journal /private/tmp/nerve-memory-research-claims.sqlite \
  --output /private/tmp/nerve-observer-reanalysis-reproduction.json
.venv/bin/python scripts/verify_galahad.py baseline
```

The output path must be new. It is exclusively reserved before analysis; failure
can leave an empty/partial file, which is not a valid completed receipt. Replaying
this deterministic training analysis does not execute a plant or reopen the
source study's consumed trial claims. Source-pinned historical files remain
unchanged. No GPU KV restoration, model-weight training, clinical workflow or
production deployment is exercised.

## Actual results

The replay completed **128 training trajectories / 10,240 recorded steps** and
reported all **48 fixed arm/regime/action-source summaries**. No plant episodes
were executed. Independent review reconciled every step error and summary,
verified source hashes and the original receipt hash, and found no leakage or
comparator defect.

External-supervisor prediction MAE decreased in all 16 arm/regime strata.
Stationary whole-trajectory MAE decreased for all eight arms. However, drift
controller-only MAE increased for **all eight arms**, and drift whole-trajectory
MAE increased for frozen horizon 1 and both gated horizon-1 arms. The observer is
therefore **not approved as an unconditional replacement** for legacy forecasts.

Selected whole-trajectory comparisons, each over eight training seeds:

| Regime / arm | Legacy MAE | Observer MAE |
|---|---:|---:|
| Stationary frozen h1 | 0.009832772 | 0.003873520 |
| Stationary adaptive consistent h1 | 0.010104579 | 0.004036740 |
| Stationary gated retain h1 | 0.009832772 | 0.003873520 |
| Drift frozen h1 | 0.027228799 | 0.027722416 |
| Drift adaptive consistent h1 | 0.028646391 | 0.026687439 |
| Drift gated retain h1 | 0.026639524 | 0.027632670 |
| Drift gated forget h1 | 0.027071410 | 0.028082825 |

These results support evaluating phase-specific observation use or explicit
recovery handling as a new hypothesis. They do not authorize choosing a routing
rule after inspecting final evaluation data: no such data were opened here, and a
new candidate still needs a frozen protocol and prospective comparison. Goal
errors and actions are unchanged from the rejected source study.

[Every summary and source manifest](evidence/observer-reanalysis-summary.json),
[complete per-step forecasts and errors](evidence/observer-reanalysis-v1.json.gz).

Full regression: **1,540 tests passed in 135.548 seconds**, zero failures/errors.
[Validation record](evidence/observer-reanalysis-validation.json).
