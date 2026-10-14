# NERVE — Self-Learning / Self-Improving / Auto-Adapting Loop Plan

**Tier 6 · Closed-Loop Self-Improvement · Loops 36–45**

This plan extends `NERVE_LOOP_PLAN.md` (Loops 18–35) with the tier that turns the stack from
*evaluated* into *self-improving*. It builds on what already exists on
`feature/galahad-persistent-memory`: the scientific research coordinator, the registered
validation studies, the restart-safe claim journals, and the evidence bundles under
`docs/galahad/evidence/`.

**Starting position (14 Oct 2026, commit `17f97ae`).** The loop can *reject* a candidate under a
pre-registered rule, persist every call, and restart with zero repeated inference. It cannot yet
*generate* candidates, *retain* winners, *deploy* them, or *learn from the real world*. Its
evaluator is also underpowered: n=8 per arm, a baseline that scores identically to always-abstain
(4/8, 0 model calls), a 1.5B code-tuned model, and ~57 s per call on CPU. Nothing can be learned
through that evaluator, so it is fixed first.

**Scope note.** Engineering loops only. Human governance sign-offs (enabling a promoted candidate
on real patients, enabling weight-learning on clinical traces) are **external gates**, noted where
relevant, not built here. The invariants that make the learning *trustworthy* — provenance,
signed-report-as-fuel, honest status, never fabricate — stay in and are enforced by proof.

---

## 1 · The loop model (unchanged)

A loop is a reactor: **trigger → reactor steps → both-path proof → stop-when-green.**

- **Both-path proof** (Loop 18.1 harness): the enabled path *acts with provenance*; the disabled
  path *no-ops*; gated-off *shows "no data"*; a degraded source *shows honest status, never
  fabricates*.
- **Done-when** = an observable, testable condition.
- Loop 22 re-audits after every change. Loop 24 conducts the sequence.

## 2 · What "self-learning" means here — four distinct mechanisms

| Level | Mechanism | Changes | Loops |
|---|---|---|---|
| L1 Policy learning | select better prompts / retrieval / tool rules / abstention thresholds from measured outcomes | config & prompts | 39, 40 |
| L2 Knowledge & skill accumulation | validated episodes → versioned Hermes skills and facts | skill store, memory | 41 |
| L3 Runtime adaptation | per-site / per-clinician behaviour via memory + bandit routing | memory, routing policy | 43 |
| L4 Weight learning | LoRA / SFT / DPO on validated traces, adapter-per-task | model adapters | 44 |

L1–L3 deliver most of the observable "self-improvement" and carry low clinical risk. L4 is gated
behind a steady stream of validated traces from L1–L3 and an external governance gate.

## 3 · Non-negotiable invariants (enforced by proof in every Tier-6 loop)

1. **The loop proposes promotions; a human grants them.** Nothing patient-facing is changed by
   the loop alone. Promotion is a signed act (Loop 25.1 state machine, same hash binding).
2. **Beat the controls, not just the baseline.** A candidate must beat always-abstain, random,
   and the incumbent on the held-out split, with no stratum regression.
3. **Pre-register, then run.** Candidate, task set, acceptance rule and seeds are hashed before
   the first model call. No retries from intermediate results.
4. **Format ≠ fact.** Output-contract failures and factual/evidence failures are scored and
   reported separately. A schema-constrained interface removes the former so the latter is
   measurable.
5. **Negative results are retained.** Rejected candidates and their evidence stay in the store;
   the generator cannot re-propose them without new evidence.
6. **Restart-safe, replay-safe.** Any loop can be killed and restarted with zero repeated
   inference and byte-identical reports (already proven for the coordinator; must hold for all).
7. **Honest status.** Every component reports `live / degraded / off` to JARVIS observability
   (Loop 35). A learning loop that is off says so; it never shows stale "improving" curves.

---

## 4 · Loops

### Loop 36 — Evaluator Foundation
*Without this, no other Tier-6 loop can learn anything.*

**Trigger:** start of Tier 6; re-triggered whenever the task bank or model digest changes.

**36.1 Task bank.** ≥300 items across the existing strata (supported-measurement,
measurement-decoy, entity-decoy, unit-mismatch, conflict) plus two new strata: *multi-source
agreement* and *stale-vs-current evidence*. Each item carries ground truth, expected behaviour
(answer / abstain), provenance, and a content hash. Split 70/30 into `dev` and `holdout`;
`holdout` is read only by the selection gate (Loop 40), never by the generator (Loop 39).
Versioned as `task-bank-vN` with a manifest hash recorded in every study.

**36.2 Control arms.** Three arms computed for every study at zero model cost: *always-abstain*,
*random-answer*, *incumbent*. Their scores are hard gates in Loop 40, not reported numbers.

**36.3 Structured output contract.** Schema-constrained generation via the runtime's
`response_format` (JSON schema). Format failures become a separately logged metric
(`format_failures`) and no longer count in `strict_correct`. Keep the raw text as well, so
schema errors in the runtime are themselves detectable.

**36.4 Inference substrate.** GPU-backed host; model ≥7B general-purpose (the 1.5B coder model
stays as a *floor control* only). Model digest pinned and recorded per study. Latency budget:
≤5 s median per call, so a 300-item study completes in under an hour.

**36.5 Statistical gate.** Minimum n per stratum (≥20 on holdout), ≥3 seeds per arm at the
sampling temperature in use, bootstrap CIs on per-stratum and overall accuracy, and a pre-declared
minimum effect size. The gate reports "insufficient power" as a distinct verdict from "rejected".

**Both-path proof:** evaluator with a missing task-bank manifest refuses to run and shows
"no data"; with a mismatched model digest refuses to run and shows honest status; control arms
are produced with zero network / inference calls (assert via patched metadata/preload/inference
as in the coordinator restart test).

**Done-when:** a 300-item holdout study on the ≥7B model completes in <60 min, produces
per-stratum CIs, and all three control arms are present in the report and in the gate.

---

### Loop 37 — Experience Store (Galahad)
**Trigger:** Loop 36.1 done.

**Reactor steps.** Extend the Galahad memory gateway with an append-only `episodes` journal.
One episode = `{episode_id, context_hash, agent, candidate_id, policy_version, inputs_hash,
action, output, evaluator_verdict, format_ok, evidence_ok, real_world_outcome, outcome_source,
timestamps, source_sha256[]}`. Every study row, every shadow run (Loop 42) and every signed
report (Loop 38) writes here. Indexed by stratum, candidate, policy version, and failure class.
Export path: `docs/galahad/evidence/episodes-<date>.jsonl` with a rolling manifest hash.

**Both-path proof:** write with provenance when enabled; no-op when the gateway is gated off;
a corrupted journal file reports "degraded — read-only" and never silently reinitialises.

**Done-when:** all 16 calls from `scientific-interface-validation-v1` are re-ingested as episodes
from the existing receipts with zero inference, and a failure-cluster query ("conflict stratum,
non-abstaining failures") returns exactly the two known candidate failures.

---

### Loop 38 — Real-World Reward Wiring
*The clinician sign-off is the fuel. This loop connects it to the tank.*

**Trigger:** Loop 37 done; Loop 25.1 sign-off state machine live.

**Reactor steps.**
1. On every `DRAFT → SIGNED` transition, emit an episode with `real_world_outcome ∈ {ACCEPT_AS_IS,
   ACCEPT_WITH_EDITS, REJECTED}` and, for edits, a section-level diff summary (which sections
   changed, edit distance, whether a claim was removed or added).
2. Treat `ACCEPT_AS_IS` as strong positive, `REJECTED` as strong negative, edits as weak labels
   keyed to the edited section. Abstentions that the clinician fills in by hand are logged as
   *missed opportunities*, not errors.
3. Aggregate per policy version, per agent, per report section, per clinic. These become
   additional strata in Loop 36's task bank over time (real cases, de-identified, after an
   external gate).

**Both-path proof:** unsigned drafts produce no reward episode; a report signed under a policy
version that no longer exists still ingests with honest "policy retired" status; PHI never
enters the evidence export (assert via redaction test).

**Done-when:** 50 signed reports have produced reward episodes, and a per-section acceptance
table renders in the JARVIS Agents tab with honest counts.

---

### Loop 39 — Candidate Generator
**Trigger:** Loops 36 and 37 done.

**39.1 Mutation space v1 (cheap, bounded).** Enumerable variations only: prompt variants from a
template library; retrieval `k` and scoring; abstention thresholds; tool-selection rules;
conflict-detection pre-step on/off. Every candidate is a hashed config, not free text.

**39.2 Failure-cluster-driven proposals.** A NERVE research agent reads the experience store,
clusters failures by stratum and failure class, and emits a *registered hypothesis*: the cluster,
the proposed mutation, the predicted effect, and the stratum where regression is most likely.
The hypothesis is hashed into the study before any model call.

**39.3 Negative-evidence memory.** Rejected candidate hashes and their study reports are stored.
A proposal matching a rejected hash (or within a declared edit distance of one) is refused unless
it cites new evidence (a newer task-bank version or a new failure cluster).

**Both-path proof:** generator with an empty experience store emits no proposals and says so;
generator with the research agent disabled falls back to mutation-space enumeration with honest
status; a proposal without a registered hypothesis is refused by Loop 40.

**Done-when:** the generator proposes, from the existing conflict-stratum failures, a
conflict-detection pre-step candidate with a registered hypothesis — without being told to.

---

### Loop 40 — Selection & Promotion Gate
*Extends `scientific_research_coordinator`.*

**Trigger:** a registered hypothesis from Loop 39.

**Reactor steps.** Run `dev` study → if promising, run `holdout` study (holdout is opened only
here) → apply the pre-registered rule: beats always-abstain, random and incumbent; no stratum
regression beyond the declared tolerance; CI excludes zero on the primary metric; format and
evidence metrics both reported. Output is one of `promote_proposal`, `retain_incumbent`,
`insufficient_power`. A `promote_proposal` is a signed artefact handed to the human gate — it is
**not** a promotion.

**Both-path proof:** existing coordinator restart test extended: killing the gate mid-holdout and
restarting makes zero repeated calls; a candidate that touches `holdout` outside this loop fails
the study; `promote_proposal` with an unsigned human gate produces no deployment.

**Done-when:** the full generate → dev → holdout → proposal path runs end to end on the
conflict-detection candidate and yields a verdict with CIs; the verdict is reproduced
byte-identically on restart.

---

### Loop 41 — Skill Retention (Hermes)
**Trigger:** a `promote_proposal` accepted by the human gate.

**Reactor steps.** The winning candidate becomes a versioned Hermes skill:
`{skill_id, version, config_hash, evidence_bundle (study reports, task-bank version, model
digest), supersedes}`. The incumbent is marked `superseded`, not deleted. Skills are
role-scoped via the existing registry. Distilled *lessons* (e.g. "when two sources disagree on
mass, abstain and surface both") are written as retrievable knowledge in the F.2 skill store.

**Both-path proof:** skill write with provenance when the gate is signed; no write when unsigned;
a skill whose evidence bundle hash fails verification loads as `degraded` and is never selected.

**Done-when:** two skill versions coexist with a verifiable supersession chain, and an agent
selecting the skill shows its evidence bundle in the JARVIS transparency drawer.

---

### Loop 42 — Shadow → Canary → Promote
**Trigger:** Loop 41 done.

**42.1 Shadow runner.** The promoted skill runs alongside the incumbent on live (non-synthetic)
inputs; outputs are logged as episodes, never shown. Disagreement rate and abstention delta are
tracked per stratum.

**42.2 Canary.** A declared fraction of low-risk tasks (e.g. report *drafting*, never
*protocol parameters*) is served by the candidate, with the clinician unaware of arm but the
episode tagged. Loop 38 reward feeds back.

**42.3 Drift monitor & rollback.** Pre-declared metrics with thresholds; breach triggers
automatic rollback to the incumbent and a `degraded` status to JARVIS. Rollback is itself
restart-safe and journaled.

**Both-path proof:** shadow mode with the candidate failing to load serves the incumbent with
honest status; canary allocation above the declared fraction is refused; rollback restores the
incumbent and proves the candidate is no longer selected.

**Done-when:** a candidate completes shadow (≥200 episodes) and canary (≥50 signed reports)
with reward ≥ incumbent, and the promotion proposal reaches the human gate with that evidence
attached.

---

### Loop 43 — Runtime Adaptation
**Trigger:** Loops 37 and 38 done (can run in parallel with 39–42).

**43.1 Preference memory.** Per-site and per-clinician preferences (report structure, phrasing,
sections routinely edited) learned from Loop 38 diffs and stored as durable memory under the
two-tier model (durable writes only through the signed-report pipeline).

**43.2 Contextual bandit routing.** Thompson-sampling or similar over {specialist agent, model,
abstain} with Loop 38 reward. Exploration rate declared and bounded; exploration never touches
safety-critical outputs.

**Both-path proof:** a new clinic with no history gets the global policy with honest "no local
data" status; routing with the bandit disabled falls back to static rules; exploration on a
safety-critical path is refused.

**Done-when:** two clinics with ≥50 signed reports each show measurably different, auditable
routing/preference policies, each traceable to its episodes.

---

### Loop 44 — Weight Learning (gated)
**Trigger:** ≥1,000 validated episodes across Loops 38 and 42 **and** an external governance gate.

**44.1 Trace curation.** Only `ACCEPT_AS_IS` and evaluator-verified episodes; de-identified;
held-out split preserved.
**44.2 LoRA / SFT** on curated traces, adapter per clinical task, never a monolithic model.
**44.3 DPO** on `ACCEPT_AS_IS` vs `REJECTED` pairs for the same context.
**44.4 Adapter registry & gate.** Every adapter passes Loop 36 holdout and Loop 40 controls before
it can enter Loop 42 shadow. Adapters are versioned skills (Loop 41) with their training-data
manifest hash in the evidence bundle.

**Both-path proof:** training with the governance gate unsigned no-ops; an adapter missing its
data manifest loads as `degraded` and is never served; serving falls back to the base model with
honest status if the adapter fails to load.

**Done-when:** one adapter beats the base model on holdout with CI excluding zero and completes
shadow without drift.

---

### Loop 45 — Self-Improvement Conductor (meta-loop)
**Trigger:** Loops 36–42 done.

**Reactor steps.** Schedules improvement cycles (generate → gate → retain → shadow) within a
declared compute budget; prioritises failure clusters by reward impact; publishes a learning
curve (holdout accuracy, real-world acceptance, abstention precision) per policy version to
JARVIS observability (Loop 35); stops a cycle when the gate returns `insufficient_power` twice
and asks Loop 36 to extend the task bank instead.

**Both-path proof:** conductor with budget exhausted stops and reports honestly; conductor cannot
bypass Loop 40 or the human gate (assert no deployment path exists from the conductor);
restart mid-cycle resumes without repeated inference.

**Done-when:** three consecutive unattended cycles produce either a promotion proposal or a
documented negative result, with the learning curve rendered and every point traceable to an
episode set.

---

## 5 · Dependency DAG

```
36 Evaluator ──┬──> 39 Generator ──> 40 Gate ──> 41 Retain ──> 42 Shadow/Canary ──┐
               │                        ^                                         │
37 Store ──────┼────────────────────────┘                                         ├──> 45 Conductor
   │           │                                                                  │
   └──> 38 Reward ──> 43 Adaptation ──────────────────────────────────────────────┘
                 \
                  └──> 44 Weight learning (needs 38 + 42 volume + external gate)
```

## 6 · Build sequence

1. **36.4, 36.3** — substrate and structured output (unblocks everything; the current 1-minute
   CPU calls make iteration impossible).
2. **36.1, 36.2, 36.5** — task bank, controls, statistical gate.
3. **37** — experience store; re-ingest existing receipts.
4. **40** — extend the coordinator to the new gate (controls, holdout, CIs, `insufficient_power`).
5. **39.1 → 39.2 → 39.3** — generator, starting from the known conflict-stratum failures.
6. **38** — reward wiring (can start as soon as 37 is in; needs sign-off traffic to be useful).
7. **41, 42** — retention and shadow/canary.
8. **43** — adaptation, in parallel from step 6.
9. **45** — conductor.
10. **44** — only when volume and governance allow.

## 7 · First ten concrete tasks (start here)

1. Stand up GPU inference with a ≥7B general model; pin and record the digest; measure median
   latency on the existing 8-task set (target ≤5 s).
2. Add `response_format` JSON-schema constraint to the scientific interface; add
   `format_failures` as a separate metric; keep raw text.
3. Re-run `scientific-interface-validation-v1` on the new substrate as a *calibration* study
   (not a promotion study) to see how much of the 0/4 supported score was formatting.
4. Generate `task-bank-v1` (≥300 items, 7 strata) with a manifest hash; write the `dev/holdout`
   split and the read-guard on `holdout`.
5. Add always-abstain and random control arms to the coordinator screen as hard gates.
6. Add bootstrap CIs, ≥3-seed runs and the `insufficient_power` verdict to the gate.
7. Implement the `episodes` journal in the Galahad gateway; re-ingest the 16 existing receipts
   with zero inference and prove byte-identical export on restart.
8. Write the registered-hypothesis schema and refuse unregistered candidates at the gate.
9. Implement mutation space v1 and have it enumerate the conflict-detection pre-step candidate.
10. Run the first full generate → dev → holdout → proposal cycle on that candidate and commit
    the evidence bundle, whichever way it goes.

## 8 · Metrics that prove "self-improving" (and what each would show today)

| Metric | Source | Today |
|---|---|---|
| Holdout strict accuracy vs always-abstain, with CI | Loop 36/40 | 4/8 vs 4/8, no CI — nothing learned yet |
| Supported-extraction accuracy (format-separated) | Loop 36.3 | 0/4 both arms — unmeasured |
| Abstention precision/recall per stratum | Loop 36 | conflict: incumbent 2/2, candidate 0/2 (n=2) |
| Real-world acceptance rate per policy version | Loop 38 | not wired |
| Proposals per cycle, promotion rate, negative results retained | Loops 39/40/45 | 1 negative result retained |
| Time-to-reject / time-to-promote | Loop 45 | 43 min for 16 calls |

The plan is done when the learning curve in Loop 45 has a slope the CI can distinguish from
zero, and every point on it is traceable to signed, hashed evidence.
