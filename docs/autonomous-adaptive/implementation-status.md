# Implementation checkpoint — 13 October 2026

## Follow-on: workspace inheritance and real local dispatch

The [local generation increment](local-generation.md) adds reviewed immutable
workspace text snapshots, a no-overwrite restore command, configured local runtime
inventory and real approved-note dispatch using the existing Ollama adapter and
shared budget. A live development probe returned an independently correct answer;
its receipt explicitly says no improvement has been demonstrated.

The follow-on full suite ran **1,419 tests: 1,418 passed and one skipped**, in
113.545 seconds. The focused integration suite passed 73 tests. A subsequently
added workspace-restore CLI test initially had a test-local variable placement
error; it was repaired and all four generation-bridge tests passed. The full run
preceded that final test addition; implementation source did not change afterward.

Phases 1 and 2 now include workspace restoration and one real fresh local session,
but automatic generational orchestration and held-out gains remain outstanding.
Phase 4 has actual metadata inspection, not comparative hardware optimisation.
The phase table below records the earlier checkpoint and must be read with this
update. No supervision changes were made in this increment.

## Earlier checkpoint

The ten-phase programme remains incomplete. This checkpoint implements bounded
generation notes through the existing host and a partial macOS service-controller
protocol. It does not claim measured improvement or independent live containment.

## Changes

- `GenerationMemory` uses `TrustedMemoryLedger` and its existing authority. Exact
  profile/task/model/runtime/template/evaluator scope, approved-only inheritance,
  immutable parent snapshots, expiry and ancestor revocation are enforced.
- `AgentOSLearning.generation_memory` and four bridge commands expose proposals,
  freeze, redacted inspection and explicit advisory handoff. They make no provider
  calls, issue no approval rights and leave legacy recall and budgets unchanged.
- `LaunchdController` is in the independent safety package. Pinned literal service
  policies, durable incident latches and intent/result journaling are tested.
  Managed service absence is separate from whole-workload containment. Native
  mutation is uncommissioned, restart is denied, and `verified` remains false.
  It is not wired as a live enforcement replacement for the current observer.

## Verification

| Check | Observed result |
| --- | --- |
| Generation + memory + Hermes + bridge focused suite | 79 passed, 4.844 seconds |
| Full NERVE suite | 1,392 run; 1,391 passed, one skipped; 238.584 seconds |
| Watchtower suite including new launchd tests | 102 passed, 7.691 seconds |
| New launchd checks | 12 passing injected-transport tests, not live shutdown evidence |
| Whitespace validation | Passed |

Full regression commands:

```sh
PYTHONPATH=src:scripts:tests python3 -m unittest discover -s tests -q
PYTHONPATH=safety python3 -m unittest discover -s tests/watchtower -q
```

The suites require localhost/test-process access outside the restricted execution
sandbox. New memory tests include a real separate Python process reopening the
ledger. Native launchd control is never exercised against the live learning job.

## Outstanding gates

| Phase | Status | Next required evidence/work |
| --- | --- | --- |
| 0 | Partial | Complete dependency/hardware inventory and frozen experiment design |
| 1 | Partial | Reviewed workspace-artifact handoff, actual fresh-session inheritance and matched held-out gain |
| 2 | Partial foundations | Installed orchestration of generation snapshots, cancellation and effect fencing |
| 3 | Partial foundations | Successive measured gains and verified retained capability through existing evolution |
| 4 | Not implemented as hardware selection | Operator-pinned runtime inventory, resource measurements, comparative selection and release |
| 5 | Not implemented | Approved additional hosts, supported backend, revocable node identities and distributed acceptance |
| 6 | Partial software only | Independent identities, protected installation/ACLs, whole-workload containment, recovery, notifications and target-host acceptance |
| 7 | Partial foundations | New preregistered contained experiments and independently graded results |
| 8 | Not integrated by this work | Actual DeepSynaps contract and precise independently validated authorised scope |
| 9 | Incomplete | Release/canary/rollback receipts after preceding applicable gates |

Read-only directory-service inspection found an additional non-admin account,
but its interactive shell does not establish dedicated restricted-workload status.
No account was modified or reclassified. Owner account-purpose confirmation and
independently managed MFA/alert configuration remain outstanding. No passwords
or token values should be supplied in chat.

The existing scheduler, budgets and queued CCE cohort remain unchanged. Runtime
inventory should compose `OllamaCueAdapter.inspect`, local job preflight and
existing Hermes inspection. Hosted aliases currently lack immutable model/tokenizer
attestation; the local adapter lacks verified hardware admission metadata. The
existing simulated recovery runtime must not be used as an inference adapter.
No configured distributed backend or authorised additional nodes were found.
