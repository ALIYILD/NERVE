# CPU preflight v2: unchanged fast inventory, explicit longer deadline

The canonical `verify_galahad.py fast` gate previously exceeded its intrinsic
180-second limit. That result remains a timeout. This separate preflight uses
an explicit 1,200-second aggregate budget and does not rewrite the canonical
verifier, tier manifest, test assertions, or previous evidence.

The tier manifest sends newly added modules to fast. Its historical measured
profile is no longer a runtime bound for the merged inventory. The v2 deadline
is a separately authorized, bounded verification budget, chosen before execution
to allow the complete current inventory to finish. A pass here would not claim
that the original 180-second requirement was met.

## Registration and execution

`run_cpu_preflight_v2.py` discovers tests using the existing timed runner and
selects exactly `partition(discover(tests), 'fast', unchanged_manifest)`. Before
the first test it exclusively writes all 2,228 selected test IDs and 583 source
and test hashes. The child invokes the unchanged `timed_test_runner.py fast`
with the same manifest. A successful result requires exact inventory equality,
complete coverage, no failures/errors/unexpected successes, and unchanged source
hashes. There is no retry based on test results.

The shared atomic directory lock prevents two orchestration test suites running
at once. The one serial unittest runner may use existing fixture subprocesses.
A process-group timeout terminates the child and descendants remaining in its process group. Existing
localhost fixtures require execution outside the filesystem/network sandbox;
this is CPU verification, not permission for laptop model inference.

The deadline clock includes discovery, and the child receives the remaining
budget. The wrapper does not independently interrupt a parent stuck during
discovery; discovery completed normally in this run. This general watchdog
limitation is disclosed rather than claiming a stronger guarantee. An initial
competing invocation was rejected at the mutex before discovery or any test;
only the root-owned invocation executed the registered suite.

Registration base: `48286fcc3933f3a1d4be9814e6b2cfbfd6724dfa`.
Registration SHA-256:
`ef00311ba16c44605630b6ab5bf5dc3942d59a324abb38c2c0d2e1c7923f5281`.

## Result

**Blocked: the 1,200-second budget expired.** Exit code 124; total wrapper wall
1,201.563 seconds including termination and verification. Source hashes remained
unchanged. No final timing summary was written, so exact complete coverage is
not established and this is not a pass. The final active test was the mocked
400-row development/receipt replay fixture in `test_scientific_candidate_v3_study`.
It performs many durable SQLite transactions and authorization reads; no real
model calls occur. The completed verbose lines are retained for diagnosis but
are not spliced into a successful aggregate.

Receipts: `evidence/cpu-preflight-v2-registration.json`,
`evidence/cpu-preflight-v2-result.json`, and `evidence/cpu-preflight-v2-run.log`.
The user authorized a separately registered, more generously budgeted complete
run. A v3 pass, if obtained, will remain distinct from this failed attempt.

```sh
python3 scripts/run_cpu_preflight_v2.py /absolute/new/output
```

The output directory must not contain an earlier registration. The wrapper
acquires the shared suite lock itself. This command creates a new verification
record; it does not overwrite historical fast-gate evidence.

## Registered v3 protocol

`run_cpu_preflight_v3.py` is a separately reviewed full-run protocol with a
3,600-second budget, three times the expired v2 allowance. The larger allowance
responds to the observed incomplete 20-minute run and expensive durable mock
study fixtures; it is not a claimed measured upper bound. Before registering,
v3 requires every v2 source hash and the exact same 2,228 ordered test IDs to
match. It performs a fresh full run, without accepting prior verbose `ok` lines
as completion evidence. The source files and existing assertions are unchanged.

A SIGALRM watchdog bounds parent discovery. The remaining aggregate allowance
bounds the child process group. A result subclass adds a flushed, hash-chained
record after each completed test, anchored to the registration hash, solely for
diagnostics. Nested fixture-runner tests are excluded from this diagnostic
stream unless their identities belong to the registered inventory. Promotion
of verification status still requires the unchanged runner's complete timing
report and exact coverage, not the diagnostic journal alone.

## V3 result

**Passed the separately registered v3 preflight: 2,226 passed, 2 skipped,
zero failures or errors.** All 2,228 registered IDs were executed and recorded
in exactly the registered order, with complete selected-inventory coverage.
Suite time was 439.471 seconds; wrapper wall time was 470.021 seconds. All
registered source hashes remained unchanged. There were zero model calls.
The canonical 180-second gate and the v2 1,200-second attempt remain timeouts;
this result does not relabel either earlier attempt as passing.

The two existing dependency-conditional skips were:

- `test_memory_inference.InferenceServiceContractTests.test_actual_inference_and_scope_responses_match_openapi`: jsonschema required for OpenAPI response validation.
- `world_model.test_world_model.WorldModelTests.test_optional_mcp_real_stdio_inspection_binding`: official MCP SDK absent.

These checks were selected but their assertions did not run. No dependencies
were installed and no additional suite was run during wrap-up. Exact inventory
coverage is distinct from every selected assertion having executed.

The final timing report, all 2,228 diagnostic hash-chain links, unique IDs,
registered ordering and source hashes were independently verified. The journal
matches the timing records exactly. Receipts are
`evidence/cpu-preflight-v3-{registration,result,timings,verification}.json`,
`evidence/cpu-preflight-v3-run.log`, and
`evidence/cpu-preflight-v3-completed-tests.jsonl`.
Registration SHA-256:
`0bbac351b59dc6ea557f10239db76804bcbd7392ffe2f9ac52b5047427cc6b85`.

The earlier attempted launch was interrupted while escalation was pending and
produced no registered run. The subsequent root-owned execution was the single
v3 run. Approval resolved after the 06:00 UTC wrap-up boundary, so an unfinished
worker would have been stopped at 06:25 UTC to allow cleanup before 06:30 UTC.
**The run completed before that cutoff; no operational termination occurred.**
The prospective plan remains preserved in
`evidence/cpu-preflight-v3-operational-cutoff.json`, with the unapplied outcome
recorded in the final verification receipt. No GPU study was started to
compensate for the delay.

The lower observed duration than v2 is not attributed to a code optimization:
the registered test bodies were unchanged, and system load/I/O causes were not
measured. The slowest v3 test was the three-arm ARC release fixture (56.403
seconds); the previously active mocked 400-row study fixture took 12.612
seconds in this run.
