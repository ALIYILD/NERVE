# Registered G1/G2 tolerance comparison

The user requested tolerance selection by simulation, superseding the preliminary zero-tolerance shelving decision in doc 116. This study registers t in {0,1,2} before outcome generation and does not prepare a signing payload unless a tolerance satisfies both selection requirements. All scores are synthetic; no model calls or real bank items are used.

Primary sampling is cyclic round-robin over strata with fewer than two discordant pairs; after every stratum is decidable it becomes ordinary round-robin. A balanced round-robin sensitivity is also registered. The next stratum depends only on prior tie/discordance indicators, never win direction, class or t. Full potential streams are shared across tolerances. This isolates tolerance from sampling outcomes and gives undecided strata priority. The score fixture assumes available synthetic observations; it does not establish availability in a finite sealed reserve.

The gate has nine strata, 100 total items, 75% ties, per-study alpha .05, bet .3, futility E<=.05 and at least three net wins. **G1** has zero tolerance: candidate correct count must never fall below always-abstain correct count in an observed stratum; its first violation is a terminal safety veto. **G2** is not decidable until a stratum has at least two discordant pairs. Once decidable, its first net incumbent advantage greater than t is a terminal regression veto. Undecided strata continue sampling; promotion requires every stratum decidable, both guards passing and E>=20. Ordering is G1, G2, futility, promotion. Exhaustion with undecided strata is insufficient_power_undecided, not a veto or a regression catch. These early-veto semantics are explicit choices, distinct from doc 116's recoverable count deficits.

Each scenario has 10,000 streams. Uniform good candidates have discordant win probabilities .85 and .90; neutral .50; harmful .35. The separate H0 seed generates another 10,000 neutral streams. As in round 2, joint correctness has probability .70 both-correct and .05 both-wrong; always-abstain is independent Bernoulli(.2). These are score-level fixtures, not faithful nine-stratum bank truth or a calibrated clinical safety model.

For the single-stratum regression scenario, the bad stratum rotates across the nine strata and has p=.30; the other eight have p=.91875. Thus equal-stratum overall p=(.30+8*.91875)/9=.85. Leaving the other strata at .85 would make overall p=.7889 and would not meet the user's requested overall effect. Schedule starting position rotates separately. Policies receive scores only, not scenario labels or the identity of the bad stratum.

A **false veto** is an actual G1 or G2 terminal veto on a uniformly good candidate. Futility and undecided exhaustion do not count. A **regression catch** requires an actual G2 veto naming the deliberately regressed stratum; vetoing a different stratum, a safety-only veto, or merely failing to promote receives no catch credit. Total nonpromotion is recorded separately. H0 false promotion is a per-study rate under the full gate, not across-study FWER.

Selection: choose the smallest t for which primary-schedule good acceptance at p=.85 is at least .80 and bad-stratum catch rate is at least .90. No tuning follows the results. If no t qualifies, register chosen_t=null, publish the full trade-off table, and stop without a payload. Nine CPU fixture tests passed before the registered run, including scalar/vector agreement, two-discordance admission, tolerance boundaries, safety priority, all-strata coverage and no false catch credit.

## Results and registered decision

**No t satisfies both conditions. Chosen t is null; no signing payload or canonical protected-path update is prepared.** The selection receipt records all rows and binds the exact registration/result hashes. Every percentage below has 10,000 streams per scenario as its denominator. False-veto columns exclude undecided/futility stops; catch requires a G2 veto identifying the bad stratum.

### Primary: undecided-stratum priority

| t | Good accept p=.85 | Good accept p=.90 | False veto p=.85 | False veto p=.90 | Bad-stratum catch | Neutral accept | Harmful accept | H0 false promotion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 57.17% | 71.23% | 36.89% | 24.71% | 37.75% | 0.34% | 0.00% | 0.31% |
| 1 | 58.90% | 71.84% | 33.46% | 23.69% | 36.76% | 0.39% | 0.00% | 0.37% |
| 2 | 67.61% | 77.50% | 20.16% | 16.84% | 4.27% | 0.52% | 0.00% | 0.46% |

### Sensitivity: balanced round-robin

| t | Good accept p=.85 | Good accept p=.90 | False veto p=.85 | False veto p=.90 | Bad-stratum catch | Neutral accept | Harmful accept | H0 false promotion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 7.52% | 9.88% | 43.05% | 29.06% | 41.90% | 0.03% | 0.00% | 0.04% |
| 1 | 8.79% | 10.65% | 32.25% | 22.94% | 34.55% | 0.03% | 0.00% | 0.06% |
| 2 | 10.33% | 11.51% | 20.65% | 17.20% | 15.39% | 0.04% | 0.00% | 0.06% |

The primary schedule makes all nine strata decidable within 100 potential items in **96.34%** of streams before applying vetoes/stopping, versus **14.13%** for balanced sampling. Thus priority sampling fixes much of the coverage limitation, but the joint guard targets still fail. With t=2 and p=.85, G1 vetoed 1,941/10,000 good streams and G2 vetoed another 75; good acceptance was 6,761/10,000. At t=0 the bad stratum was caught in 3,775/10,000 streams; at t=2 only 427/10,000. A tolerance of two permits both of a stratum's first two discordant observations to be incumbent wins, so decisibility alone does not imply sensitive regression detection.

Bad-stratum candidates were actually promoted in 36.25%, 37.20% and 66.91% of primary streams for t=0,1,2. Total nonpromotion was 63.75%, 62.80% and 33.09%; neither these values nor vetoes in unrelated strata were substituted for the stricter catch rate. This distinction prevents a low-power gate from appearing to detect regression merely by refusing everything.

No tolerance was retuned, no follow-up search was run, and no payload was produced. These failures apply to the registered synthetic score distribution, early-veto semantics and 100-item cap, not every possible guard design. G1 uses the inherited Bernoulli(.2) abstain-control fixture; results do not establish clinical safety or actual bank-v3 guard rates.

Public artifacts: `evidence/g1-g2-tolerance-v1-registration.json`, `evidence/g1-g2-tolerance-v1-result.json`, `evidence/g1-g2-tolerance-v1-selection.json` and `evidence/g1-g2-tolerance-v1-verification.json`. Nine tests passed; 186 scalar/vector fixture evaluations agreed; 36 scenario/tolerance cells reconciled. Zero model calls, no real reserve access, no signing or installation. The earlier preliminary source in `scientific_promotion_gate_v3.py` remains unselected and inactive; its separate zero-tolerance experiment is historical context, not a selected canonical gate.
