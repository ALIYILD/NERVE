# Automatic diagnosis of an infeasible parameter search

The registered research graph now follows a verified WorldCore rejection with a bounded diagnostic node. A separate CLI can consume an existing WorldCore receipt, so the previous final evaluation is not repeated. Successful candidates do not trigger this failure-specific diagnostic.

The diagnosis identifies a structural mismatch in the current experiment. The evaluator suppresses sensor packets originating at steps 35 through 49. Fixed two-step delivery means the latest possible preceding packet arrives at step 36 and the next at step 52. The controller therefore encounters at least 15 consecutive missing updates. Every permitted candidate has `max_missing` between 2 and 12, and the controller refuses to act when that count is reached. It must abort no later than step 48, completing at most 48/80 = **60%** of the episode. The existing acceptance gate requires at least **95%** completion and zero aborts.

This conclusion is specific to the inspected evaluator and candidate schema. It explains why repeatedly mutating risk aversion and missing-packet tolerance cannot meet the gate. It does not imply that the safety stop is wrong or that NERVE generally cannot adapt.

## Executable evidence

The diagnostic recognizes the inspected evaluator using whole-function AST fingerprints, verifies the step budget and absolute gate constants, and fails closed on unknown semantics. It directly exercises the existing `WorldCoreV2` guard across 11 missing-packet limits and three risk values. These are mechanism checks: `miss()` and `choose()` run, but no plant action, full simulation episode, language-model call or held-out evaluation occurs. The continuous-risk conclusion follows from the guard being checked before risk scoring; only three risk values are measured.

The followup validates the predecessor ledger and deterministic decision replay, claims its diagnostic node before execution, and verifies the diagnostic receipt before reporting success. Every diagnostic case is claimed in SQLite before running. Source drift, malformed receipts and interrupted work retain consumed evidence. Existing output directories cannot be replayed. These are local operator-owned controls, not independent evidence custody.

The decision is to stop the unmodified parameter search. No safety threshold is increased and no candidate is promoted. The next research task is to design a prospective observation-recovery experiment, for example independently evaluated redundant sensing. That design and its new evaluation protocol remain outstanding; no safe physical fallback is claimed.

## Actual run

The diagnostic ran once against the verified previous WorldCore receipt: **33 mechanism cases**, **231 miss calls** and **231 choose calls** completed. Every first sensor-unavailable count matched its configured threshold. Zero plant episodes or holdout calls ran. The inferred completion ceiling is 60%; the recorded decision is `stop_unmodified_parameter_search`. No weights, production settings or controller gates changed.

- [Complete report](evidence/outage-diagnosis-v1.json.gz)
- [Summary, source pins and ledger hashes](evidence/outage-diagnosis-v1-summary.json)

The original study's source pins remain valid. The orchestrator gained its conditional branch after that study; this followup used the standalone receipt-consuming entrypoint, not a replay of the earlier graph. New graph executions invoke the same function automatically. The local diagnostic is terminal; no background process remains active.

## Verification

The full repository suite passed **1,319 tests**, zero failures/errors, in 89.946 seconds. Tests include malformed and consistently altered receipts, unknown evaluator semantics, source drift, incomplete claims, strict case schemas and automatic dispatch. Independent review validated the actual local ledgers and source hashes. See [validation evidence](evidence/outage-diagnosis-validation.json).

## Reproduction

```sh
cd /Users/aliyildirim/nerve-galahad
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/diagnose_worldcore_research.py \
  --directory /private/tmp/nerve-outage-diagnosis-replication \
  --predecessor /private/tmp/nerve-cross-track-orchestrator-v1/worldcore
```

Use a new directory and the verified predecessor's complete ledger/export. Source changes that invalidate the predecessor require explicit historical verification rather than silently accepting stale receipts. Repetition of these published mechanism checks is replication, not fresh held-out evidence.
