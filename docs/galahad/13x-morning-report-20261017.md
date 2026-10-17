# NERVE overnight report — 17 October 2026

**Early wrap-up at 01:08 London: the third recorded infrastructure failure triggered the stop rule.** All six pods are independently verified EXITED. Worker branches are preserved; required fast-gate integration is blocked.
No retained skill, registry entry, trust entry or signed gate was changed by this run.
All learning and reward evidence remains synthetic. Real clinician sign-off and real
PerfFlux workload reward are future inputs, not overnight accomplishments.

## Definition of Done

| Row | Status | Evidence and exact boundary |
|---|---|---|
| D1 self-learn | partial | W2 imported 1,200 episodes: historical B100, fresh B200 arm outcomes, deterministic A900. Two historical B proposal records of one configuration and one distinct A routing proposal; kept v5 leaves no failures. Not three cycles per family; no actual reverted seam. [Closure](../../research/overnight-20261017/closure.json). Legacy pinned v2 remains unchanged; companion schema is explicit. |
| D2 self-improve dev | partial | Fresh B01b kept: 35 wins, 0 losses, 65 ties, controls beaten, 100 calls in 198.9 seconds; independently replayed. Scope is two agreement strata, not whole-family safety. No Family A keep. [Fresh result](evidence/overnight-20261017/B01b-result.json), [leaderboard](../../research/leaderboard-20261017.jsonl). SDK fixture keeps do not count as canonical scientific family improvements. |
| D3 sealed improvement | not achieved | No new eligible broad candidate and no new signed narrow gate; L4 did not open any reserve. No new skill signing request from this run. [Gate review](130-overnight-gate-review-20261017.md). |
| D4 evaluator improvement | not achieved | Existing doc 129 grid fails the original zero-observed-harmful requirement. W1 and independent reviewer reproduce all nine harmful cases. [Audit receipt](evidence/overnight-20261017-gate-reverification.json). |
| D5 scientific adaptation | partial | Engineering fixture detects three shifts, switches/back and rolls back; SIGKILL/resume yields 1,200 unique receipts. This is not canonical 1,200-item scientific paired-bank inference evidence. W3: `docs/galahad/13x-drift-adaptation.md`, `receipts/loop-restart-20261017/restart-proof.json`. |
| D6 cross-domain adaptation | achieved, synthetic fixture scope | Same SDK/orchestrator completes PerfFlux and Clinical OS sandbox drift/switch/back/rollback on CPU. No workload latency or clinical benefit claim. [Study index](../../orchestration/w3-studies.json); W3: `docs/outcome-learning/auto-adaptation-20261017.md`. |
| D7 Loop SDK | partial | All five methods and three CLI demos exist with controls, receipts and replay. Signed evaluation fails closed for a host signed-gate integration; generator currently has one repair template. Full fast gate did not pass. W3: `docs/loop-sdk.md`, `src/nerve_awim/loop/`, `tests/test_loop_sdk.py`. |
| D8 verification | partial | Independent CPU replay, protected hashes and all six pods EXITED verified. Valid exclusive fast gate failed at 180 seconds; integration blocked. Provider billing differs from interval estimate; external queue lacks explicit source hash; some boundary rows were recorded late. [Independent review](../../orchestration/independent-review.md). |

## Branches and integration

The dirty local `/Users/aliyildirim/nerve-galahad` worktree at cb65c81 was preserved.
Workers started from remote b97aabf, a descendant of requested 1992f11, carrying
already-completed negative doc 129 evidence. Workers are `overnight/w1-gate`,
`overnight/w2-autoresearch`, `overnight/w3-adapt-sdk`; they are reviewable in their
separate worktrees and pushed to ALIYILD/NERVE only. Integration into Galahad is
blocked until the required fast tier passes. No force merge or history rewrite.

An external concurrent process committed 49bbe7b in `nerve-w0` and wrote a bounded
harmful-rate signing entry into the shared queue. None of this run's workers made
that change. The work is preserved; this run continued on isolated
`overnight/w0-final` at `nerve-w0-final`. The external proposal changes harmful 0
into a confidence-bound criterion and **does not satisfy original D4**. Independent
review verified its payload bindings, not its qualification under this run. Its
stored full-form string omits the original required explicit source hash. Nested
payload binding does not satisfy that field requirement. The external entry was
preserved, not silently repaired or signed.

## Evidence navigation

- Preflight identity: [report](evidence/overnight-20261017/identity-report.json),
  [registration](evidence/overnight-20261017/identity-registration.json),
  [receipt hashes](evidence/overnight-20261017/identity-bundle-hashes.json).
- W1: `overnight/w1-gate`, `docs/galahad/130-overnight-gate-review-20261017.md` and
  `docs/galahad/evidence/overnight-20261017-gate-reverification.json`.
- W2: `overnight/w2-autoresearch`, `docs/galahad/130-autoresearch-ledger-20261017.md`,
  `research/overnight-20261017/`, registered private dev study
  `/Users/aliyildirim/nerve-research-runs/overnight-20261017-B01b`.
- W3: `overnight/w3-adapt-sdk`, `docs/loop-sdk.md`,
  `docs/galahad/13x-drift-adaptation.md`,
  `docs/outcome-learning/auto-adaptation-20261017.md`, `orchestration/w3-studies.json`,
  `receipts/loop-demo-*-20261017/`, `receipts/loop-restart-20261017/`.
- Independent report: `orchestration/independent-review.md`; shared live ledger:
  `/Users/aliyildirim/nerve-orchestration/ledger.jsonl`.

## Preflight, tests and controls

All ten historical dev identity comparisons match canonical decoded bytes. Five
latencies were 14.728, 1.859, 1.668, 2.194, 1.856 seconds within registered bounds; 12 model
calls, zero reserve items. A40 model digest is
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, Ollama 0.40.5.
Canonical v3 signature verifies. The old combined checker fails its stale assertion
that bank v4 is empty: 100 items were already consumed and 508 slots allocated;
1,292 slots remain unallocated, not 1,700. No bank reset was performed.

Fast attempts under Python 3.10 and3.13 hit 180 seconds after 419 and 192 completed
success lines, respectively; these are incomplete counts, not passed suites.
Python 3.10 is below package support. W3 mistakenly used mkdir-p for a test lock,
briefly overlapping the second attempt; it stopped and documented the violation.
The final supported-interpreter, exclusive attempt also timed out at 180 seconds
(exit 124). Its log is `orchestration/preflight-fast-exclusive.log`. The third
recorded infrastructure failure triggered early wrap-up; no further inference is
authorized. No protected test limit or manifest was relaxed.
Focused tests: W2 12 compatibility/engine tests plus 3 cancellation tests; W3 eight
SDK tests after the ingestion fix; W0 six stop/budget/integrity tests. The new SDK
test module is automatically included in fast discovery without editing the
protected tier manifest.

The conductor is a fail-closed policy/state checker plus W0 MCP execution, not an
independent background service. It counts claims conservatively before calls,
revokes lock files on stops and emits stop actions. Only fresh MCP reads prove
EXITED. The running agent performs MCP polling and stop calls; a saved action plan
alone is not an autonomous shutdown guarantee.

## Human decisions

This run creates no qualifying gate/skill signing payload. Preserve and review the
external bounded-harmful proposal separately, using its exact payload and hashes;
never treat it as success against harmful 0. No signing, retaining or activation was
performed. Decide whether to authorize a future evaluator criterion, further
canonical drift evidence, and sharing SDK work with the two external repos.

## Compute, shutdown and limits

Exactly 112 claims/calls were recorded: 12 preflight and 100 B01b; no retries were
needed. Maximum concurrency was one A40 pod and four requests within B01b.
Two conservative request-to-EXITED intervals at the live MCP rate $0.59/hour total
**$0.20844873 compute**. This includes provisioning/shutdown waiting time. Storage
is excluded from that estimate. The provider billing snapshot spans broader hourly
buckets and reports $0.06747213 across six pods, including $0.00289352 disk; its
incomplete hourly buckets do not reconcile to this run yet. The returned records
cover 23:00–00:00 UTC despite the query ending at 01:00 UTC, include other pods,
and omit the B01b interval after midnight UTC. Neither figure is falsely
presented as a final invoice. The $12 cap and 12,000-call cap were not approached.
See `orchestration/spend.json`, `billing-snapshot.json`, and the independent live
`independent-final-pods.json` read. No active compute was left behind.

The immutable ledger contains the operational stop and actual study result.
W1/W3 summary rows were imported after their boundaries and explicitly marked
`boundary_recorded_late`; this does not satisfy perfect live-boundary logging.
The stop marker remains at `~/nerve-orchestration/inference-revoked.json`.

## Canonical drift missing data

The available retained A-v3 receipts cover 700 unique tasks; B-v4 bank-v3 receipts
cover 900; B-v4/v5 bank-v5 receipts cover 100 in two strata. Cross-set task-ID
intersections are zero. Adapted-v1 is not the unchanged retained A-v3, and v5 is
not retained. Relabelling these as paired retained outcomes would fabricate the
missing counterfactuals. W3 recorded a prospective paired-study requirement in
`orchestration/w3-canonical-drift-feasibility.json`; no such new study ran after
this stop. Synthetic switch-back behavior is not proof that the real retained
skills will support a switch-back on those tasks.

## Autoresearch closure

The new Family A audit applies canonical v3 to all 900 bank-v3 dev items: all
900 deterministically return unsupported-evidence abstention, giving 300 correct
and 600 incorrect outcomes without model calls. These are compatibility failures,
not a contradiction of the earlier different 100/100 receipt. Six failure clusters
support one distinct routing candidate: use retained B-v4 only when v3 declares
unsupported evidence. A01 is registered as an unexecuted next study; its runner
remains to be implemented. No candidate execution after the stop is claimed.

For Family B, v5 has no remaining errors in the fresh scoped study. The generator
therefore produces no next candidate instead of inventing a failure cluster. The
rejection-memory mechanism has tests, but no actual reverted experiment occurred
tonight. Neither family establishes three completed autonomous proposal cycles.

Final worker tips: W1 `46b0f2d`, W2 `8f81985`, W3 `3ac9d63`. The report branch
contains copied report/evidence snapshots, not an accepted merge of worker code.
Use the worker branches to inspect or run the corresponding implementations.
