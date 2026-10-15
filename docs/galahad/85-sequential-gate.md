# Loop 40.2: non-canonical sequential gate, overnight v2

This is a CPU-only, score-level simulation. Nothing is signed, retained,
installed, or connected to a model. The canonical gate and registry are unchanged.
It supersedes neither the scientific policy gate nor the prior Loop 40.2 evidence.

## Registered method

The exact design and source hashes are written exclusively before outcome
creation. Seed 20261016; 200 proposals: 40 harmful, 60 neutral, 100 good.
Conditional win probabilities among discordant pairs are 0.35, 0.50, 0.65.
Candidate correctness is Bernoulli(p), incumbent correctness independently
Bernoulli(0.5); ties therefore occur. This is a synthetic fixture, not a fitted
model of NERVE behavior. Each proposal has 100 items in five balanced strata.

The primary e-process multiplies by 1.3 on a paired win, 0.7 on a paired loss,
and 1 on a tie. A fixed bet b=0.3 is registered, not learned from the stream.
Under the conditional null P(win | discordant, past) <= 0.5, the expected next
factor is <=1. Nonnegativity and Ville's inequality bound any threshold crossing
by alpha, including optional stopping. This mathematical statement requires
fresh conditionally valid outcomes; a wallet cannot repair adaptive reuse of
exposed holdout items. The implementation supports registered alpha up to 0.05;
this run reserves 0.05/200 = 0.00025 per study (threshold 4,000).

Promotion proposals also require all strata observed and net wins minus losses
at least 3. Doc 82 measured zero seed variance; three is the explicitly registered
minimum, not an empirically estimated nonzero noise band. A reverse e-process
in each stratum tests harm against always-abstain at threshold strata/alpha;
a crossing vetoes promotion. **Absence of a veto is not evidence of stratum
noninferiority.** Domain violations veto immediately. Futility E<=0.05 retains
the incumbent; reaching 100 items without passing is insufficient power. These
stops only restrict acceptance. Interrupted claimed outcomes return incomplete
infrastructure and are never redispatched.

The registration binds candidate identity, current deployed incumbent identity,
and the attestation that the comparison reverts only the candidate. Marginal
delta is (wins-losses)/items. In this simulation those identities are fixtures;
a future live adapter must enforce actual pipeline installation and reversion.
The gate never installs a candidate itself.

## Wallet and recovery

To respect the overnight rule that the alpha ledger is immutable once created,
all 200 reservations are sealed upfront in one exclusive, read-only, hash-chained
wallet. The reserved alpha is 0.05; no refund occurs after early termination.
Adding an unallocated study or changing a registration fails closed. Schedules
must have distinct item identities across studies. The ledger's externally
pinned SHA-256 is rechecked on use. Code is separate from this immutable state.

Claims and outcomes use a separate private SQLite/HMAC journal adapted from the
previous Loop 40.2 implementation (23719d1). A single authoritative journal path
is bound to each wallet/study. Transactions persist claims before outcomes;
restart replays authenticated outcomes, returns cached claims, and recomputes
exactly the same e-value. The simulation integrity key is explicitly public,
not a production signing key. Event edits and ordinary truncation are detected.
An independently stored expected journal head is needed to detect a coordinated
whole-database rollback. The simulation tests that protection, but does not
provide a trusted checkpoint service; an unanchored reopen cannot detect such
rollback. Same-user/root compromise is not addressed by this fixture.

## Comparators and interpretation

Arm A calls the actual `run_scientific_runpod_gate.aggregate` predicate: candidate
strictly beats all three controls overall, never below abstain within a stratum,
20 items in each of five strata. It deliberately reuses one synthetic bank of
100 item/control identities across 200 proposals, without an alpha wallet.
Arm B uses fresh independent paired samples and the sequential wallet gate.
A vs B differs in correlation and reuse, so its difference cannot be attributed
solely to the gate. A third sensitivity calculation applies the exact current
slice predicate to the complete fresh Arm B streams. Arm A and sensitivity each
consume 20,000 item evaluations. This simulation does not authorize reuse in the
canonical gate.

Zero of 40 harmful accepts would mean an observed 0%, with one-sided exact 95%
upper bound about 7.2%; it would not demonstrate a population harmful-accept
rate below 1%. Good and neutral acceptance are reported alongside harmful
acceptance and item savings so low power cannot be hidden by a favorable target.

## Sources and attribution

The adoption plan calls the first source Lewis, ICML 2026. Its supplied
[ICML page](https://icml.cc/virtual/2026/82618) could not be retrieved during this
run. The indexed primary [Scientific CI/CD manuscript on OpenReview](https://openreview.net/pdf/37e7a378692946058ce923354801dfc34a4bcb55.pdf)
confirms the title and the e-value/alpha-spending architecture, but the retrieved
abstract is anonymous and a direct open encounters a browser challenge.
The author and venue attribution therefore remain unverified here. This is
NERVE's registered synthetic demonstration, **not a replication** of that paper.

[Nakajima, Regimes, sections 3.5 and 8.2](https://arxiv.org/html/2606.10241v1)
describes marginal comparison against the current pipeline with only the
candidate reverted, and proposes a noise-aware plateau threshold after observing
over-promotion. Our minimum-three rule is the overnight plan's adaptation, not
an independently replicated result from Regimes.

## Results and reproduction

**The nominal target was met, but the sequential gate accepted zero of 100 good
proposals. This does not demonstrate a useful promotion gate.** With the frozen
alpha allocation and 100-item cap, its power is inadequate for this simulation.
No parameter or seed was changed after results, and no second simulation was run.

| Gate / sampling | Harmful accepted | Neutral accepted | Good accepted | Items consumed |
|---|---:|---:|---:|---:|
| Current slice, naive reuse | 0/40 (0%) | 18/60 (30%) | 100/100 (100%) | 20,000 |
| Sequential, frozen wallet | 0/40 (0%) | 0/60 (0%) | **0/100 (0%)** | 16,386 |
| Current slice, matched fresh sensitivity | 2/40 (5%) | 30/60 (50%) | 97/100 (97%) | 20,000 |

The sequential run used 18.07% fewer item evaluations; 126 proposals exhausted
the item budget with insufficient power and 74 retained the incumbent for
futility. Its observed harmful rate is below 1%, but so is the naive reused-bank
arm's rate in this seed. **There is no demonstrated harmful-accept improvement
over the requested naive-reuse comparator.** The matched sensitivity has a
different result and is reported separately, not substituted as the primary arm.
The 0/40 one-sided exact 95% upper bound is 7.2158%, not below 1%.

All 200 journals resumed with identical reports and no repeated dispatch.
The immutable wallet's final hash matched its creation hash and the conductor's
independent protection receipt. Simulation runtime: 229.393 seconds; zero model
calls. The alpha wallet reserved 0.05 in full before any outcome was generated.

The 18 focused tests passed in 9.620 seconds. The fixed-seed 10,000-stream H0
check (200-item horizon, alpha=0.05, no futility) crossed 436 times (4.36%). This
is empirical validation under the simulated null; the general guarantee rests
on the conditional-null supermartingale argument above. Tests also cover early
H1 stopping, ties, plateau, stratum veto, futility, exhaustion, source identity,
resume, interrupted claims, authenticated-history tampering, wallet tampering,
and whole-database rollback against an independently retained head. These are
**focused test results, not a claim that the full repository suite passed**.

Public receipts: `evidence/sequential-gate-sim-v1.json`, registration,
alpha-wallet, test JSON/log, simulation log, and verification JSON alongside it.
The durable private simulation directory is
`/Users/aliyildirim/nerve-research-runs/sequential-gate-overnight-20261016`.
Registration SHA-256: `57d910986dfb528f4486cc19557dbb3381f4d3994c5d9a74a49a1358aa112dfb`.
Wallet SHA-256: `b23bf1fe63be574d9d1e679442a076fa7b923548b3b5cdd5bc6c605b58762f57`.
A future power redesign needs a new registration; it is not performed tonight.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p test_scientific_sequential_gate.py -v
PYTHONPATH=src python3 scripts/simulate_sequential_gate.py /absolute/new/private/output
```

The output directory must be new; registration and the wallet are exclusive.
No retry with another seed or changed parameters is part of this study.
