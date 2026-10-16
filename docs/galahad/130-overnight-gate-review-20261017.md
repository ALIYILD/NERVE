# 130 — Overnight gate review, 17 October 2026

**Verdict: retain_incumbent. D4: not achieved.** The existing v3.2 grid in [doc 129](129-gate-v3_2-coverage-grid.md) already evaluates the requested m ∈ {12, 14, 16} design against registered and fresh seeds. All three values fail the pre-registered requirement of zero observed harmful accepts. No qualifying m exists, so no gate-v3.2 signing payload or signing request is prepared. The canonical signed gate remains v3.

This review does not rerun experiments with alternative seeds, lower targets, or relabel this failure as insufficient power. For every m, registered narrow-64% has 1 harmful promotion per 10,000 streams and fresh measured-v5 has 2 per 10,000. The nine harmful outcomes determine the failed qualification. At m=12, the broad G2 target also fails. Favorable acceptance and H0 rates cannot override the harmful criterion.

## Scope and historical metric

The registered candidate scope requires at least 8% primary discordance across all nine balanced strata, conditional win probability at least 0.85, and a validated profile. Narrow-88% lies outside this scope and the public proposed Process returns insufficient_power before sampling. This boundary is necessary, not a distribution-free power guarantee. The measured-v5 plug-in discordance is 9.556%, but its scaled dev Wilson lower endpoint is about 7.50%, below the proposed floor. No failed gate is certified by these planning estimates.

V3's historical 92.12% broad non-promotion included primary non-acceptances and incomplete evaluations. G2 identified 6,676 of 7,464 evaluated candidates, or 89.44%. The grid reports G2 identification with its evaluated denominator separately. These metrics must not be conflated.

## Preflight discrepancy and holdout eligibility

`retained_promotion_gate.verify()` verifies the signed payload `c1dab32c453609ce2cae72a7c3b660874f243b1f2e67bebde8c9463d44de22d8`, bound evidence, and protected files. The legacy checker fails a later historical-state assertion requiring bank v4's consumption ledger to remain empty. The live ledger has one complete allocation for `v5-gate-v3-20261016` with 100 consumed items and 508 allocated slots (52 for each of eight strata and 92 for dissenter). Consequently 1,292 slots are unallocated; this is distinct from 1,700 not-yet-consumed items. The prior allocation is not released or reused by this review. The live bank-v5 ledger reports zero reserve consumption and 100 dev items consumed.

L4 remains unexecuted. A broad candidate may proceed under canonical v3 only after its registered dev handoff, all infrastructure checks, and an exclusive fresh allocation satisfying per-stratum capacity. Narrow v5 cannot proceed under the failed unsigned v3.2 proposal. The legacy checker is preserved unchanged; its failure remains visible in preflight reporting. No holdout item-level outputs were inspected, and no reserve permissions were changed.

## Replay evidence

The reproducible read-only command is `python3 scripts/reverify_overnight_gate_20261017.py`. It checks the 390 indexed file hashes; decompresses every existing stream receipt and verifies its raw hash, promotion count, item total and maximum; and replays all nine harmful promotions through the public scalar Process using the existing registered-seed auditor. It blocks network access and redirects the auditor's output into the new report rather than rewriting historical evidence.

Aggregate replay of 1,860,000 rows is not a fresh scalar replay of every stream. The existing research contains 18,600 historical scalar/vector parity checks; this review does not represent those as newly executed. The overnight audit passed: all 390 indexed hashes, 186 receipt cells / 1,860,000 aggregate rows, and all nine harmful scalar cases match. The new [reverification receipt](evidence/overnight-20261017-gate-reverification.json) has SHA-256 `076763e611506e37bafedcc6f37ade4c39d5a016fd4478b7d9a2c356813c3c2b`. W0 authorized this CPU audit alongside its test suite; W1 launched no competing test suite.

All outcomes are synthetic. New inference, pod operations, reserve consumption, and GPU spend are zero. No gate or skill was signed, retained, installed, or activated.
