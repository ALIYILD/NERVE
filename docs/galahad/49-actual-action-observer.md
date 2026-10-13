# Authenticated actual-action observer

The prediction audit found that the suspended controller's filter does not
advance while the synthetic external supervisor applies commands. The new
`ActualActionObserver` can track those confirmed commands in a separate state
estimator. It has no controller reference, actuator, recovery method, memory
promotion capability or automatic deployment path. Existing controllers remain
unchanged; the observer is opt-in and used alongside the research runtime.

## Host boundary and state semantics

The host injects the existing IdentityVerifier interface and binds issuer,
audience and an allowlist of reporter subjects. Mutations require a verified
identity with `actual-action-observer` role, unexpired credentials and monotonic
host verification time. The audience must identify the intended host observation
scope. No caller-supplied role dictionary is trusted. This is an injected local
verification contract, not a new production IdP, network API or clinical service.

`record_action` accepts an authenticated report of an already executed action
(-1, 0 or 1) and the model gain applicable to that transition. It emits an
observation-based predicted state using that action, then retains an immutable
gain history for delayed sensor replay. This output is not an action proposal.
Reports must use globally ordered transition numbers. A future step with a gap,
or explicit `record_unknown`, makes the estimate unavailable. No missing action
is filled with zero. Only a complete current sensor checkpoint can re-establish
state after unknown history; this resets only the observer's epoch.

A zero report is a factual host assertion, never an assertion that zero actuation
is safe. The host is responsible for confirmation from the execution boundary.
The synthetic demo assumes the initial plant is at rest, matching the observer's
initial state. Starting against an existing running system requires an explicit
unknown-history transition and current checkpoint. Observer state is in-memory;
restart persistence and hardware event delivery are not implemented here.

Delayed position/velocity measurements can correct known contiguous history, but
not reach across an unknown epoch. Inputs use strict types and finite bounded
values. Updates stage a copied filter and validate numerical results before
committing. A numerical exception means **no forecast for that report**: callers
must not reuse the previous snapshot as a current forecast, and must explicitly
record unknown history if continuing after an unprocessable executed action.
Snapshots include `next_step` so their temporal scope is explicit.

Public reads and mutations serialize through an RLock. History is bounded (4,096
transitions by default, configurable up to 10,000). On budget exhaustion, a valid
actual-action report advances the observer clock but marks the estimate unknown;
it does not leave a current-looking stale estimate. A current authenticated sensor
checkpoint can start another bounded epoch. These are synthetic research limits,
not a claim of real-time performance or certified state uncertainty.

## Executed demonstration

`scripts/demo_actual_action_observer.py` wires the observer alongside the existing
NerveResearchRuntime. A synthetic verified reporter confirms each applied action.
The 16-step noiseless, known-model trace contains **11 externally supervised
steps** after sensor outage. The observer changes neither controller phase,
incident, action history nor controller state. It never authorizes recovery.

External-step velocity MAE was **0** for known-action propagation and
**0.022419614329121425** for the existing frozen-state forecast. This is a single
deterministic mechanism test with matched known plant parameters, not a learned
improvement, randomized benchmark, claim of robust accuracy or model promotion.
No prospective study/holdout streams were used. A future learning study must use
the same observer and factual-action access on frozen and adaptive controls.
[Recorded trace](evidence/actual-action-observer-demo-v1.json).

## Verification and reproduction

Fifteen unit/integration tests cover authority, expiry, time/replay rejection,
actual-action physics, gaps, current checkpoints, delayed replay, immutable gains,
invalid/numerically unsafe updates, history budget, concurrent duplicate reports
and a suspended controller unchanged by observation. One executable-demo test
checks the entire 16-step integration. Independent review reproduced the observer
tests and found no blocking issue for this synthetic scope.

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_actual_action_observer*.py' -v
PYTHONPATH=src .venv/bin/python scripts/demo_actual_action_observer.py \
  --directory /private/tmp/nerve-actual-action-observer-reproduction
.venv/bin/python scripts/verify_galahad.py baseline
```

Use a fresh output directory for the demo. No remote authentication, Galahad GPU
restore, live clinical integration, weight training or deployment was performed.

Full regression: **1,525 tests passed in 121.126 seconds**, zero failures/errors.
[Validation record](evidence/actual-action-observer-validation.json).
