# Recovery-epoch learning hypothesis and development rejection

This cycle returned to control performance after the verified forecast-memory
integration. It made the stale-gain diagnosis reproducible and implemented one
opt-in hypothesis: after independently authorized recovery, replace pre-outage
adaptation with the configured nominal gain and a fresh evidence gate.

The development comparison found regressions when the configured nominal gain
was wrong. The blanket-reset candidate is therefore not advanced as an improvement.
No new registered training, validation or final-evaluation streams were consumed.

## Mechanism and boundaries

The original estimator learns from consecutive observed velocity pairs with
nonzero actions. Sparse informative actions and sensor outages can leave learned
gain unchanged. Existing window forgetting clears fitting samples while retaining
gain. Recovery also resets local transition indexes, so those indexes cannot be
used as global evidence age.

The new diagnostic examines only the 128 recorded training episodes with seeds
41001–41008. It pairs each gated arm with the same-seed, same-regime frozen arm at
the same planning horizon. It reconstructs global last-update and last-gain-change
times and compares fixed intervals and post-recovery groups. These are descriptive
associations, not causal estimates or tuning evidence from a holdout.

In drift horizon-1 training, three of eight recoveries retained gains around
0.48–0.49, with last changes 18–22 steps old. Those episodes had a mean paired
post-recovery goal-error increase of about 0.028731 over the frozen control. The
other five retain-window episodes averaged about −0.001462. Horizon-3 regressions
also occurred without elevated recovery gain, so staleness is not a complete
explanation.

Research on forgetting in parameter estimation emphasizes the role of informative
inputs. Its convergence results have assumptions; they do not establish that
resetting this nonlinear, guarded controller to its prior will help. See the
[variable-direction forgetting tutorial](https://arxiv.org/abs/2003.03523) and
[variable-rate forgetting analysis](https://arxiv.org/abs/2003.02737). This candidate
is a heuristic experiment, not an implementation of those papers' guarantees.

## Implemented candidate

`RecoveryEpochRuntime` reuses the existing evidence-gated controller, prospective
filter and identity/signed recovery path. Successful authorized reseeding creates
a new fitting window and restores the configured initial gain. It updates only
the new filter's next transition coefficient; archived filter histories remain
unchanged. Direct reseeding cannot activate the fallback outside the identity
authorization path. No truth, regime label, outcome error or fixed outage time
enters the candidate.

The nominal parameter is configuration, not newly learned evidence. Tests use
alternative priors to ensure it is not hardcoded to the simulator's default.
The candidate remains opt-in and is not a default replacement.

## Actual development comparison

Twelve episodes, 960 simulated steps, development seed 9. Each plant uses the same
noise/dropout draws across frozen, existing gated and recovery-epoch arms; all
controllers start with nominal gain 0.27 and planning horizon 1. True gain is used
only for environment transitions and scoring. Stationary plants include 0.18,
0.27 and 0.40, plus the existing changing-gain schedule.

| Plant | Existing gated goal MAE | Reset candidate goal MAE | Existing gated prediction MAE | Reset candidate prediction MAE |
| --- | ---: | ---: | ---: | ---: |
| Constant 0.18 | 0.148419766 | 0.159395348 | 0.011608399 | 0.016283420 |
| Constant 0.27 | 0.143761226 | 0.143761226 | 0.006637115 | 0.006637115 |
| Constant 0.40 | 0.260707808 | 0.261950573 | 0.033571576 | 0.044149016 |
| Changing gain | 0.160138309 | 0.160138309 | 0.023441317 | 0.023441317 |

All twelve episodes recorded zero envelope violations and exercised authorized
recovery. One development seed is not a general benchmark or confidence estimate.
The counterexamples are enough to reject a claim that this simple reset is an
established improvement. Its mechanism may still inform a different hypothesis,
but parameters must not be tuned against consumed final-evaluation data.

The executable development screen compares every plant against both frozen and
existing gated controls. It requires nonregression in goal error, prediction error,
violations and supervision steps plus a strict aggregate goal improvement. The
actual result is `eligible_for_registered_study: false` and
`next_action: retain_baselines_and_revise_hypothesis`. This is a development
screen, not a preregistered independent experiment or a deployment gate.

The initial diagnosis proposed testing the recovery-epoch hypothesis. Its proposal
is superseded by these development counterexamples; it must not be interpreted as
authorization to launch an unchanged candidate. The development fixture was run
again after adding the automatic screen; those repeated cases are not additional
independent samples.

Evidence: [training diagnosis](evidence/recovery-gain-diagnostic-v1.json),
[complete development traces](evidence/recovery-epoch-development-v2.json.gz), and
[case summaries, gate decisions and source hashes](evidence/recovery-epoch-development-summary.json).
The runs used Python 3.10.0 on macOS 26.5.2 x86-64, CPU only. No timing or cost
advantage is claimed.

Final verification passed **1,640 tests** in 275.108 seconds with zero failures or
errors. Independent review passed all 21 new tests and reconciled the actual
development results and rejection decision. See [validation evidence](evidence/recovery-epoch-validation.json).
Work is local on `feature/galahad-persistent-memory`, based on commit
`13cfda5fb47e30ff688128d95e9d0112225b83c5`; no PR, push, merge or deployment was made.

## Reproduction

```sh
PYTHONPATH=src .venv/bin/python scripts/diagnose_recovery_gain.py \
  --study /private/tmp/nerve-evidence-gated-study-v1 \
  --claims /private/tmp/nerve-evidence-gated-study-claims.sqlite \
  --coordinator-directory /private/tmp/nerve-memory-research-v1 \
  --coordinator-journal /private/tmp/nerve-memory-research-claims.sqlite \
  --output /private/tmp/nerve-recovery-gain-diagnostic-new.json
PYTHONPATH=src .venv/bin/python scripts/demo_recovery_epoch.py \
  --output /private/tmp/nerve-recovery-epoch-demo-new.json
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

Use fresh output filenames. The diagnostic validates existing receipts and replays
their calculations without executing plant episodes. The demo is a reusable
development fixture. All work is CPU-only and synthetic, with no clinical
authority, model-weight training or deployment.

The first full-suite attempt hit its 300-second runner limit before completion
and is recorded as incomplete, not passing. The verification runner now accepts
an explicit per-process timeout from 1 to 1,800 seconds, retaining the 300-second
default. The final-code check uses 600 seconds. This changes only the wait budget,
not assertions, test selection or scientific acceptance thresholds.
