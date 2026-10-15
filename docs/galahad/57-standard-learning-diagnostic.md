# Standard-learning prediction diagnosis

This loop diagnoses the rejected six-case development comparison without running
new plant episodes. It verifies the source-pinned artifact, physical traces,
independent learning audits and comparison screen before inspecting outcomes.

For each recorded step the signed error is decomposed exactly:

```
prediction - true velocity
  = retention * (estimated previous velocity - true previous velocity)
    + (estimated gain - true gain) * applied action
```

The two terms can cancel. Their absolute magnitudes must not be added and called
total prediction error. Hidden simulator state appears only in offline diagnosis;
it is never supplied to the learning controller.

A separate calculation substitutes nominal gain 0.27 while holding the recorded
state estimate and action fixed. It measures a conditional forecast difference,
not a causal control improvement: deploying another gain can change decisions,
observations and the entire subsequent trajectory.

This analysis uses the previously consumed development seed 9. It provides a
mechanistic hypothesis, not an independent performance evaluation or permission
to tune against final holdout outcomes.

## Actual findings

All 480 signed-error identities reconciled with maximum absolute residual
1.1102230246251565e-16. The following comparisons hold the single-use candidate's
recorded state/action trajectory fixed and include only nonzero actions:

| Regime | Recovery period | Steps | Learned forecast MAE | Nominal forecast MAE | Difference |
|---|---|---:|---:|---:|---:|
| Stationary | Before | 13 | 0.006209475 | 0.005462973 | +0.000746502 |
| Stationary | After | 8 | 0.007685871 | 0.006632934 | +0.001052938 |
| Drift | Before | 11 | 0.046976599 | 0.052678201 | -0.005701602 |
| Drift | After | 5 | 0.108954220 | 0.113303841 | -0.004349621 |

Every zero-action group has exactly equal learned and nominal forecasts. This
follows from the gain multiplying zero, not from evidence of estimator accuracy.
The learning contribution is unfavorable in stationary conditions and favorable
in drift on this recorded development trajectory. It does not establish that a
gain selector would improve actual closed-loop control.

## Next hypothesis

An independently reviewed next hypothesis is a sensor-only selector between
nominal and learned gains. A shadow learner would continue consuming each pair
once, while both models make immutable forecasts before observing outcomes.
Delayed observations would score those forecasts once, before learning from the
same observation. Selection would affect future commands only; recovery would
clear selection evidence and pending forecasts through the existing authority.

An initial fixed four-consecutive-better-forecasts rule is proposed for testing,
not implemented or calibrated by this diagnostic. It is not a confidence test;
noise and dependence can create false switches. Sparse actions can delay
adaptation. No method guarantees zero learning cost against an exactly correct
prior while adapting to unknown changes. The next candidate must face mismatched
nominal priors and frozen/single-use controls under unchanged outcome gates.

## Reproduction and status

The CLI requires the compressed `.json.gz` artifact. From the repository root:

```sh
PYTHONPATH=src .venv/bin/python scripts/diagnose_standard_learning.py --artifact docs/galahad/evidence/standard-learning-development-v1.json.gz > /private/tmp/nerve-standard-learning-diagnostic-reproduction.json
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_standard_learning_diagnostic.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

The [full diagnostic](evidence/standard-learning-diagnostic-v1.json.gz) retains
per-step decomposition; the [summary](evidence/standard-learning-diagnostic-summary.json)
retains aggregates and source hashes. Ten targeted tests and independent review
passed. This CPU-only diagnostic executed zero new episodes and used no holdout
outcomes. It introduces no control policy, training or deployment authority.

Full regression passed **1,684 tests in 160.085 seconds**, with zero failures or
errors. See the [validation receipt](evidence/standard-learning-diagnostic-validation.json).
The full diagnostic's uncompressed SHA-256 is
`568a040b61e66a677e4dbab3d5a2587a05881ad11bf8776cf73c1b4a1ab60d2f`.
