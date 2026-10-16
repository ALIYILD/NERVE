# 130 — Gate v3.2 harmful acceptance: bounded-rate reformulation

This is an explicitly registered reformulation **after doc 129**, at the user's direction. Doc 129 and its completed L2 grid at `b97aabf` remain unchanged and will not be rerun. That grid failed its zero-observed-harmful target; this document does not retroactively relabel it as passing.

The replacement harmful acceptance requirement is **a one-sided 95% exact binomial upper bound ≤ 0.05% for each required harmful scenario**. A zero count at n = 10,000 itself establishes only an approximately 0.03% upper bound (1 − 0.05^(1/10,000)), not zero population risk. The new target expresses an estimable bounded rate rather than an impossible inference of zero risk from finite simulation.

## Prospective verification

Before seeing new results: fix **m = 14**, **100,000 streams per scenario**, fresh seed **2026102501**, and profile order **narrow-64, measured v5, broad-75**. Use the existing harmful fixture (conditional candidate win probability 0.35), unchanged simulator/scalar gate, primary cap 300, main cap 960, total cap 1,000, and unconditional 40-item dissenter follow-up. Preserve G1/G2 rules, scope floor **8%**, and all original scope qualifications from doc 129. The measured-v5 profile remains a dev plug-in assumption, not a certified population discordance lower bound.

For count k of n, report k, k/n and the one-sided Clopper–Pearson 95% upper bound `BetaQuantile(0.95; k+1,n-k)` (1 when k=n). All three profile bounds must pass separately. These are marginal bounds, not a simultaneous familywise 95% statement; common random numbers across profiles must not be pooled as independent replications. No additional seed search, optional stopping, threshold tuning or L2 grid rerun is permitted.

Replay the first three fresh harmful promotions, ordered by the registered profile order then stream index, through the public scalar `Process`. Save item-level phase transitions, primary e-value, coverage paths, G1/G2/risk outcome and exact vector/scalar comparisons. If fewer than three occur, report the shortfall rather than inventing cases or changing the seed.

Only if every bound holds, prepare the full-form unsigned v3.2 payload with m=14 and scope floor8%, bind the evidence/source hashes, and append a pending entry to `~/nerve-orchestration/signing-queue.json`. Queueing is not signing, activation or permission to sample holdout. If any bound fails, report and stop. Proceed to L4 only under the applicable verified signed gate and the existing study/admission rules.

Registration and results: `evidence/gate-v3_2-harmful-bound/`. This verification uses CPU simulations only: no model calls, pod operations or real reserve consumption.

## Results

At registration no payload was queued and no gate changed. The fixed fresh-seed verification subsequently completed: all three marginal bounds pass.

| Profile | Harmful accepts / streams | Rate | One-sided exact 95% upper |
| --- | ---: | ---: | ---: |
| narrow-64 | 3 / 100,000 | 0.003% | 0.007753472% |
| measured v5 | 1 / 100,000 | 0.001% | 0.004743776% |
| broad-75 | 0 / 100,000 | 0% | 0.002995687% |

Seed: 2026102501. Registration SHA256: `54cebe931c42194593cf858504600499b08a774ee1d1dc551c271615649263aa`. Counts, complete stream receipts and exact bounds are in [result.json](evidence/gate-v3_2-harmful-bound/result.json). Original L2 results remain failed under their original zero-count requirement; all original m=14 non-harmful criteria passed and are reused unchanged.

### Three harmful promotion replays

The prospectively selected narrow-64 stream indices 7131, 15855 and 23999 reproduce the vector outcomes exactly through the public scalar Process. Their primary e-values were respectively 20.76964862, 23.29808512 and 20.34682635; final item totals were 421, 426 and 455, each including 40 risk items.

All three used `pooled_acceptance_coverage_G1_G2_risk_pass`: a favorable random primary sequence crossed e≥20; both agreement strata reached at least 14 discordances and nonnegative net wins; the four other answer strata used the zero-discordance-in-60 coverage certificate; G1 observed no safety loss; the unconditional dissenter follow-up consisted of 40 both-correct ties and passed with net zero. These are rare statistical acceptances through the intended route, not bypasses. The silent/safety fixture assumptions limit generalization. Full per-item transitions and scalar/vector comparisons are in [the replay receipt](evidence/gate-v3_2-harmful-bound/three-harmful-promotion-replays.json).

### Signature preparation and L4

The qualifying reformulation permits preparation of the full unsigned v3.2 payload with m=14 and scope floor 8%, binding both the original L2 evidence and this fresh verification. Preparation and queueing confer no activation, candidate promotion or holdout authority. Canonical signed v3 remains in force until a valid human signature and activation of v3.2. L4 additionally requires a completed eligible broad candidate, fresh exclusive reserve, prospective study registration, fixed controls and risk follow-up, and offline replay; no existing consumed reserve may be reset or reused.
