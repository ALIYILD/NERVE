# Phase-aware forecast candidate and prospective study

This fixed candidate keeps the controller's own prediction while that controller
is acting and selects the separate actual-action observer during external
supervision. The rule was chosen from training-only observer diagnostics before
opening fresh experiment streams. It never selects the lower observed error, uses
true plant state to route, or changes commands. A successful forecast comparison
would not establish better control goals or overturn earlier rejected adaptive
controller results.

`PhaseAwareForecaster` reuses the observer's authenticated host boundary. The host
reports factual action source and, for controller actions, the contemporaneous
controller velocity forecast. The observer propagates every confirmed action so
that it remains current when selected. Invalid source/forecast combinations fail
before mutation. Missing history or exhausted observer capacity never falls back
to a stale forecast for external supervision. The component has no actuator or
recovery authority. Local synthetic verifier fixtures are not production identity.

## Frozen experiment

All eight previously registered frozen/adaptive/gated arms receive identical
routing rules in stationary and drift regimes. New training seeds are
44001–44008; validation seeds 45001–45008; final seeds 46001–46016. The routing rule
and controller parameters are fixed, with no search, runner-up or post-result
tuning. The worker executes each existing controller once, then performs ordered
observer replay from projected sensor/action/model fields before scoring.

This is a prospective **shadow forecast** experiment on freshly generated
trajectories, not an online change to the controller or a counterfactual action
comparison. Controller predictions must be bit-for-bit preserved. Every arm/regime
mean routed MAE must be no worse than legacy (tolerance 1e-12), with strict summed
MAE improvement greater than 1e-5. Missing forecasts or action changes fail gates.
Only a complete training pass opens validation; only a validation pass opens the
one-use final split. There is no automatic promotion. These forecast-specific
gates do not weaken or replace the existing control-study goal/safety gates.

Maximum execution is 512 episodes / 40,960 plant steps, 30 seconds per child and
1,800 seconds of episode execution. Source verification and receipt reconciliation
are separate overhead. Durable dataset claims precede execution, stage outcomes
are frozen, and a failed consumed run cannot silently retry. Source provenance
includes the verified observer reanalysis and its original study/coordinator chain.

New code is versioned separately, preserving existing experiment source pins.
Development worker tests use seed 9; registered streams are not used by tests.
All data are synthetic, with no clinical decision authority, GPU KV restoration,
LLM weight training or production deployment.

## Measured result

The completed CPU experiment consumed all 512 episodes / 40,960 steps. All three
stages passed their frozen gates, producing `forecast_candidate_for_review`.
Every one of the 16 arm/regime averages improved at each stage; controller-period
forecasts were preserved exactly and there were zero missing forecasts.

| Split | Episodes | Legacy mean absolute error | Routed mean absolute error | Relative reduction |
| --- | ---: | ---: | ---: | ---: |
| Training | 128 | 0.023250118 | 0.018280893 | 21.37% |
| Validation | 128 | 0.022907361 | 0.018586942 | 18.86% |
| Final holdout | 256 | 0.021566228 | 0.017472226 | 18.98% |

These are equally weighted arm/regime means, equivalent to episode means because
counts and lengths are equal. Holdout includes 16 shared seeds across eight arms
and two regimes; the 256 episodes are not 256 independent random seeds. The
comparison is paired on identical trajectories. No statistical significance or
generalization beyond these synthetic regimes is claimed. Individual trajectories
can regress even though every registered stratum average improved.

Environment: macOS 26.5.2, x86-64, Python 3.10.0, CPU only. Summed measured worker
times were 23.354 seconds training, 18.159 validation and 40.144 holdout. These
include control execution/validation, observer replay and scoring; they exclude
the outer forecast validation, process startup and receipt-chain verification, and are not an inference latency
or speedup benchmark. Full regression started after experiment completion.

The [summary](evidence/phase-forecast-study-summary.json) contains every stratum,
source pin and protocol; [full evidence](evidence/phase-forecast-study-v1.json.gz)
preserves all trajectories and forecasts. Report SHA-256:
`b3a6f4148aef9d74e4b6d21f4e7822fe5d1467f5911568484ed0b53c6242d280`.
The final split is consumed and cannot be reused for tuning. No candidate was
promoted, no control improvement established, and no neural weights trained.

Full regression passed **1,568 tests** in 178.192 seconds, with zero failures or
errors. Independent read-only receipt verification exited successfully and
reconciled the full source chain and all 512 recorded episodes without executing
new plant trials. See [validation evidence](evidence/phase-forecast-study-validation.json).

## Next integration boundary

An online research wrapper remains to be implemented and tested. Existing
`runtime_v28.tick` returns a command, not proof that an actuator executed it.
The wrapper must retain bounded pending command context and wait for a separate
authenticated factual execution report before advancing this observer. A
controller-source report must match the issued command; external-supervision
reports need their own trusted host authority. Missing, late or repeated reports
must not fabricate observer continuity. Forecast outputs must remain separate from
recovery authorization and actuator decisions. This is a proposed next step, not
part of the measured shadow-replay result above.

## Reproduction

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_phase_forecast*.py' -v
PYTHONPATH=src .venv/bin/python scripts/run_phase_forecast_study.py \
  --directory /private/tmp/nerve-phase-forecast-study-v1 \
  --claims /private/tmp/nerve-phase-forecast-study-claims.sqlite \
  --predecessor /private/tmp/nerve-observer-reanalysis-v1.json \
  --source-study /private/tmp/nerve-evidence-gated-study-v1 \
  --source-claims /private/tmp/nerve-evidence-gated-study-claims.sqlite \
  --coordinator-directory /private/tmp/nerve-memory-research-v1 \
  --coordinator-journal /private/tmp/nerve-memory-research-claims.sqlite
.venv/bin/python scripts/verify_galahad.py baseline
```

The experiment command is one-use. Add `--verify-only` to the identical arguments
for receipt verification after completion; it never executes episodes. Preserve
the shared claims database and original source pins. Changing the run directory
is not permission to retry a consumed dataset. The CLI requires existing source
study, coordinator and observer-reanalysis artifacts from the preceding cycles.
