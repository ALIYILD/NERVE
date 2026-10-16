# Sequential gate round 2: effect size, ties and fresh-item alpha

**The registered revised gate meets the requested observed power threshold on this synthetic fixture: 85/100, 94/100 and 99/100 good accepts at discordant win probabilities 0.85, 0.90 and 0.95. It remains uninstalled, unsigned and non-canonical.** The 0.65 class remains weak at 11/100. No seed search or post-outcome parameter changes were made. This is simulation evidence, not a measured result on the bank-v3 reserve or real text.

## Design and provenance

The exclusive source-hashed registration preceded every research draw and the full power calculations. Seed 2026101703 fixes four separate 200-proposal scenarios (40 harmful, 60 neutral, 100 good each); all scenarios share the same uniform draws and labels/order, changing only good-class p. Harmful p=0.35, neutral p=0.5. Policies never receive class labels. Both gate comparators consume the identical fresh paired scores and controls. Historical naive-reuse results are preserved separately in doc 114, whose full ablation table now includes neutral acceptance without rerunning that experiment.

The requested tie probability is 0.75. We set P(both correct)=0.70, P(both wrong)=0.05, P(candidate-only correct)=0.25p and P(incumbent-only correct)=0.25(1-p). At p=0.92 these reproduce the published 0.93/0.72 accuracy marginals. This is a compatible synthetic calibration, not identification of the actual discordant count or conditional win probability from aggregate totals. No private paired holdout data were opened. The five-stratum score fixture, abstain-control probability 0.2 and random-control probability 0.15 remain the simulation's setup; this is not the nine-stratum bank itself.

The revised gate keeps bet=0.3, futility E<=0.05, minimum three net wins, all-strata coverage, reverse-stratum veto alpha=0.00025 and the 100-item cap. Fresh items receive per-study alpha=0.05 without spending or earning reuse wealth. Full planned item IDs are reserved before outcomes so a later overlap cannot be called fresh merely because a study stopped early. These are per-study guarantees; no 5% family-wise guarantee across all 200 fresh studies is claimed.

Only overlapping item sets enter alpha-investing: initial wealth 0.05, registered spend phi=min(0.1W,0.05/0.95), study alpha=min(0.05,phi/(1+phi)), and promotion credit phi+0.05, with zero credit otherwise. The debit/refund formulation implements the standard nonrejection-cost/rejection-bonus rule; the 10% spending fraction is a chosen schedule, not a unique universal standard. Fresh promotions do not replenish reuse wealth. No simulation study here reused items; the reuse path was tested with isolated fixtures. A new conditional-null validity justification is required for actual reuse, and the research policy refuses uncertified reuse. Alpha-investing does not by itself make previously exposed outcomes honest conditional tests: see [Foster and Stine](https://faculty.wharton.upenn.edu/wp-content/uploads/2011/11/Alpha-investing.pdf). No reserve adapter was installed or real items consumed.

## E-process alone: exact power

E starts at one, multiplies by 1.3 on a discordant win, 0.7 on a discordant loss and one on a tie. No wallet, plateau, futility or stratum veto is used for this grid. Terminal P(E_n>=20) is calculated by a binomial tail; anytime P(max E_k>=20, k<=n) by absorbing-state recursion. Ties do not change power conditional on a fixed number of discordant pairs, but increase total item cost: expected items are four times the discordant count. Exactly 25 discordant pairs is not the same as a fixed cap of 100 total items.

Each cell is **terminal / anytime percentage**.

| p among discordant | 5 pairs | 10 pairs | 25 pairs | 50 pairs | 100 pairs |
|---|---:|---:|---:|---:|---:|
| 0.6 | 0.00 / 0.00 | 0.00 / 0.00 | 2.94 / 5.41 | 15.61 / 23.09 | 30.68 / 47.43 |
| 0.7 | 0.00 / 0.00 | 0.00 / 0.00 | 19.35 / 26.46 | 68.39 / 75.20 | 94.70 / 97.29 |
| 0.8 | 0.00 / 0.00 | 0.00 / 0.00 | 61.67 / 68.77 | 98.56 / 99.03 | 100.00 / 100.00 |
| 0.9 | 0.00 / 0.00 | 0.00 / 0.00 | 96.66 / 97.62 | 100.00 / 100.00 | 100.00 / 100.00 |
| 0.95 | 0.00 / 0.00 | 0.00 / 0.00 | 99.88 / 99.92 | 100.00 / 100.00 | 100.00 / 100.00 |
| Expected total items | 20 | 40 | 100 | 200 | 400 |

Rounded 100.00% entries are not claims of certainty. Fewer than twelve discordant pairs cannot reach 20 even with all wins at this bet.

For a genuine 100-total-item cap with random 75% ties, exact recursion including futility and plateau gives the following e-process crossing probabilities. This calculation omits the reverse-stratum veto and hence is an **upper bound on full-gate power**, not a full-gate guarantee. All-strata coverage is achieved before a crossing is possible in this round-robin fixture.

| p among discordant | Exact 100-item crossing probability | Expected items |
|---|---:|---:|
| 0.65 | 14.4972% | 96.3958 |
| 0.85 | 85.3653% | 70.4614 |
| 0.9 | 95.3552% | 61.6610 |
| 0.95 | 99.1910% | 53.9424 |

## Paired 200-proposal scenarios

Counts have denominators 40 harmful, 60 neutral and 100 good per scenario. Item consumption includes every class. The slice predicate uses all 100 items; the sequential gate may stop early. The same harmful/neutral draws are shared across scenarios, so repeated counts are not independent replications.

| Good-class p | Gate | Harmful accepted | Neutral accepted | Good accepted | Items |
|---|---|---:|---:|---:|---:|
| 0.65 | Slice, matched fresh | 1/40 (2.50%) | 26/60 (43.33%) | 92/100 (92%) | 20,000 |
| 0.65 | Revised sequential | 0/40 (0.00%) | 1/60 (1.67%) | 11/100 (11%) | 18,329 |
| 0.85 | Slice, matched fresh | 1/40 (2.50%) | 26/60 (43.33%) | 100/100 (100%) | 20,000 |
| 0.85 | Revised sequential | 0/40 (0.00%) | 1/60 (1.67%) | 85/100 (85%) | 15,679 |
| 0.9 | Slice, matched fresh | 1/40 (2.50%) | 26/60 (43.33%) | 100/100 (100%) | 20,000 |
| 0.9 | Revised sequential | 0/40 (0.00%) | 1/60 (1.67%) | 94/100 (94%) | 14,711 |
| 0.95 | Slice, matched fresh | 1/40 (2.50%) | 26/60 (43.33%) | 100/100 (100%) | 20,000 |
| 0.95 | Revised sequential | 0/40 (0.00%) | 1/60 (1.67%) | 99/100 (99%) | 13,851 |

## H0 and decision

The separate 10,000-stream null test uses seed 2026101704, p_discordant=0.5, the same 75% tie fixture, the actual 100-total-item cap and both actual gate predicates on identical streams. **Slice: 4,718/10,000 = 47.18%; revised sequential: 50/10,000 = 0.50%.** The slice predicate requires a strict count advantage, not a 5%-level significance test; do not attach an unimplemented alpha guarantee to it. The revised gate's observed per-study rate is below its alpha=5%. These are not the previous 200-discordant-item/no-futility diagnostics and not all-null portfolio FWER estimates.

At p>=0.85 the revised gate meets this run's observed targets: at least 80% good acceptance, 0/40 harmful acceptance, fewer than 20,000 items and H0 below alpha. The shelving trigger is not met. This does not prove population power >=80% from 85/100, or population harmful acceptance <=1% from 0/40. The exact e-process calculation helps explain feasibility but does not replace validation of the full gate. No additional tuning or real reserve evaluation follows automatically. Nothing is signable or canonical without explicit full-form authorization and the outstanding real-data/reuse validity work.

Nine CPU fixture tests passed. An independent binomial-tail calculation checked all 25 terminal-power cells, probability mass reconciled for all four 100-item recursions, all 800 study receipts reconciled with their aggregate counts/costs, and every registered source hash remained unchanged. Zero model calls, no reserve access, no signing or installation. Completed within the one-day timebox.

Public receipts: `evidence/sequential-round2-v1-registration.json`, `evidence/sequential-round2-v1-result.json`, `evidence/sequential-round2-v1-verification.json`. Reproduction: `python3 scripts/study_sequential_round2.py /absolute/new/output` (exclusive output directory). Registration SHA: `119e247f52f742ce9c28eb535083cf8745dd4db12e40a788543bf22e40ced7a5`.
