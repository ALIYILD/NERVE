# 126 — Gate v3.2 proposal: silent-stratum coverage

Gate v3.1 is withdrawn at the user’s instruction. Its historical evidence and unsigned payload remain preserved; no activation or signature occurred. Gate v3 remains canonical. Gate v3.2 is pre-registered research only and fails the narrow-candidate power target; no signing payload is prepared.

## Registration and interpretation

[Registration](evidence/gate-v3_2/registration.json) was written and source-hashed before simulation or new dev inference. Primary100, balanced all-nine sampling, main460 plus unconditional dissenter40, cap500, G1 zero tolerance and G2 t=0 are unchanged. Coverage on the six answer strata is ten discordances OR zero discordances in at least60 main observations. Safety strata remain structural ties under the recorded-zero-misfire fixture and G1; this fixture is not proof of population-zero safety errors.

The 64% and88% narrow tie rates apply within the two agreement strata; other answer strata are structural ties in these fixtures. Broad75% follows the signed simulation: overall75% ties across nine strata, hence37.5% discordance on each of six answer strata. The active regressed stratum has conditional win probability .30; other active strata .91875. Narrow and broad regression alternatives therefore have different pooled effects.

**Cap obstruction:** at most52 observations per stratum fit in460 balanced main items. Even500 main items would give at most56. The silent60 branch cannot fire under this schedule. The40 dissenter follow-up cannot supply answer-stratum coverage. No allocation change was silently introduced.

Registered seeds: main2026101801/H02026101802. Fresh seeds: main2026102201/H02026102202. Each scenario uses10,000 streams. Execution-order deviation: JSON key sorting made the fresh set execute before the original set; both sets and all scenarios were fixed and hashed before any results, with no tuning or selection between runs. Tables below present the requested original-then-fresh comparison.

## Results

All rates are percentages. Regressed means non-promotion by any route, not successful identification.

| Seed | Fixture | Good .85 | Good .90 | Regressed non-promotion | Neutral accept | Harmful accept | H0 promotion |
|---|---|---:|---:|---:|---:|---:|---:|
| registered | narrow_64 | 0.00 | 0.00 | 100.00 | 0.00 | 0.00 | 0.00 |
| registered | narrow_88 | 0.00 | 0.00 | 100.00 | 0.00 | 0.00 | 0.00 |
| registered | broad_75 | 85.18 | 95.03 | 92.12 | 0.13 | 0.00 | 0.19 |
| fresh | narrow_64 | 0.00 | 0.00 | 100.00 | 0.00 | 0.00 | 0.00 |
| fresh | narrow_88 | 0.00 | 0.00 | 100.00 | 0.00 | 0.00 | 0.00 |
| fresh | broad_75 | 84.43 | 94.70 | 91.85 | 0.07 | 0.00 | 0.11 |

Both broad rows meet the registered targets. Both narrow rows fail good-accept≥80%, with zero good promotions. Their100% regression non-promotion is vacuous protection from lack of power. G1 false veto is0 under the recorded-zero-misfire fixture.


There is also a primary-stage bottleneck: with only two active strata, 64% ties within them means92% ties overall under nine-stratum sampling; 88% within them means97.33% overall ties. At p=.85, original/fresh primary accepts are102/97 out of10,000 for64%, and0/0 for88%. All narrow primary acceptances then fail coverage. Thus merely making the60-item branch reachable would not establish80% power with the unchanged100-item primary.

| Seed | Fixture (good .85) | Primary accepts /10,000 | Coverage incomplete after acceptance | Mean total items |
|---|---|---:|---:|---:|
| registered | narrow_64 | 102 | 102 | 104.08 |
| registered | narrow_88 | 0 | 0 | 100.00 |
| registered | broad_75 | 8617 | 75 | 319.54 |
| fresh | narrow_64 | 97 | 97 | 103.88 |
| fresh | narrow_88 | 0 | 0 | 100.00 |
| fresh | broad_75 | 8564 | 87 | 318.39 |

## Small regressions in a nominally silent stratum

For each narrow fixture, one of the four otherwise silent answer strata is assigned per-item loss-only discordance of5% or10%, rotating across streams; the two active agreement strata retain p=.85. This is an absolute error increase on paired items, not a five-point change in conditional discordant win probability.

| Seed | Fixture | Silent loss rate | Non-promotion | Stratum identification |
|---|---|---:|---:|---:|
| registered | narrow_64 | 5% | 100.00% | 0.00% |
| registered | narrow_64 | 10% | 100.00% | 0.00% |
| registered | narrow_88 | 5% | 100.00% | 0.00% |
| registered | narrow_88 | 10% | 100.00% | 0.00% |
| fresh | narrow_64 | 5% | 100.00% | 0.00% |
| fresh | narrow_64 | 10% | 100.00% | 0.00% |
| fresh | narrow_88 | 5% | 100.00% | 0.00% |
| fresh | narrow_88 | 10% | 100.00% | 0.00% |

No stream earned a silent60 certificate. Therefore this run states **no ≤5% hidden-discordance bound**. If the fixed first60 observations were available and all tied, the marginal one-sided95% exact binomial upper bound would be4.8703%, approximated by3/60=5%. The probability of observing zero losses at true5%/10% loss rates would be4.607%/0.180%. These require independent stationary paired outcomes; they are neither equivalence proofs nor simultaneous guarantees across strata nor general anytime confidence sequences.

The hypothetical bound controls discordance incidence, not the conditional chance of a loss among discordances. A nonzero small regression can remain undetected.

## Verification and evidence

[Aggregate results](evidence/gate-v3_2/result.json) link deterministic compressed stream receipts and hashes for every scenario. The unchanged vector engine is valid here because the only new branch is unreachable under the unchanged cap;100 streams per cell were checked against the separate scalar v3.2 proposal,4,400 scalar comparisons total. Four boundary/G1/G2/cap tests passed. Source hashes were verified before simulations; canonical gate signature verification still succeeds. No reserve items were read for these simulations.

The registered100-item bank-v5 dev measurement and measured-rate resimulation are reported separately in doc127. No gate payload, signing or retention follows from these failed narrow-fixture targets.
