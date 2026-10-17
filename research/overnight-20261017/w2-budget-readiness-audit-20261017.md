# W2 admission audit at 684c162 — CPU inspection only

The tracked tree was clean at inspection. Current readiness source hashes match current files, but the readiness claim of 43 tests in 15.89 seconds references `cycle-remote-integrity-py313.log`, which still reports 41 tests in 2.47 seconds. Its referenced snapshot receipt predates changes to the program, Hermes worker and Claude tests. A fresh focused run with matching source snapshots and receipts is required before this readiness can substantiate the new HEAD. No model/API call was made for this audit.

## Budget implementation

`reserve_call` serializes reservations with a mutex. A Socratic attempt reserves $0.50 before dispatch, including failed attempts. Before recording a claim it checks both compute plus accumulated allocations plus the new $0.50 against $11, and incremental compute plus allocations against `resume_compute_cap_usd`. General accounting also stops at or above those limits. The 1,000-call ceiling therefore does not authorize $500 of paid calls; the dollar check binds first. A new attempt can bring the allocation exactly to $11, but cannot exceed it under this accounting model.

The numbers are conservative reservations, not provider invoices. The worker caps prompt bytes, output tokens, iterations and run time. The cycle's accounting includes `base_compute_usd`, the current pod interval, and this cycle's allocation claims. It does not independently add prior API allocations or a second concurrently running pod. W0 must include prior exposure in the baseline and separately enforce total spend across any other pod; admission must not treat this one-pod accounting as a complete two-pod invoice. Failed claims must not be removed to recover budget.

The budget ceiling has an existing focused refusal test for a $10.75 compute baseline plus a new $0.50 allocation, but the current claimed 43-test receipt needs correction as above. Remote worker hash verification from 8a2cfec remains present. Inference release remains W0's responsibility after valid preflight and scoped authorization; this note grants neither.

## Evidence correction

W0 authorized a fresh focused run after the tracked tree stabilized at 684c162. All 43 tests passed on the supported Python 3.13.12 environment in 8.67 seconds with an atomic test lock and identical before/after source snapshots. The matching receipt and log are `cycle-claude-workspace-py313.json` and `.log`; readiness now references these. This resolves the stale evidence reference, not live admission. W0 confirmed only one pod will run and no previous API calls are evidenced, and will bind the current total baseline plus a remaining allocation of at most $10, expiring 06:00 UTC. No API or model calls were made by this audit or test run.

After the successful run completed, another writer changed `scripts/overnight_cycle.py` to add current-preflight guards. The 43-test receipt remains valid for its recorded684c162 source hashes only; current-tree validation is explicitly false pending that writer's focused revalidation.
