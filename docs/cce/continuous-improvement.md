# Continuous improvement programme

The user goal is repeated autonomous research and adaptation until improvement
is demonstrated. This programme extends the existing scheduled NERVE/Hermes
workflow; it is not a new agent controller or a declaration of completion.

The outer loop is the existing 900-second bridge cycle. It collects verified
mission outcomes, records bounded research leads, dispatches one eligible study
or shadow check, persists results, and waits for the next scheduled cycle. It
respects the existing native 20-session UTC-day allowance and separate local
80-attempt allowance. Budget resets do not reset evidence consumption.

The inner audit loop is training baseline → lesson proposal → paired selection
→ paired retention → paired untouched final evaluation → independent receipt
verification → experimental export. A subsequent registered study can use
bounded prior training feedback to propose a better lesson. The comparison
baseline remains the existing capable audit prompt; it is not weakened to make
an improvement easier to claim. The existing CCE loop separately retains its
30-pair holdout, model compatibility, calibration and activation gates.

Cross-study context starts with studies created under the continuity runner's
exact revision. It does not import the older fixed audit study or silently
reinterpret pre-change receipts. Snapshots contain prior proposed lessons and
regraded training-baseline counts, not an assertion those lessons improved
performance. Subsequent experiments must establish that separately.

## New observations and fresh evaluation

Enabled cycles collect up to 32 previously unseen failed mission observations
from the host's existing `nerve_missions` ledger into immutable
`research_findings` rows in `autoresearch.sqlite3`. The source adapter already
distinguishes supervisor timeouts from unverified/reclaimed work. Intake stores
profile, categorical outcome and provenance digests, never mission payloads,
source paths, generated instructions or credentials. Digests provide integrity
references, not a guarantee of anonymization.

These rows are hypotheses requiring host review. A timeout does not prove that a
model was wrong, that a particular cue caused failure, or what the correct answer
should have been. Intake makes zero provider calls, does not feed findings to a
model, and cannot admit a benchmark or approve a skill. Status exposes a bounded
list under `research_findings`. Pausing autoresearch pauses this intake too.

The next research subloop is to inspect a lead, author genuinely new tasks with
independently established gold, separately review source/semantic novelty and
split separation, and admit a frozen cohort through the existing cohort registry.
Rephrasing old tasks, renaming IDs, changing model profiles or resetting a queue
does not create fresh evidence. Public simulated audit cohorts are explicitly
limited to their procedural reasoning scope; their six final cases cannot satisfy
the independent CCE 30-pair requirement.

## Completion evidence

The goal remains active until the requested scope is verified. In particular:

| Requirement | Evidence required |
| --- | --- |
| Repeated autonomous execution | Actual scheduled runs, persistent lineage and bounded call receipts, including failures and waits |
| Learning between attempts | A later frozen proposal receives independently verified prior training feedback without final/selection/retention leakage |
| Measured improvement | Positive paired gain against the unchanged capable baseline on untouched evaluation, with required uncertainty and no retained-capability regression |
| Model-aware CCE integration | Supported immutable profile, compatible cue, independently measured safety/calibration/latency/cost and all CCE gates |
| Operational adaptation | Approved bounded use under existing NERVE permissions, subsequent verified outcomes and rollback/revocation evidence |
| Paper reproduction | The pinned reproduction protocol and external resource gates in the existing manifest, not substituted simulated tasks |

Neither a passing transport diagnostic, new queue entry, generated lesson,
successful task-local recovery nor a green software test suite alone completes
this goal. Do not promote a candidate until its own evidence satisfies the
existing release authority. Clinical and provider constraints remain in force.

## Live continuation on 13 October 2026

The installed scheduler consumed the frozen v1 audit cohort and registered v2
cohort after the UTC budget reset. Both stopped after the training-baseline
response had malformed citation objects. Each reserved eight native sessions;
each returned one model response before failure. All reservations and evidence
remain consumed. This is failed research, not an accepted improvement.

The returned citations copied entire source records instead of the required
`source_id` and string-array `fields` schema. The registered runner's prediction
prompt now states that schema explicitly. Malformed individual training answers
can also become independently graded failed feedback for the proposer; malformed
evaluation answers remain failures. The old fixed study is preserved unchanged.

The independently reviewed v3 cohort is registered as
`audit-composition-20261013-v3`, manifest
`ef671cbfdda13620f3ea31de9165224e0c28f39e13fa6a018be7243e264cea37`.
It has not been dispatched. Four native sessions remained immediately after the
two prior studies, fewer than the eight required for a new study. A source repair
requires explicit append-only review of its pending revision before it can run;
the cohort, gold, evaluator and original queue record cannot be rewritten.

The new intake also recorded two real supervisor-observed mission timeouts as
pending research leads. Their existence does not supply benchmark gold or prove
that a model or cue caused either timeout. The overall improvement goal remains
unproven and active.

The installed citation diagnostic subsequently used one native session on the
already exposed v1 training cases. Both outputs had valid citation structure;
one answer was correct and one was a reasoning error. It is a protocol check,
not an independent gain or calibrated model evaluation. Three sessions remained.
The explicit [pending queue review](../evidence/agentos-audit-v3-queue-review.json)
then authorized revision
`1dfada0526435c6a38ed8af0db66c96fb6a2a8a4730098a4e32e5117a9904f17`
for the untouched v3 cohort. An installed tick verified `queued_budget` with
eight required sessions and three remaining; no study was replayed and no
reservation refunded. The next UTC daily reset is 2026-10-14 00:00 UTC; dispatch
remains subject to the normal scheduler, model and evidence checks.
The [live receipt](../evidence/agentos-continuity-live-20261013.json) preserves
the failed studies, diagnostic and current queue status.
