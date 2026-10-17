# NERVE — External Methods Adoption Plan

**Tier 6 upgrades drawn from the 2026 literature · prepared 15 Oct 2026**
Applies to `feature/galahad-persistent-memory` (Loops 36–46) and the reconciled `nerve-outcome-release` orchestrator.

**Rule for everything below.** A method is adopted only if it passes the Tier 6 invariants (§3 of
`NERVE_SELF_LEARNING_LOOP_PLAN.md`): human holds the promotion key; beat the controls; pre-register
then run; format ≠ fact; negative results retained; restart-safe; honest status. Anything that would
give the loop authority over its own grader, the holdout, or deployment is rejected or deferred to
Loop 46 under the protected-path manifest. Every adopted method is cited in the doc that implements it.

---

## 1 · Adoption table

| Source | What we take | Where it lands | Verdict |
|---|---|---|---|
| Lewis, *Scientific CI/CD for Self-Modifying Discovery Agents* (ICML 2026) | Anytime-valid statistical gate (e-values / confidence sequences) on protected holdout; α-spending across a stream of proposals; capacity budget; domain verifier | Loop 40.2, 40.3, 40.4 | **Adopt** — solves the burned-slice problem |
| Nakajima, *Regimes* (arXiv 2606.10241) | Deterministic failure-diagnosis oracle; typed pipeline seams; regime→seam routing; attempt budgets and rotation; marginal confirm-delta; plateau-aware promotion; content-addressed response cache in evidence | Loop 39.4, 39.5, 40.5, 37.2 | **Adopt** |
| Arize, *How to prove each update* | Evidence plan tiered by change risk; repeated runs with shuffled task order; evaluator independent of the system judged | Loop 41.2, 42.4, 36.5 | **Adopt** |
| Vaccaro, *Preregistration for Experiments with AI Agents* (ICML 2026) | Registration template: checkpoint hashes, verbatim prompts, sampling params, timeouts and retry limits, pilot-history disclosure, confirmatory/exploratory split, exclusion rules fixed in advance | Loop 36.6 registration schema v2 | **Adopt** |
| Zhu et al., *Path to Self-Evolving Clinical Systems* (arXiv 2607.11175) | Five-axis scoring (reasoning quality, efficiency, robustness, UX, safety); "clinical gym" with verifiable rewards; three-level autonomy taxonomy | Loop 36.7 reporting; Loop 38 naming; governance doc | **Adopt** (reporting and vocabulary) |
| FDA PCCP final guidance (Dec 2024) | Description of modifications (automatic/manual, global/local); modification protocol with pre-defined acceptance criteria; impact assessment; real-world monitoring | `docs/galahad/pccp-mapping.md` | **Adopt** as design alignment, not a submission |
| Darwin Gödel Machine (Clune et al., ICLR 2026) | Archive of all variants, including rejected, as a population for future re-proposal | Loop 39.3 rejection memory | **Adapt** — re-eligibility only on bank or model change |
| Voyager | Skill library: executable skill + description + usage record, retrieved for reuse | Loop 41 skill record | **Adapt** |
| Reflexion | Per-episode verbal self-critique kept as a note | Loop 37 episode `lesson` field | **Adapt** — generator input only, never evidence |
| Cammarata, *Already Clean* (Goodfire, 2026) | Mechanistic interpretability as verification: activation probes for named circuits (abstain, copy-number, select-source); activation-level drift | Loop 47 (white-box verification), feeding 40.4 and 43.3 | **Adapt, research track** — hypothesis stage; needs open-weight 7B+ and probe tooling |
| DSPy, TextGrad, Trace/OptoPrime | Prompt-optimisation engines | Loop 39.1 mutation space, under a seam | **Defer** — needs model calls; allowed later as a generator, never as a gate |
| SEAL | Self-generated finetuning data, weight self-edits | Loop 44 only | **Defer** — gated by volume and governance |
| ADAS, EvoAgentX | Meta-agent designs new agents / workflows | Loop 46 scope | **Defer** — protected-path rules apply |

---

## 2 · Specifications

### Loop 40.2 — Sequential gate (anytime-valid)
*Replaces fixed-n, single-use holdout slices as the primary promotion test. Slices remain as a fallback.*

**Problem it solves.** A fixed-n holdout consumed once per attempt burns 100 items per infrastructure
failure (slice 1, 15 Oct) and cannot be re-checked without inflating error. An anytime-valid test lets
the gate consult the holdout item by item and stop as soon as the evidence is sufficient, with type-I
error controlled at every stopping time.

**Design.**
- Primary statistic: paired per-item outcome, candidate vs incumbent, on the same holdout item
  (win / loss / tie on strict correctness). Ties carry no evidence.
- Test: a test-supermartingale on the win probability among discordant pairs, H0: p ≤ 0.5
  (candidate not better). Use a mixture or betting e-process; registered before the run with its
  parameters. Promote when e ≥ 1/α; α = 0.05 by default, registered per study.
- Per-stratum guards: the same e-process per stratum against always-abstain, H0: candidate ≤ control.
  A stratum whose e-process crosses 1/α in the *wrong* direction vetoes promotion.
- α-spending wallet (Lewis): the holdout carries a budget of total α across all candidates that ever
  touch it. Each registered study draws from the wallet; the wallet and its ledger are protected paths.
- Early stop rules: promote (e ≥ 1/α on primary, no stratum veto); reject (primary e-process
  crosses the futility bound); `insufficient_power` (item budget exhausted); `incomplete_infrastructure`
  (transport policy exhausted). Item order is seeded and registered; items are drawn stratified.
- Plateau rule (Regimes): a promotion also requires net wins − losses ≥ a noise-calibrated minimum
  taken from the dev study's seed variance, so near-zero-delta promotions at high baselines are refused.
- Marginal delta (Regimes): the comparison is always against the *currently deployed* incumbent,
  measured by installing the candidate and reverting only it.

**Both-path proof.** Gate with an exhausted α-wallet refuses to open holdout and says so; a run killed
mid-stream resumes at the same item with the same e-value and zero repeated inference; item-level
outcomes never leave the gate's private directory; the wallet ledger hash is re-verified before every
study; a tampered e-value history is detected and halts with `degraded — integrity`.

**Done-when.** Replication of Lewis's experiment with NERVE's own gate: a synthetic stream of 200
proposals (20 % harmful, outcomes simulated, zero model calls) evaluated by (a) the current fixed-slice
gate with naive re-use and (b) the sequential gate with α-spending. Report harmful-accept rate and
items consumed for each. The sequential gate must bring harmful acceptance below 1 % and consume
fewer items than the slice design on the same stream. Then candidate v3 is re-evaluated on the reserve
through the sequential gate, and the verdict is reproduced byte-identically on restart.

**Governance.** This changes a protected path (the gate). It is designed and reviewed by humans,
registered as a gate version with its own tests, and signed before it replaces the slice gate.
Loop 46 may never propose changes to it.

---

### Loop 40.3 — Capacity budget
Every candidate declares its capacity delta relative to the incumbent: prompt tokens, output tokens,
model digest and size, number of deterministic rules, retrieval `k`, tools and memory reads, autonomy
(which decisions it makes without a rule). The gate charges a registered price per unit and requires
the primary gain to exceed a capacity-adjusted threshold. A candidate that wins only by spending more
is reported as `gain_not_capacity_adjusted`, not promoted.

**Both-path proof.** A candidate that omits its declaration is refused; a declaration that disagrees
with the measured run (token counts, call counts) fails the study.

---

### Loop 40.4 — Domain verifier (invariants as vetoes)
Deterministic checks on every output, scored separately from correctness and applied as vetoes:
unit is dimensionally consistent with the requested quantity; value lies within the range present in
the cited evidence; `source_id` resolves to a record in the prompt; no answer without a source; an
abstention carries its rule name. Any violation on holdout vetoes promotion regardless of score.
Clinical extensions later: guideline-range checks, contraindication flags, dose bounds.

---

### Loop 39.4 — Deterministic diagnosis oracle
Each failed item is labelled by a deterministic oracle over ground truth, never by an LLM judge:
`abstained_when_answerable`, `answered_when_should_abstain`, `wrong_value`, `wrong_unit`,
`wrong_provenance`, `format_invalid`, `decoy_selected`, `stale_selected`, `conflict_not_detected`.
Labels are independent of the correctness scorer. The regime histogram per study is the generator's
only view of failures (stratum- and label-level counts on holdout; item-level on dev only).

### Loop 39.5 — Typed seams and regime→seam routing
Candidates are patches bound to named pipeline points, never free code:
- `abstention-rule` seam (deterministic gate rules)
- `extraction-schema` seam (JSON schema, enums, typed fields)
- `prompt-fragment` seam (bounded edits; max characters registered; may not add keys)
- `retrieval-order` seam (scoring/ordering of evidence records)
- `routing` seam (which model/agent; Loop 43.2)

Fixed map: `conflict_not_detected`, `answered_when_should_abstain` → abstention-rule;
`wrong_provenance`, `format_invalid`, `wrong_unit` → extraction-schema; `wrong_value`,
`decoy_selected` → prompt-fragment then retrieval-order; `stale_selected` → abstention-rule
(recency rule) then retrieval-order. A regime with no seam is a **wall** and is the registered trigger
for Loop 46. Each regime has an attempt budget; when exhausted the loop rotates to the next
seam-reachable regime. The generator selects the dominant seam-reachable regime each cycle.

**Both-path proof.** A patch outside its seam's static checks (import whitelist, signature, size,
no new keys) is refused before any model call; a wall is reported, not silently skipped.

---

### Loop 36.6 — Registration schema v2 (Vaccaro)
Every study registers, hashed, before the first call: model identifier and checkpoint digest,
quantisation, runtime version; verbatim prompts and schemas; temperature, top-p, seeds; token limits,
timeouts, transport retry policy; task-bank manifest and split; exclusion rules for malformed,
refused or timed-out responses; primary and secondary outcomes with their tests and interpretation
rules; `confirmatory` or `exploratory` flag (calibrations are exploratory and never promote);
**pilot history** — how many candidate drafts, calibration runs and dev studies preceded this
registration and what they showed; declared robustness variants, all reported including nulls;
attestation that no holdout item has been read. Staged designs are allowed only with later-stage
decision rules fixed in advance.

### Loop 36.5 (extension) — Shuffled-order seeds
For any stateful policy (memory, retrieval cache), each seed also varies task order. A gain that
reverses under reordering is reported as order-dependent and does not promote.

### Loop 36.7 — Five-axis report (clinical survey)
Every study reports: accuracy (per stratum, with intervals); efficiency (model calls, tokens,
median and max latency, capacity delta); robustness (seed and order variance, worst stratum);
safety (domain-verifier violations, unsafe answers, abstention precision); UX (deferred to Loop 38:
clinician edit distance and acceptance). Name the task bank + controls + reward the **NERVE clinical
gym** in docs; it is what the survey calls for.

---

### Loop 37.2 — Content-addressed response cache in the evidence bundle
Regimes' stated gap: replay requires a cache that was not published. NERVE already keeps receipts;
make the cache explicit — every model response stored by content hash of (model digest, prompt,
params), the cache manifest included in each evidence bundle, so a third party can replay any study
byte-identically with zero model calls. Item-level holdout entries live in the gate-private directory;
dev entries are public.

### Loop 37.3 — Episode `lesson` (Reflexion, adapted)
Optional free-text note attached to an episode by the generator ("conflict rule fired on
rounding difference; consider tolerance"). Generator input only; never evidence, never a score input.

---

### Loop 41.2 — Evidence plan by change tier (Arize)
| Tier | Change type | Required before promotion |
|---|---|---|
| A | prompt fragment, schema, deterministic rule, memory note | sequential gate on holdout; regression suite; named rollback |
| B | routing, tool policy, retrieval order, abstention threshold | Tier A + constraint checks (cost, latency, permissions) + human approval |
| C | model digest, adapter, code outside seams, permissions, autonomy level | Tier B + isolated evaluation + full safety suite + shadow/canary (Loop 42) + named owner |

Candidate v3 is Tier A/B (rules + schema). Any Loop 44 adapter is Tier C.

### Loop 41.3 — Skill record (Voyager, adapted)
A retained skill = `{skill_id, version, seam, patch, description, evidence_bundle, capacity_delta,
usage: {selected, outcomes}, supersedes, signed_by}`. Retrieval by seam and regime, not by score alone.

### Loop 39.3 (extension) — Archive and re-eligibility (DGM, adapted)
Rejected candidates stay in the archive with their study. A rejected candidate becomes re-eligible
only when the task-bank version, model digest or incumbent changes; re-proposal must cite which.

### Loop 42.4 — Independent evaluator
The scorer, the diagnosis oracle and the gate run in a separate process from the candidate and the
generator, with read-only access to the bank and no write access to the protected paths. Asserted by
test: a candidate that attempts to import or write to the gate is refused at the static-check stage.

---

### Loop 47 — White-box verification (research track, Tier 7)
*From Cammarata's hypothesis that modern architectures are mostly monosemantic. Treated as a
hypothesis to test on NERVE's own substrate, not a method to depend on.*

**Trigger:** an open-weight model ≥ 7B on a GPU host (Loop 36.4) and a probe toolkit that runs
against it; never on the 1.5B laptop substrate.

**47.1 Circuit probes for the verifier.** Identify and validate activation-level signatures for the
behaviours the deterministic gate already names: *abstain*, *copy-number*, *select-source*,
*decoy-attend*. Validation is behavioural and pre-registered: a probe is accepted only if it predicts
the diagnosis-oracle label (Loop 39.4) on held-out dev items above a registered threshold, and
steering it changes the output in the predicted direction. Accepted probes become additional inputs
to the domain verifier (40.4): an answer whose *copy-number* circuit did not fire is flagged even if
the value is correct.

**47.2 Activation-level drift (feeds 43.3).** Per-site activation statistics on the validated circuits
form a second drift channel beside input-distribution statistics. A drift alert here opens the same
re-adaptation ticket as 43.3; it never promotes anything on its own.

**47.3 Mechanism-level failure diagnosis (feeds 39.4).** When the oracle labels a failure, the probe
record says which circuit was or was not active. The generator receives this as an additional
regime dimension, routed through the same seam map. Example: yesterday's prompt-induced abstention
collapse would have shown as *abstain* active on every supported item in a single study.

**Both-path proof:** with no probe toolkit the loop reports "white-box: unavailable" and 40.4 / 43.3
run on outputs only; a probe whose held-out predictive power falls below threshold is retired and
removed from the verifier automatically with honest status; probe outputs are evidence for the gate,
never a score input, and never a promotion path.

**Done-when:** one validated probe (likely *abstain*) reproduces the study-3 → study-5 finding from
activations alone on the dev split, and is cited in a verifier veto on at least one holdout item.

**Governance:** probes are Tier C changes (Loop 41.2) — they alter what the verifier can reject.
Companion paper and tooling to be reviewed before 47.1 is registered.

---

### PCCP mapping — `docs/galahad/pccp-mapping.md`
A design-alignment document, not a regulatory submission:
1. **Description of modifications** the loop may make: seams (what), Tier A/B/C (risk), *manual*
   (human key) not automatic, *global* by default; site-scoped policies (Loop 43.3) are *local*
   modifications and carry their own justification and monitoring.
2. **Modification protocol**: registration schema v2 = data management and performance evaluation
   plan; the sequential gate's α and acceptance rule = pre-defined acceptance criteria; Loop 42
   shadow/canary/rollback and Loop 43.3 drift = real-world monitoring and update procedures.
3. **Impact assessment**: per tier, the risks of a wrong promotion and the controls that bound them;
   labelling statement that the system learns under a controlled plan.
Reviewed by a regulatory advisor before it is cited externally.

---

## 3 · Build order (after holdout slice 2 — nothing here runs before that verdict)

| # | Item | Window | CPU |
|---|---|---|---|
| 1 | Citations added to docs 62–78; PCCP mapping doc; five-axis report template | outcome-release | none |
| 2 | Registration schema v2 with pilot-history and confirmatory flag; tests | galahad | low |
| 3 | Loop 40.2 sequential gate: design note, e-process implementation, α-wallet, tests; **200-proposal simulated replication of Lewis** (zero model calls) | galahad | low |
| 4 | Diagnosis oracle + typed seams + regime→seam map; re-run generator on existing episodes | galahad | low |
| 5 | Capacity budget + domain verifier as vetoes; back-apply to v3 evidence | galahad | low |
| 6 | Evidence tiers, skill record, archive re-eligibility, independent-evaluator process split | both | low |
| 7 | Response cache in evidence bundles | galahad | low |
| 8 | Re-evaluate v3 on the reserve through the sequential gate (first real use) | galahad | **model calls — machine idle** |
| 9 | Loop 47.1 probe study — only once a ≥7B open-weight model is on a GPU host and probe tooling is reviewed | galahad | GPU |

Items 1–7 need no inference and can run while the GPU decision is pending. Item 8 is the first
holdout evaluation that does not consume a slice.

## 4 · What is deliberately not adopted now
DSPy/TextGrad/Trace as generators (model-call heavy; add under the prompt-fragment seam once a
GPU host exists); SEAL weight self-edits (Loop 44, gated); ADAS/EvoAgentX meta-agents (Loop 46,
protected paths); DGM-style arbitrary self-rewriting code (never — seams only).

## 5 · Claim this supports
"NERVE's self-improvement loop uses an anytime-valid statistical gate on sealed holdout data,
pre-registered studies, control-anchored acceptance, deterministic failure diagnosis routed to typed
repair points, and human-keyed promotion aligned to the FDA PCCP model." Each clause maps to one
numbered loop above and to a published method it extends.

## Sources
- Lewis, *Scientific CI/CD for Self-Modifying Discovery Agents* — https://icml.cc/virtual/2026/82618
- Nakajima, *Regimes* — https://arxiv.org/abs/2606.10241
- Arize, *Self-improving agents: how to prove each update* — https://arize.com/resources/self-improving-agents/
- Vaccaro, *Preregistration for Experiments with AI Agents* — https://arxiv.org/pdf/2606.11217
- Zhu et al., *The Path to Self-Evolving Clinical Systems* — https://arxiv.org/pdf/2607.11175
- FDA PCCP final guidance summary — https://www.foley.com/insights/publications/2025/01/fda-final-guidance-ai-device-software-predetermined-change-control-plan/
- Darwin Gödel Machine — https://iclr.cc/virtual/2026/poster/10007327
- Framework survey (DSPy, TextGrad, Trace, Reflexion, Voyager, SEAL, ADAS, EvoAgentX) — https://futureagi.com/blog/self-improving-ai-agents-open-source-frameworks/
- Cammarata, *Already Clean* (Goodfire) — https://already-clean.goodfire.com/
