# Research memory planning

The synthetic research host can now consult approved episodic experiment memory
when deciding what research step to propose next. `ResearchMemoryPlanner` validates
the complete original study receipt and predecessor chain, then retrieves through
the existing scoped MemoryGateway. It requires an exact match of independently
regenerated content, source identity, episodic kind and receipt-review evaluator.
It never interprets stored prose as executable instructions.

A unique approved rejection proposes
`diagnose_rejection_and_register_new_hypothesis`. A unique approved candidate
proposes independent review. Missing, pending, expired, revoked, deleted,
ambiguous or mismatched memory proposes `verify_and_record_outcome`. That last
label means host lifecycle review is needed: it does not authorize re-ingestion,
restore revoked records or override consumed receipt tombstones. Retrieval is
bounded; inability to retrieve the matching record also takes this conservative
path. Cross-tenant access fails before reading the study.

Plans are advisory snapshots. Every execution still needs the existing registered
study protocol and durable consumption checks; no plan authorizes execution,
replay, candidate promotion or weight training. Revocation after a snapshot does
not retract the returned object; consumers must reauthorize every actual access.
The module has no dispatcher and is an explicit host entry point, not an automatic
replacement for the source-pinned research supervisor.

## Actual evidence

The standalone host command below read the persisted approved memory
`59dc328c34e3416eba2ff7ef961269f5`, independently revalidated receipt
`45c164be578cc63afecc2817ad4a06447330b607da2af9ba614a0eb08759d1d6`, and
returned `diagnose_rejection_and_register_new_hypothesis` with all execution,
promotion and weight-training flags false. A separate reviewer reproduced it.
No new plant episodes or holdout evaluations were run. This establishes reuse of
verified negative outcomes for planning, not improved model accuracy or speed.

The 13 new unit tests use a stub receipt verifier to isolate planning and lifecycle
behavior. The real receipt command complements those tests by validating the full
saved chain. Tests cover pending-to-approved transition, restart, revocation,
deletion, foreign tenant/context, revoked capabilities, revocation during receipt
validation, altered content, wrong evaluator, invalid receipt, duplicates and
mandatory independent candidate review.

## Reproduction

From the repository root, with the previously generated local study artifacts:

```sh
PYTHONPATH=src .venv/bin/python scripts/plan_research_from_memory.py \
  --memory /private/tmp/nerve-research-memory-v1/memory.sqlite \
  --study /private/tmp/nerve-evidence-window-study-v1 \
  --claims /private/tmp/nerve-evidence-window-study-claims.sqlite \
  --supervisor /private/tmp/nerve-research-supervisor-v1
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_research_memory_planner.py -v
.venv/bin/python scripts/verify_galahad.py baseline
```

The command does not dispatch experiments or mutate outcome records. Gateway
initialization may initialize database schema/quota metadata; this is not a SQLite
read-only connection. Host capabilities are local research authority, not remote
clinical authentication. Original experiment source pins remain unchanged.
Galahad GPU restoration, commercial licensing and clinical deployment remain
unverified; no general self-improvement or neural-weight training is claimed.

Full regression: **1,453 tests passed in 121.192 seconds**, zero failures/errors.
[Validation record](evidence/research-memory-planning-validation.json).
