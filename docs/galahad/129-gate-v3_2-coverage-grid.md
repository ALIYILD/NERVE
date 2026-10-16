# 129 — Gate v3.2 coverage grid and scoped power claim

**Selected m: None.** No grid value satisfies all registered targets; no signing payload is prepared.

Zero model calls, zero pod operations, zero reserve consumption. Signed gate v3 remains canonical; v3.1 remains withdrawn. This is a research proposal.

All three m values fail the zero-harmful target: each has 1/10,000 harmful accepts in registered-seed narrow-64% and 2/10,000 in fresh-seed measured v5. Each case replays exactly through the scalar gate. At m=14 and16, broad G2 detection and the other in-scope rate targets pass, but that does not override the harmful criterion. At m=12, broad G2 detection also remains below90%.

## Registration, scope and unchanged rules

Registration and code hashes were frozen before all results. Original seeds 2026101801/main and 2026101802/H0 ran first for every m; fresh seeds 2026102401/main and 2026102402/H0 ran second. There are 10,000 streams per cell. Common random numbers across m/scenarios support paired comparisons; cells must not be pooled as independent replications. Grid m ∈ {12,14,16}; primary cap 300 balanced across nine strata; e ≥ 20 with the existing bet, futility and initial-observation conditions. Coverage samples only uncovered answer strata, least observed first, to m discordances or zero in 60. Total cap 1,000 = 960 main plus 40 unconditional dissenter follow-up. G1 zero-tolerance and G2 zero-net-loss unchanged.

The pre-registered minimum primary discordance is **8% across balanced all-nine samples**, with conditional win probability ≥ 0.85 for the proposed good-candidate power claim. The in-scope profiles under evaluation are broad-75%, narrow-64%, and measured v5; no gate is certified by this failed grid. The measured agreement discordances are 22% and 64%, zero elsewhere as an explicit historical plug-in assumption. Their all-nine discordance is 9.556%. Narrow-64% has 8%; broad-75% has 25%. This does not claim distribution-free power for every heterogeneous vector above the minimum.

Narrow-88% is out of claimed scope: its all-nine discordance is only 2.667%. The proposed public Process requires a prospectively registered dev-scope hash, profile and discordance. Below the floor or outside the validated profiles, it returns **insufficient_power before sampling**, never retain_incumbent. Scope evidence must be verified by the study custodian; a hash-shaped string alone is not provenance. Scope is not selected retrospectively from holdout outcomes. The measured-profile rate is a planning estimate, not a certified population lower bound: the dev pooled-discordance Wilson lower endpoint, scaled to all-nine balance, is about 7.50%, below the 8% floor.

Out-of-scope raw-kernel simulations are retained below as diagnostics, including their H0 rates and hypothetical costs. Actual scope-enforced narrow-88% acceptance and H0 promotion are both zero, with zero items consumed. The 8% floor is a necessary boundary of the claim, not a guarantee for arbitrary untested profiles.

Qualification: all in-scope profiles in both seed sets need good acceptance ≥ 80%, regressed non-promotion ≥ 90%, H0 ≤ 5%, zero observed harmful accepts; broad G2 identification among evaluated candidates must itself reach 90%. The raw out-of-scope H0 diagnostic must also stay ≤ 5%. Small silent regressions are reported separately without inventing another selection target.

## Correcting the historical regression metric

V3’s 92.12% broad non-promotion was **not G2 detection alone**: 2,474 primary non-acceptances + 62 incomplete evaluations + 6,676 G2 detections = 9,212 non-promotions. Of 7,464 candidates actually evaluated by G2, 6,676 were detected: **89.44%**.

Doc 128’s original-seed broad result was G2 alone: 8,529/10,000 detections = 85.29%, with no primary abandonment. Its fresh-seed 85.09% overall non-promotion contained one primary non-acceptance plus 8,508 G2 rejections; 8,507 identified the deliberately bad stratum. Therefore it would be inaccurate to relabel every previously reported v3.2 total as “G2 detection alone.” The tables here expose G2-only identification with its evaluated denominator, separately from any-route non-promotion.

The old uniform coverage also oversampled some strata while waiting for the slowest. Adaptive coverage stops an evaluated stratum at its threshold, so raising m directly tests G2 power without credit for primary non-evaluations.

## Target tables

Rates are percentages. Rows marked outside are raw diagnostic outcomes, not admitted gate promotions.

| Seed | m | Profile | Scope | Good .85 | Good .90 | Regressed non-promotion | G2 bad-stratum detection / evaluated | Neutral | Harmful | H0 |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| registered | 12 | broad_75 | in | 99.64 | 99.99 | 88.17 | 88.17 | 1.10 | 0.00 | 1.18 |
| registered | 12 | narrow_64 | in | 83.02 | 94.43 | 96.89 | 38.17 | 0.51 | 0.01 | 0.60 |
| registered | 12 | narrow_88 | outside | 1.88 | 3.53 | 99.97 | 40.00 | 0.00 | 0.00 | 0.00 |
| registered | 12 | measured | in | 93.24 | 98.69 | 94.58 | 83.44 | 0.88 | 0.00 | 0.94 |
| registered | 14 | broad_75 | in | 99.80 | 99.98 | 90.22 | 90.22 | 0.91 | 0.00 | 1.06 |
| registered | 14 | narrow_64 | in | 83.03 | 94.43 | 97.18 | 43.94 | 0.51 | 0.01 | 0.59 |
| registered | 14 | narrow_88 | outside | 1.88 | 3.53 | 99.96 | 20.00 | 0.00 | 0.00 | 0.00 |
| registered | 14 | measured | in | 93.26 | 98.70 | 95.51 | 86.28 | 0.86 | 0.00 | 0.89 |
| registered | 16 | broad_75 | in | 99.92 | 100.00 | 92.21 | 92.21 | 0.82 | 0.00 | 1.06 |
| registered | 16 | narrow_64 | in | 83.03 | 94.43 | 97.75 | 55.27 | 0.51 | 0.01 | 0.58 |
| registered | 16 | narrow_88 | outside | 1.88 | 3.53 | 99.97 | 40.00 | 0.00 | 0.00 | 0.00 |
| registered | 16 | measured | in | 93.27 | 98.70 | 96.47 | 89.21 | 0.85 | 0.00 | 0.86 |
| fresh | 12 | broad_75 | in | 99.61 | 99.96 | 88.27 | 88.27 | 1.26 | 0.00 | 1.16 |
| fresh | 12 | narrow_64 | in | 83.53 | 94.97 | 97.25 | 42.23 | 0.55 | 0.00 | 0.68 |
| fresh | 12 | narrow_88 | outside | 2.02 | 3.50 | 99.97 | 25.00 | 0.00 | 0.00 | 0.01 |
| fresh | 12 | measured | in | 93.97 | 98.92 | 94.42 | 83.01 | 0.81 | 0.02 | 0.89 |
| fresh | 14 | broad_75 | in | 99.77 | 100.00 | 90.39 | 90.39 | 0.95 | 0.00 | 1.06 |
| fresh | 14 | narrow_64 | in | 83.55 | 94.97 | 97.52 | 47.90 | 0.55 | 0.00 | 0.67 |
| fresh | 14 | narrow_88 | outside | 2.02 | 3.50 | 99.97 | 25.00 | 0.00 | 0.00 | 0.01 |
| fresh | 14 | measured | in | 93.99 | 98.93 | 95.79 | 87.18 | 0.79 | 0.02 | 0.88 |
| fresh | 16 | broad_75 | in | 99.93 | 100.00 | 92.47 | 92.47 | 0.86 | 0.00 | 1.01 |
| fresh | 16 | narrow_64 | in | 83.55 | 94.97 | 97.87 | 55.25 | 0.54 | 0.00 | 0.65 |
| fresh | 16 | narrow_88 | outside | 2.02 | 3.50 | 99.96 | 0.00 | 0.00 | 0.00 | 0.01 |
| fresh | 16 | measured | in | 93.99 | 98.94 | 96.88 | 90.50 | 0.78 | 0.02 | 0.88 |

## Silent 5% / 10% regressions

One nominally silent answer stratum has loss-only discordance of 5% or 10% per item; agreement strata retain p = 0.85. The bad stratum rotates. The bound column refers specifically to that bad stratum, with all 10,000 proposed studies as denominator. Outside rows are raw diagnostics.

| Seed | m | Profile | Loss rate | Non-promotion | Bad stratum identified | Bound activated | Promoted with bound |
|---|---:|---|---:|---:|---:|---:|---:|
| registered | 12 | narrow_64 | 5% | 96.03% | 65.80% | 397/10,000 | 397/10,000 |
| registered | 12 | narrow_64 | 10% | 99.86% | 54.88% | 14/10,000 | 14/10,000 |
| registered | 12 | narrow_88 | 5% | 99.88% | 0.56% | 12/10,000 | 12/10,000 |
| registered | 12 | narrow_88 | 10% | 100.00% | 0.20% | 0/10,000 | 0/10,000 |
| registered | 12 | measured | 5% | 95.13% | 80.30% | 487/10,000 | 487/10,000 |
| registered | 12 | measured | 10% | 99.82% | 73.48% | 18/10,000 | 18/10,000 |
| registered | 14 | narrow_64 | 5% | 95.93% | 65.70% | 407/10,000 | 407/10,000 |
| registered | 14 | narrow_64 | 10% | 99.82% | 54.84% | 18/10,000 | 18/10,000 |
| registered | 14 | narrow_88 | 5% | 99.92% | 0.60% | 8/10,000 | 8/10,000 |
| registered | 14 | narrow_88 | 10% | 100.00% | 0.20% | 0/10,000 | 0/10,000 |
| registered | 14 | measured | 5% | 95.28% | 80.44% | 472/10,000 | 472/10,000 |
| registered | 14 | measured | 10% | 99.83% | 73.49% | 17/10,000 | 17/10,000 |
| registered | 16 | narrow_64 | 5% | 96.07% | 65.84% | 393/10,000 | 393/10,000 |
| registered | 16 | narrow_64 | 10% | 99.79% | 54.81% | 21/10,000 | 21/10,000 |
| registered | 16 | narrow_88 | 5% | 99.92% | 0.55% | 8/10,000 | 8/10,000 |
| registered | 16 | narrow_88 | 10% | 100.00% | 0.20% | 0/10,000 | 0/10,000 |
| registered | 16 | measured | 5% | 95.31% | 80.43% | 469/10,000 | 469/10,000 |
| registered | 16 | measured | 10% | 99.85% | 73.51% | 15/10,000 | 15/10,000 |
| fresh | 12 | narrow_64 | 5% | 96.29% | 65.96% | 371/10,000 | 371/10,000 |
| fresh | 12 | narrow_64 | 10% | 99.85% | 54.23% | 15/10,000 | 15/10,000 |
| fresh | 12 | narrow_88 | 5% | 99.86% | 0.59% | 14/10,000 | 14/10,000 |
| fresh | 12 | narrow_88 | 10% | 99.99% | 0.24% | 1/10,000 | 1/10,000 |
| fresh | 12 | measured | 5% | 95.94% | 82.13% | 406/10,000 | 406/10,000 |
| fresh | 12 | measured | 10% | 99.85% | 74.67% | 15/10,000 | 15/10,000 |
| fresh | 14 | narrow_64 | 5% | 95.94% | 65.60% | 406/10,000 | 406/10,000 |
| fresh | 14 | narrow_64 | 10% | 99.76% | 54.14% | 24/10,000 | 24/10,000 |
| fresh | 14 | narrow_88 | 5% | 99.90% | 0.63% | 10/10,000 | 10/10,000 |
| fresh | 14 | narrow_88 | 10% | 99.99% | 0.24% | 1/10,000 | 1/10,000 |
| fresh | 14 | measured | 5% | 95.68% | 81.85% | 432/10,000 | 432/10,000 |
| fresh | 14 | measured | 10% | 99.83% | 74.65% | 17/10,000 | 17/10,000 |
| fresh | 16 | narrow_64 | 5% | 95.76% | 65.37% | 424/10,000 | 424/10,000 |
| fresh | 16 | narrow_64 | 10% | 99.87% | 54.25% | 13/10,000 | 13/10,000 |
| fresh | 16 | narrow_88 | 5% | 99.90% | 0.60% | 10/10,000 | 10/10,000 |
| fresh | 16 | narrow_88 | 10% | 100.00% | 0.25% | 0/10,000 | 0/10,000 |
| fresh | 16 | measured | 5% | 95.74% | 81.81% | 426/10,000 | 426/10,000 |
| fresh | 16 | measured | 10% | 99.69% | 74.51% | 31/10,000 | 31/10,000 |

Zero discordances in the predeclared first 60 observations gives a marginal one-sided 95% exact binomial upper bound of 4.8703%, approximated by 5% using the rule of three. It requires IID stationary per-stratum paired outcomes. It is not equivalence, not a simultaneous bound across strata, and not a general anytime confidence sequence. True 5%/10% regressions can still yield zero events in 60 items with probabilities 4.607%/0.180%. Both first-60 certificates and terminal bound activation are retained in the stream receipts.

## Items and cost

[Complete per-class mean/p90 items, minutes and cost table](evidence/gate-v3_2-coverage-grid/items-and-cost-all-classes.csv) covers all 186 cells, including good, regressed, silent, neutral, harmful and H0 scenarios. [Machine-readable tables](evidence/gate-v3_2-coverage-grid/tables.json) also contain every metric and route count. Costs project historical 2.3–3.4 seconds per item at $0.59/A40-hour; actual GPU/model spend here is zero. All proposals, including primary failures, contribute to mean and p90. Simulations assume fresh per-stratum reserve is available; any real study needs a separate exclusive allocation and must stop if its reserve is exhausted.

Measured-profile good classes:

| Seed | m | p | Accepts | Mean / p90 items | Mean cost | p90 cost |
|---|---:|---:|---:|---:|---:|---:|
| registered | 12 | 0.85 | 9324/10,000 | 407.89 / 452.0 | $0.154–$0.227 | $0.170–$0.252 |
| registered | 12 | 1.0 | 10000/10,000 | 394.42 / 420.0 | $0.149–$0.220 | $0.158–$0.234 |
| registered | 14 | 0.85 | 9326/10,000 | 418.00 / 462.0 | $0.158–$0.233 | $0.174–$0.257 |
| registered | 14 | 1.0 | 10000/10,000 | 406.64 / 434.0 | $0.153–$0.227 | $0.164–$0.242 |
| registered | 16 | 0.85 | 9327/10,000 | 428.61 / 472.0 | $0.162–$0.239 | $0.178–$0.263 |
| registered | 16 | 1.0 | 10000/10,000 | 418.81 / 447.0 | $0.158–$0.233 | $0.168–$0.249 |
| fresh | 12 | 0.85 | 9397/10,000 | 408.17 / 451.0 | $0.154–$0.227 | $0.170–$0.251 |
| fresh | 12 | 1.0 | 10000/10,000 | 394.08 / 420.0 | $0.149–$0.220 | $0.158–$0.234 |
| fresh | 14 | 0.85 | 9399/10,000 | 418.31 / 461.0 | $0.158–$0.233 | $0.174–$0.257 |
| fresh | 14 | 1.0 | 10000/10,000 | 406.56 / 434.0 | $0.153–$0.227 | $0.164–$0.242 |
| fresh | 16 | 0.85 | 9399/10,000 | 429.08 / 472.0 | $0.162–$0.239 | $0.178–$0.263 |
| fresh | 16 | 1.0 | 10000/10,000 | 418.75 / 446.0 | $0.158–$0.233 | $0.168–$0.249 |

## Selection and verification

Eligible values: **[]**. Selected m: **None**. No target or seed was changed after results. Zero observed harmful accepts is a Monte Carlo requirement here, not a proof of zero population probability.

1,860,000 stream receipts verified, with 18,600 independent scalar/vector checks and ten focused tests covering the grid, scope admission, caps, guards and follow-up. Canonical v3 signature verification passes. All item-level records here are simulated; no real reserve items were opened.

Every harmful promotion was independently replayed through the public scoped scalar Process: 9 cases, all matching verdict, items and per-stratum counts/net/discordance. This targets the rare outcomes that determine qualification, beyond the first100-per-cell parity sample. [Rare-promotion audit](evidence/gate-v3_2-coverage-grid/harmful-promotion-scalar-audit.json).

Sources: [registration](evidence/gate-v3_2-coverage-grid/registration.json), [results](evidence/gate-v3_2-coverage-grid/result.json), [historical metric audit](evidence/gate-v3_2-coverage-grid/historical-metric-audit.json).
