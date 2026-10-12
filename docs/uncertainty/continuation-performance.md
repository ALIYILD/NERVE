# Atomic assessments and development performance

Continuation from `64b6073`, implemented in `5d2d529` on `codex/uncertainty-integration`.
Source digest after changes:
`b3a814bf355fd98e5e971112602242104f9713bd877fcbabba52f3b3d8b2e75f`.

Assessment creation previously committed dependency links before validating and
storing the final policy assessment. A denied policy change or failed receipt
write could therefore leave dependency events and revisions behind. Claims,
inherited dependencies, links, fixed policy and the assessment now share one
`BEGIN IMMEDIATE` transaction. Failure rolls back all of them. Dispatch binding
also acquires its write transaction before inspecting an existing binding.

This consolidates connections and commits without reducing durability or skipping
source, role, task, expiry, parent dependency or revision checks. Two regression
tests inject a receipt failure and reject a policy downgrade, confirming that
neither leaves partial dependencies or lifecycle history.

Task adaptation now joins the task and grant lookup instead of issuing two SQL
queries. The actor capability, current grant, tenant and agent are still checked
on every read. An attached coordinator skips a redundant schema-existence query;
a restarted host with no coordinator still checks persistent opt-in and denies
omission. Five new tests exercise grant revocation, actor revocation, cross-tenant
access, the current kill switch and coordinator omission after restart.

## Observed development measurements

| Diagnostic | Before | After | Interpretation |
|---|---:|---:|---|
| Median assessment time, seven repetitions of 30 decisions | 6.588 ms | 3.766 ms | 42.8% lower local median; sequential diagnostic, not a production estimate |
| SQL queries per authorized adaptation read | 2 | 1 | Exact reduction; permissions checked every time |
| Median time for 2,000 authorized reads, 12 interleaved rounds | 124.762 ms | 85.983 ms | 31.1% lower isolated read time |
| Median 12-episode development batch, same interleaved study | 601.456 ms | 602.087 ms | Effectively unchanged; no end-to-end improvement established |

The assessment study excludes setup and uses a fresh disposable database per
repetition. The adaptation study alternates old/new methods in seeded order and
generates development episodes; it never loads the frozen holdout. Earlier noisy
diagnostics were not used to select a favorable timing result. The final exact
profiler receipt is the basis of the table.

No promotion threshold changed. The prior adaptation overhead rejection and
negative fast-memory result still stand. The previous uncertainty benchmark
belongs to its original source digest; these changes do not borrow it as a new
held-out benefit claim. No paid provider request, production activation or
deployment occurred.

## Reproduction and evidence

```sh
cd /Users/aliyildirim/nerve-uncertainty
PYTHONPATH=src python3 benchmarks/uncertainty/profile_assessment.py
PYTHONPATH=src python3 tests/test_adaptation_performance.py --profile
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_uncertainty_integration.py' -v
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_adaptation_performance.py' -v
PYTHONPATH=src python3 -m nerve_awim.uncertainty.combined_demo --state /tmp/nerve-continuation-demo.sqlite3
```

The adaptation profiler reads trusted baseline `64b6073` from local Git history;
it needs that commit available in the checkout. It swaps only the two measured
methods and restores them on exit. It is an explicit development command, never
run on import or automatically inside the test suite.

Controlled evidence: `/private/tmp/nerve-continuation-evidence/` contains
`policy-before.json`, `policy-after.json`, `adaptation-profile.json`, `combined.json`
and `full-tests.log`. The combined demo again reports `passed: true`: correction
reuse works, relevant conflicts block effects, independent work proceeds and
restart/reset retains evidence. Aggregate regression results are recorded in
`implementation-progress.json`.

Final regression: **1,128 Python tests passed, zero skips**, exit 0, 89.589 seconds, using `PYTHONPATH=src /private/tmp/nerve-adaptation-ci-venv/bin/python -m unittest discover -s tests -v`. This includes all seven new regression tests. The three combined integration tests and fresh-state combined demo also passed separately. The previous seven Node checks remain unchanged; no JavaScript was modified. No new holdout or provider study was run.
