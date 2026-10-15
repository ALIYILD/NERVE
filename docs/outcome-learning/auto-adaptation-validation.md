# Automatic adaptation validation — 2026-10-15

- Full NERVE unittest suite: 1,460 run, 1,459 passed, one skipped; 236.361 seconds. Existing socket/nested-sandbox tests ran with their required permissions.
- PerfFlux relevant suite: 70 passed; changed test lint and formatting checks passed.
- Clinical OS offline process suite: two passed.
- Both application source manifests matched the pinned NERVE source byte-for-byte.
- Each application resumed in a new process after the second phase's strategy switch, monitored the trial, adapted back, and returned identical final state on repeated execution.
- NERVE module and Agent OS bridge entrypoints both completed the same bounded protocol.

Each domain: 28/36 operational successes, versus 24/36 and 12/36 for fixed controls; two strategy switches; all three monitoring windows 8/8. Eight pre-recovery failures are included. Additional adaptive evaluation: 32 calls per domain. Separate trial reversal: two failures, rollback, then six successes.

Evidence: `auto-adaptation-applications.json`. These synthetic task families demonstrate the mechanism, not real clinical or GPU efficacy, equal-compute superiority, or general adaptation. Production policy/scheduler activation is not part of this result.
