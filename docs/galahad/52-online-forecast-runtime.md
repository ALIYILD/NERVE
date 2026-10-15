# Online forecast research runtime

This integration connects the fixed phase-aware forecast rule to an opt-in
research runtime. It does not feed forecasts into control decisions or promote
the candidate. The previous prospective comparison remains a shadow-replay study;
this cycle checks executable online wiring and behavioral equivalence.

## Execution boundary

The original runtime issues commands. A separate trusted reporter confirms what
actually executed. The wrapper captures the controller's pre-command state and
gain, retains one pending action step, and computes the controller forecast from
that captured state. Agents cannot supply their own forecast or gain. A
controller execution report must match the issued action. External-supervision
reports are accepted only after controller abstention.

A pending action must be resolved by a valid execution report or an explicit
unknown-action report before another wrapper tick. Unknown action history
invalidates observer continuity; it is never filled with an assumed zero input.
This backpressure is an intentional research-host contract. The wrapper is not an
actuator watchdog or a production control service.

Report deadlines use the simulator's nonnegative integer step clock: `now - step`
must stay within the configured execution-report delay. This is not a wall-clock
deadline or network timeout. Late factual execution reports are rejected; an
authenticated unknown-action report can resolve the pending step without claiming
that its action is known. The wrapper requires a fresh runtime and matching fresh
observer at construction. It does not support attaching to an arbitrary running
controller or restoring an online session after process restart.

Reporter authentication is distinct from recovery authorization. The existing
signed approval and identity checks still control recovery. Accepted observations
are mirrored from host-cached values, not replaced by caller-supplied sensor data.
All examples use synthetic identity fixtures and synthetic plant observations.

## Verification scope

Development seed 9 is used for stationary and drifting plants with frozen and
adaptive controllers. The online driver executes the plant, reports the factual
action, and scores against the resulting state separately. It compares wrapped
and unwrapped trajectories and recovery events, and checks online forecast values
against the existing ordered replay. Reusing this development fixture is an
equivalence check, not a new held-out performance experiment.

The consumed phase-forecast training, validation and final streams are not rerun
or used to tune this wrapper. Better control, broad scientific discovery, GPU KV
restoration, production authentication and clinical deployment remain unverified.

## Recorded development run

The actual CLI run completed four online episodes and eight comparison episodes,
960 simulated steps in total. Each online episode exercised 65 controller steps,
15 external-supervision steps and one authorized recovery. All four trajectories
and recovery-event lists matched the original runner exactly; selected estimator
and recovery states matched the unwrapped local driver at every step. All 320
online forecasts matched ordered replay, with zero missing forecasts and zero
recorded envelope violations in the four online episodes.

Full recorded evidence is available as [compressed JSON](evidence/online-forecast-demo-v1.json.gz),
with [case summaries and source hashes](evidence/online-forecast-demo-summary.json).
Report SHA-256: `6d23f50564ff3fdf32204d76c1d5e621a072d70829e3f5b18574ab68cd12053e`.
The run used Python 3.10.0 on macOS 26.5.2 x86-64, CPU only, starting from
commit `5b4bec7e5264bcde99465523ee46b69809dbdfaa` plus this cycle's new modules.

The original recovery runtime is used in this integration demonstration, including
its existing learning behavior. It is not a new comparison among the eight arms
of the prior forecast study. Numerical equivalence on this fixture does not prove
universal equivalence or improved task performance.

The saved demo contains the enabled trajectories and selected states, plus hashes
and comparison results from execution. It does not contain the complete disabled
and original state snapshots. A future read-only evidence importer can validate
recorded trace arithmetic and replay equivalence, but must not treat comparison
booleans alone as independent proof of the omitted comparisons. Those comparisons
are checked by the executable integration tests.

Full regression passed **1,587 tests** in 174.642 seconds with zero failures or
errors. Independent review passed all 19 new boundary/integration tests and
inspected the actual saved demo. [Validation evidence](evidence/online-forecast-validation.json)
records the scope and results.

## Next loop connection

The existing negative-outcome memory coordinator is source-pinned by earlier
receipts. A separate versioned extension should adopt this completed study,
validate online evidence without executing plant episodes, propose a narrowly
scoped research fact to the existing gateway, and wait for independent trusted
fact review before emitting a forecast-only review packet. Approval of a research
fact must not authorize recovery, deployment, control-policy promotion or another
use of the consumed holdout. This extension remains future work in this cycle.

## Reproduction

From the repository root:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_forecast_runtime.py' -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_online_forecast_demo.py' -v
PYTHONPATH=src .venv/bin/python scripts/demo_online_forecast.py --output /private/tmp/nerve-online-forecast-demo-new.json
.venv/bin/python scripts/verify_galahad.py baseline
```

Use a new output filename; the CLI refuses to overwrite an existing artifact.
This is a reusable development fixture, not a newly consumed research holdout.
No GPU, external model service, clinical data or production credentials are needed.
