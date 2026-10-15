# Loop 40.2: unsigned sequential gate v1

This adds an independent simulation-only gate version. It does not replace or
import into the current slice gate, authorize a promotion, open reserve/holdout,
or call any model. The user explicitly authorized this CPU-only build before the
Galahad holdout verdict. Human review and a signed live adapter remain required.

The local specification is Galahad's
`docs/galahad/plans/external-methods-adoption-source.md`, Loop 40.2, attributed there
to Lewis (anytime-valid testing and alpha spending) and Nakajima/Regimes (plateau
and marginal delta). This is a NERVE synthetic demonstration, not an exact
replication of the cited paper. Transactional journal mechanics are adapted from
Galahad's staged `external_methods/gate.py`; the prior workflow's normal-test
comparator was not used.

## Registered design and results

The fixed seed, 200 proposals (exactly 40 harmful), probabilities, alpha
allocations, bet, stopping bounds, dev noise fixture and 100-item budget were
written exclusively before generating outcomes. No outcome-based tuning was
performed. Every study reserves alpha 0.00025 from a total wallet of 0.05 before
claiming its first item. The simulated dev deltas [0.38, 0.40, 0.42] calibrate the
plateau as `max(1, ceil(2 * sample_sd * item_budget))`; these are fixtures, not v3
measurements. Stratified rounds shuffle the five strata with registered seeds.

| Primary matched-stream experiment | Harmful accepted | Beneficial accepted | Item evaluations |
|---|---:|---:|---:|
| Current slice decision | 5/40 (12.5%) | 160/160 (100%) | 20,000 |
| Sequential wallet gate | 0/40 (0% observed) | 160/160 (100%) | 6,590 |

The observed targets are met: below 1% harmful acceptance and 67.05% fewer item
evaluations. All harmful proposals stopped for futility; all beneficial proposals
became exploratory review results. Zero model calls; byte-identical aggregate
verdicts on restart. This does **not** prove a population error rate below 1%:
zero of 40 harmful trials has a one-sided exact 95% upper bound of about 7.2%.

The primary experiment uses identical paired score streams for both decisions,
with fresh independent synthetic items per proposal. Its incumbent is the
complement of candidate correctness, an intentionally simple discordant-pair
fixture, not a claim about a deployed model's absolute accuracy. The fixed-slice
predicate is copied from `scientific_v3_holdout.aggregate`: all five strata have
20 items, candidate total strictly exceeds incumbent, abstain and random, and no
stratum scores below abstain. The slice's Wilson intervals are descriptive and
are not substituted with a significance test.

A separately preregistered supplemental experiment explicitly reuses the same
100-item bank and incumbent/control scores for all 200 proposals, without an
alpha wallet. It accepts 6/40 harmful (15%) and 160/160 beneficial proposals,
consuming 20,000 evaluations of 100 unique items. Its pairing/correlation differs
from the primary experiment; differences cannot be attributed solely to the gate.
There is no claim that a sequential e-process permits arbitrary adaptive reuse
of exposed items. A matched adaptive bank-reuse replication remains unmeasured.

## Statistical and governance contract

A registered fixed bet b multiplies the paired e-process by 1+b on a win, 1-b on
a loss and one on a tie. Under conditional discordant-win probability <= 1/2,
this is a nonnegative test supermartingale. Optional stopping is valid under
that assumption. Each global comparison (incumbent, abstain, random) must cross
1/alpha; requiring all three is an intersection-union guard and does not require
splitting the primary alpha among them. Reverse abstain e-processes latch a
stratum veto at `number_of_strata / alpha`. Futility may reject early but cannot
create a false acceptance. Exhausted item budgets return insufficient power.

Registration binds the exact schedule, bank, candidate and currently deployed
incumbent identity; it requires the attestation that only the candidate is
reverted in the comparison. Marginal delta is net paired wins divided by items.
These identities and measurements are synthetic attestations here. A real host
must verify them rather than accepting a candidate's self-assertions.

SQLite transactions and HMAC-linked events protect wallet reservations, claims,
and outcomes. The ledger is reverified before each study. Private directories
and databases use modes 0700 and 0600. Public artifacts contain aggregates only.
A claimed item never redispatches: completed claims return cached; an interrupted
claim returns incomplete infrastructure until a trusted cached response resolves
it. No response means the run stays incomplete, never repeated inference. The
stored schedule prevents skipped/reordered items. Outcomes and e-values are
recomputed from authenticated history on restart.

HMAC history plus the same-database checkpoint detect event edits and ordinary
truncation. Coordinated rollback of both tables requires a trusted external
anchor. `expected_ledger_head` checks such an anchor on reopen, with a test for
whole-database deletion; it is optional in this synthetic API. **Without it no
whole-database rollback guarantee is made.** A production adapter must persist
and supply the latest head in independent trusted storage. Same-user/root
filesystem compromise and key theft are outside this fixture's threat model.
The runtime database is kept private under `/private/tmp`, not committed.

## Validation and reproduction

- Retention contract: 6 tests passed.
- Original full suite, run once before changes: 1,479 tests in 157.829 seconds;
  36 subtest failures and 3 errors from unavailable nested sandbox / prohibited
  localhost binds in the outer sandbox. This run did not pass.
- Targeted recovery outside the outer sandbox: all 52 tests in the five affected
  modules passed in 21.393 seconds; no application security bypass was added.
- New gate tests: 13 passed, including ties, optional-stop factor, control
  superiority, veto, futility, plateau, immutable registration/order, exhausted
  wallet, restart/cache recovery, tampering, trusted-head rollback and exact
  slice-control behavior.

Run with a new private directory (exclusive preregistration prevents accidental
reruns into the same output directory):

```sh
PYTHONPATH=src python -m nerve_awim.sequential_gate_simulation /private/tmp/loop40-2-new-run
PYTHONPATH=src python -m nerve_awim.sequential_gate_simulation /private/tmp/loop40-2-new-reuse --reused-slice
PYTHONPATH=src python -m unittest discover -s tests -p test_sequential_gate_v1.py -v
```

Aggregate receipts, preregistration and test logs are under `evidence/loop40-2-*`.
Real reserve evaluation, real dev noise calibration, live scorer isolation,
external trusted checkpoint service and signed activation remain separate work.
