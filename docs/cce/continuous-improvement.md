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
