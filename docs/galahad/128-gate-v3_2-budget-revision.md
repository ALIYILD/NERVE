# 128 — Gate v3.2 budget revision: primary 300, targeted coverage, cap 800

**Targets fail; no signing payload is prepared. Research proposal only.** All requested profiles were simulated, with zero model calls, no pod operations and no reserve access. No signature, installation or retention occurred. The canonical gate remains signed v3. Historical v3.1 remains withdrawn.

## Frozen design and execution

The [registration](evidence/gate-v3_2-budget/registration.json) was source-hashed before any simulation results. Original seeds 2026101801 (main) and 2026101802 (H0) ran first. New seeds 2026102301 and 2026102302 ran second, with no intervening tuning. Every cell contains 10,000 streams.

Primary sampling remains balanced across all nine strata, with e ≥ 20 or a 300-item cap. The existing bet 0.3, futility e ≤ 0.05, minimum net wins 3 and all-nine-observed conditions are retained. Acceptance is latched: coverage outcomes do not update the pooled e-process or rescue a failed primary stage.

After primary acceptance, sample only uncovered answer strata, selecting the least-observed first and resolving equal counts by the pre-registered rotated answer order. Primary observations count toward coverage. Coverage is ≥ 10 discordances OR zero discordances in ≥ 60 observations. A covered stratum drops out. Main sampling is capped at 760, reserving 40 unconditional dissenter follow-up items inside the 800 total cap. G1 is zero-tolerance; G2 is a single-stage zero-net-loss guard on complete coverage. Incomplete coverage gives insufficient_power.

G1 uses the recorded v3/v4 zero-misfire fixture; its false-veto rate is zero in this simulation, not a population safety guarantee. The dissenter follow-up remains structural both-correct ties under that fixture.

Broad 75% ties means 75% overall across nine strata, hence 37.5% discordance within each of six answer strata, matching historical simulations. Narrow 64%/88% ties are within the two agreement strata; all other strata are structural ties in those fixtures. The measured profile uses agreement discordance 22% and 64%, separately; zero elsewhere is the historical plug-in assumption, not proof.

The regressed alternative sets one active answer stratum to p = 0.30 among discordances and the other active strata to 0.91875. The bad stratum rotates. This has a different pooled effect in two-active and six-active fixtures; no claim of equal pooled effect is made. Neutral/H0 use p = 0.5; harmful uses p = 0.35.

Qualification requires good acceptance ≥ 80% at p = 0.85, regressed non-promotion ≥ 90%, H0 false promotion ≤ 5%, and zero observed harmful accepts, in every profile in both seed sets. No averaging across profiles. These are Monte Carlo point estimates; zero observed harmful accepts is not a proof of zero population probability.

## Target table

Percentages; regressed means non-promotion by any route, not localization.

| Seeds | Profile | Good .85 | Good .90 | Regressed non-promotion | Neutral accept | Harmful accept | H0 promotion | Pass all |
|---|---|---:|---:|---:|---:|---:|---:|---|
| registered | broad_75 | 99.17 | 99.92 | 85.29 | 1.18 | 0.00 | 1.47 | False |
| registered | narrow_64 | 83.01 | 94.43 | 96.46 | 0.51 | 0.01 | 0.60 | False |
| registered | narrow_88 | 1.88 | 3.53 | 99.97 | 0.00 | 0.00 | 0.00 | False |
| registered | measured | 93.18 | 98.69 | 93.01 | 0.87 | 0.00 | 0.96 | True |
| fresh | broad_75 | 99.02 | 99.89 | 85.09 | 1.22 | 0.00 | 1.43 | False |
| fresh | narrow_64 | 82.86 | 94.36 | 96.34 | 0.63 | 0.01 | 0.54 | False |
| fresh | narrow_88 | 2.08 | 3.74 | 99.97 | 0.00 | 0.00 | 0.00 | False |
| fresh | measured | 93.38 | 98.80 | 93.25 | 0.87 | 0.00 | 0.79 | True |

The adaptive budget fixes silent-stratum coverage and gives the measured pair adequate simulated power. It does not qualify the general design: the broad regressed alternative is promoted about 15% of the time, the narrow 88%-tie primary remains unpowered, and the narrow 64%-tie harmful class has one acceptance in each seed set. Extending the primary stage removes some non-promotions that previously contributed to the regression metric; unchanged G2 at ten discordances does not compensate in the broad fixture. No thresholds or sample sizes were tuned after observing this.

## Measured pair, p = 1.0 and p = 0.85

| Seeds | Conditional p | Accepts /10,000 | Primary accepts | Incomplete coverage | Mean / p90 items | Mean cost | p90 cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| registered | 1.0 | 10000 | 10000 | 0 | 382.27 / 407.0 | $0.144–$0.213 | $0.153–$0.227 |
| registered | 0.85 | 9318 | 9327 | 0 | 398.30 / 441.0 | $0.150–$0.222 | $0.166–$0.246 |
| fresh | 1.0 | 10000 | 10000 | 0 | 382.08 / 408.0 | $0.144–$0.213 | $0.154–$0.227 |
| fresh | 0.85 | 9338 | 9345 | 0 | 398.32 / 442.0 | $0.150–$0.222 | $0.167–$0.246 |

## Silent-stratum regressions and bound activation

A nominally silent answer stratum has 5% or 10% loss-only discordance per item; the two active agreement strata retain p = 0.85. The selected silent stratum rotates across the four otherwise silent answer strata. These are absolute per-item regressions, not reductions in conditional win probability.

Bound activation below refers specifically to the deliberately regressed stratum, not the other genuinely silent strata. First-60 certificates and terminal silent coverage are separately recorded in every stream. Rates use all 10,000 proposed studies as denominator, including primary failures.

| Seeds | Profile | Silent loss | Non-promotion | Identified | First-60 certificates | Terminal bound activated | Promotions with that bound |
|---|---|---:|---:|---:|---:|---:|---:|
| registered | narrow_64 | 5% | 96.20% | 65.93% | 380/10,000 | 380/10,000 | 380/10,000 |
| registered | narrow_64 | 10% | 99.83% | 54.85% | 17/10,000 | 17/10,000 | 17/10,000 |
| registered | narrow_88 | 5% | 99.89% | 0.56% | 11/10,000 | 11/10,000 | 11/10,000 |
| registered | narrow_88 | 10% | 100.00% | 0.20% | 0/10,000 | 0/10,000 | 0/10,000 |
| registered | measured | 5% | 95.12% | 80.21% | 488/10,000 | 488/10,000 | 488/10,000 |
| registered | measured | 10% | 99.81% | 73.47% | 19/10,000 | 19/10,000 | 19/10,000 |
| fresh | narrow_64 | 5% | 96.00% | 65.00% | 400/10,000 | 400/10,000 | 400/10,000 |
| fresh | narrow_64 | 10% | 99.81% | 52.77% | 19/10,000 | 19/10,000 | 19/10,000 |
| fresh | narrow_88 | 5% | 99.88% | 0.71% | 12/10,000 | 12/10,000 | 12/10,000 |
| fresh | narrow_88 | 10% | 99.99% | 0.22% | 1/10,000 | 1/10,000 | 1/10,000 |
| fresh | measured | 5% | 95.68% | 81.10% | 432/10,000 | 432/10,000 | 432/10,000 |
| fresh | measured | 10% | 99.80% | 73.92% | 20/10,000 | 20/10,000 | 20/10,000 |

When the silent branch activates, the stated upper bound is approximately 5% (rule of three), or exactly 4.8703% at one-sided 95% confidence for a fixed first 60 IID stationary per-stratum paired outcomes. It is a marginal incidence bound, not equivalence, not a simultaneous guarantee across strata and not a general anytime confidence sequence. The probability of zero observations of a real 5%/10% loss process in 60 items is 4.607%/0.180%, before accounting for the chance the study reaches those 60 items. A true small regression can therefore activate the bound and occasionally be promoted. If fewer than 60 observations are collected, no such bound is stated.

## Items and projected cost for every class

All proposals are included, including failed primary stages and follow-ups. Dollar ranges use historical 2.3–3.4 seconds per item and A40 $0.59/hour. These are hypothetical all-arm study projections, not billed simulation costs; this work used zero GPU/model calls. Machine-readable results also include mean/p90 minutes.

| Seeds | Profile | Class | Mean items | p90 items | Mean cost | p90 cost |
|---|---|---|---:|---:|---:|---:|
| registered | broad_75 | good_085 | 223.82 | 251.0 | $0.084–$0.125 | $0.095–$0.140 |
| registered | broad_75 | good_090 | 220.05 | 246.0 | $0.083–$0.123 | $0.093–$0.137 |
| registered | broad_75 | regression | 227.34 | 256.0 | $0.086–$0.127 | $0.096–$0.143 |
| registered | broad_75 | neutral | 200.60 | 300.0 | $0.076–$0.112 | $0.113–$0.167 |
| registered | broad_75 | harmful | 90.19 | 145.1 | $0.034–$0.050 | $0.055–$0.081 |
| registered | broad_75 | H0 | 199.91 | 300.0 | $0.075–$0.111 | $0.113–$0.167 |
| registered | narrow_64 | good_085 | 385.40 | 434.0 | $0.145–$0.215 | $0.164–$0.242 |
| registered | narrow_64 | good_090 | 391.59 | 429.0 | $0.148–$0.218 | $0.162–$0.239 |
| registered | narrow_64 | regression | 305.29 | 300.0 | $0.115–$0.170 | $0.113–$0.167 |
| registered | narrow_64 | neutral | 289.10 | 300.0 | $0.109–$0.161 | $0.113–$0.167 |
| registered | narrow_64 | harmful | 238.70 | 300.0 | $0.090–$0.133 | $0.113–$0.167 |
| registered | narrow_64 | H0 | 288.98 | 300.0 | $0.109–$0.161 | $0.113–$0.167 |
| registered | narrow_64 | silent_regression_05 | 467.28 | 613.0 | $0.176–$0.260 | $0.231–$0.342 |
| registered | narrow_64 | silent_regression_10 | 384.34 | 486.0 | $0.145–$0.214 | $0.183–$0.271 |
| registered | narrow_88 | good_085 | 303.54 | 300.0 | $0.114–$0.169 | $0.113–$0.167 |
| registered | narrow_88 | good_090 | 306.74 | 300.0 | $0.116–$0.171 | $0.113–$0.167 |
| registered | narrow_88 | regression | 300.08 | 300.0 | $0.113–$0.167 | $0.113–$0.167 |
| registered | narrow_88 | neutral | 299.88 | 300.0 | $0.113–$0.167 | $0.113–$0.167 |
| registered | narrow_88 | harmful | 298.85 | 300.0 | $0.113–$0.167 | $0.113–$0.167 |
| registered | narrow_88 | H0 | 299.84 | 300.0 | $0.113–$0.167 | $0.113–$0.167 |
| registered | narrow_88 | silent_regression_05 | 302.14 | 300.0 | $0.114–$0.168 | $0.113–$0.167 |
| registered | narrow_88 | silent_regression_10 | 300.41 | 300.0 | $0.113–$0.167 | $0.113–$0.167 |
| registered | measured | good_085 | 398.30 | 441.0 | $0.150–$0.222 | $0.166–$0.246 |
| registered | measured | good_090 | 395.75 | 431.0 | $0.149–$0.221 | $0.162–$0.240 |
| registered | measured | never_worse | 382.27 | 407.0 | $0.144–$0.213 | $0.153–$0.227 |
| registered | measured | regression | 326.33 | 437.0 | $0.123–$0.182 | $0.165–$0.244 |
| registered | measured | neutral | 283.46 | 300.0 | $0.107–$0.158 | $0.113–$0.167 |
| registered | measured | harmful | 214.47 | 300.0 | $0.081–$0.120 | $0.113–$0.167 |
| registered | measured | H0 | 282.48 | 300.0 | $0.106–$0.157 | $0.113–$0.167 |
| registered | measured | silent_regression_05 | 505.24 | 624.0 | $0.190–$0.282 | $0.235–$0.348 |
| registered | measured | silent_regression_10 | 415.19 | 499.0 | $0.157–$0.231 | $0.188–$0.278 |
| fresh | broad_75 | good_085 | 224.42 | 251.0 | $0.085–$0.125 | $0.095–$0.140 |
| fresh | broad_75 | good_090 | 220.69 | 246.0 | $0.083–$0.123 | $0.093–$0.137 |
| fresh | broad_75 | regression | 227.94 | 256.0 | $0.086–$0.127 | $0.096–$0.143 |
| fresh | broad_75 | neutral | 199.66 | 300.0 | $0.075–$0.111 | $0.113–$0.167 |
| fresh | broad_75 | harmful | 90.10 | 146.0 | $0.034–$0.050 | $0.055–$0.081 |
| fresh | broad_75 | H0 | 199.55 | 300.0 | $0.075–$0.111 | $0.113–$0.167 |
| fresh | narrow_64 | good_085 | 385.42 | 434.0 | $0.145–$0.215 | $0.164–$0.242 |
| fresh | narrow_64 | good_090 | 391.76 | 430.0 | $0.148–$0.218 | $0.162–$0.240 |
| fresh | narrow_64 | regression | 305.35 | 300.0 | $0.115–$0.170 | $0.113–$0.167 |
| fresh | narrow_64 | neutral | 289.26 | 300.0 | $0.109–$0.161 | $0.113–$0.167 |
| fresh | narrow_64 | harmful | 238.03 | 300.0 | $0.090–$0.133 | $0.113–$0.167 |
| fresh | narrow_64 | H0 | 288.85 | 300.0 | $0.109–$0.161 | $0.113–$0.167 |
| fresh | narrow_64 | silent_regression_05 | 464.89 | 612.0 | $0.175–$0.259 | $0.231–$0.341 |
| fresh | narrow_64 | silent_regression_10 | 380.55 | 485.0 | $0.143–$0.212 | $0.183–$0.270 |
| fresh | narrow_88 | good_085 | 303.95 | 300.0 | $0.115–$0.169 | $0.113–$0.167 |
| fresh | narrow_88 | good_090 | 307.09 | 300.0 | $0.116–$0.171 | $0.113–$0.167 |
| fresh | narrow_88 | regression | 300.07 | 300.0 | $0.113–$0.167 | $0.113–$0.167 |
| fresh | narrow_88 | neutral | 299.87 | 300.0 | $0.113–$0.167 | $0.113–$0.167 |
| fresh | narrow_88 | harmful | 298.70 | 300.0 | $0.113–$0.166 | $0.113–$0.167 |
| fresh | narrow_88 | H0 | 299.89 | 300.0 | $0.113–$0.167 | $0.113–$0.167 |
| fresh | narrow_88 | silent_regression_05 | 302.70 | 300.0 | $0.114–$0.169 | $0.113–$0.167 |
| fresh | narrow_88 | silent_regression_10 | 300.49 | 300.0 | $0.113–$0.167 | $0.113–$0.167 |
| fresh | measured | good_085 | 398.32 | 442.0 | $0.150–$0.222 | $0.167–$0.246 |
| fresh | measured | good_090 | 395.54 | 431.0 | $0.149–$0.220 | $0.162–$0.240 |
| fresh | measured | never_worse | 382.08 | 408.0 | $0.144–$0.213 | $0.154–$0.227 |
| fresh | measured | regression | 326.25 | 437.0 | $0.123–$0.182 | $0.165–$0.244 |
| fresh | measured | neutral | 282.45 | 300.0 | $0.106–$0.157 | $0.113–$0.167 |
| fresh | measured | harmful | 212.81 | 300.0 | $0.080–$0.119 | $0.113–$0.167 |
| fresh | measured | H0 | 282.24 | 300.0 | $0.106–$0.157 | $0.113–$0.167 |
| fresh | measured | silent_regression_05 | 507.06 | 626.0 | $0.191–$0.283 | $0.236–$0.349 |
| fresh | measured | silent_regression_10 | 415.82 | 500.0 | $0.157–$0.232 | $0.188–$0.279 |

## Verification and disposition

620,000 simulated streams across 62 cells were verified against receipt hashes and aggregate counts. Each cell includes 100 independent scalar/vector parity checks, 6,200 total, covering scheduling, counts, discordance, net, primary acceptance, coverage, promotion and items. Six focused tests passed for primary cap, total cap including follow-up, adaptive silent coverage, branch boundaries, G1, G2 and follow-up safety. Canonical v3 signature verification passes.

All target cells qualify: **False**. **No signing payload is prepared.** The failed profiles and measured-pair reachability are preserved without changing the gate after observing them.

Evidence: [registration](evidence/gate-v3_2-budget/registration.json), [full results and compressed stream receipt hashes](evidence/gate-v3_2-budget/result.json). Real bank-v5 dev measurements remain those of [doc 127](127-bank-v5-dev-and-v3_2-measured-power.md); no new real data were consumed.
