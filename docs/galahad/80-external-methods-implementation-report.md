# External-methods implementation report

The staged implementation is wired in Galahad and the outcome-release
GoalOrchestrator. Human promotion and real holdout execution remain disabled,
as authorized when overriding the original build-order prerequisite.

## Delivered

- Registration v2; paired sequential gate; alpha wallet; integrity-checked restart;
  control, capacity and deterministic-domain checks.
- Independent diagnosis; typed patch seams; persistent repair budgets and rotation;
  negative-result archive and identity-based re-eligibility; skill records and usage;
  episode lessons excluded from evidence.
- Content-addressed response replay; stratified shuffled order; robustness verdicts;
  evidence tiers; five-axis reports; separate evaluator worker and orchestrator bridge.
- Protected-source manifest, citations in docs 62–78, the source adoption plan,
  PCCP internal draft, five-axis template and detailed design/limitations.
- White-box availability/validation/retirement contracts; no fabricated activation
  probes or hardware qualification.

See [implementation map and commands](79-external-methods-adoption.md).

## Verification

25 new external-methods tests, 13 existing GoalOrchestrator tests and 4 existing
Tier-6 reconciliation tests passed: **42 total**. Coverage includes exhausted
wallets, all-control comparison, ties, futility, capacity/verifier vetoes, replay,
crash after cached response, non-repeated ambiguous dispatch, changed registrations,
modified/truncated histories, external database tampering, sealed CLI inputs,
typed seams, persistent proposal budgets, archive eligibility and skill usage.
`git diff --check` passed in both worktrees. All **75 source hashes** from the
pending v3 transport registration still match. Existing unrelated working-tree
changes were preserved; no commit, merge or deployment was made.

The independent worker and GoalOrchestrator completed the retrospective audit
and its replay, with **zero new model calls** and no holdout access. The audit
reproduces **99/100** strict development correctness with **zero disagreements**
against the historical scorer. It identifies one source/query mismatch and
creates a bounded prompt-fragment proposal for the `decoy_selected` regime.
The proposal is not executed or promoted. See
[development audit](evidence/external-methods-dev-audit.json).

The fixed-seed 200-proposal simulation contains 40 harmful proposals. The
sequential gate accepted **0/40 harmful proposals**, consumed **6,392 items** and
replayed byte-identically; the naive repeated-look comparator accepted **3/40**
and consumed **20,000 items**. These are synthetic results, not clinical evidence,
an exact Lewis replication, or a universal error guarantee. See
[simulation evidence](evidence/external-methods-simulation.json).

An initial simulation implementation exceeded its 600-second worker timeout.
Its evidence directory is retained at
`/Users/aliyildirim/nerve-research-runs/external-methods-simulation`. The optimized
version verifies the full ledger at each study boundary and invalidates its
in-process verification cache on SQLite changes; the completed simulation lives
in `external-methods-simulation-v2`. This failed attempt was not discarded or
reported as a passing experiment.

## Still gated or not established

1. The real slice-2 verdict and a human-reviewed, signed live gate adapter are
   prerequisites to reserve evaluation. This work neither opens the reserve nor
   replaces the deployed gate. The staged API deliberately refuses holdout.
2. Real capacity measurement, calibrated plateau thresholds, cross-order studies,
   isolated safety evaluation and shadow/canary evidence must be supplied by a
   prospective live adapter. Historical missing evidence is reported as missing.
3. A 7B+ GPU model, reviewed probe tooling, preregistered behavioural/steering
   validation and Tier C approval are required for actual Loop 47 probes. The
   current status is `white-box: unavailable`; no activation-drift or circuit
   finding is claimed.
4. The PCCP document needs regulatory-advisor review before external citation.
   Synthetic extraction performance is not clinical efficacy or FDA compliance.
5. Reusable adaptive holdout theory, external anti-rollback witnesses and OS-level
   isolation are not furnished by this staged Python implementation. Its concrete
   protections and limits are documented in the design note.

Deferred optimizer engines, weight self-edits and meta-agent code rewriting stay
deferred under the source plan. No automated promotion path was introduced.


## Publication follow-up

The external-methods changes were isolated on `codex/nerve-external-methods-20261015` for publication. The orchestrator bridge is on `codex/nerve-outcome-external-methods-20261015`. Historical slice-1/slice-2 working-tree changes and documents 77–78 belong to separate ongoing work and are not included in these commits. The 75-source comparison above records the original working-tree verification; it does not imply that the separate uncommitted holdout implementation is bundled here.
