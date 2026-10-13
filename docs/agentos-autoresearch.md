# Continuous Hermes skill research

NERVE adapts the experiment structure in Andrej Karpathy's [autoresearch README](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/README.md) and [agent program](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md), inspected on 2026-10-12 at commit `228791fb499afffb54b46200aca536f79142f117`.

Upstream changes one training artifact, evaluates it under a fixed budget, records outcomes, keeps improvements, and repeats. NERVE applies that structure to procedural advice proposed by Hermes. It does not run upstream's GPU training code or update model weights.

## What can improve

The mutable artifact is a bounded lesson for one declared task scope. The host owns the evaluator, evidence split, accounting, and acceptance rules. A candidate cannot alter those rules to improve its score. Native Hermes receives training feedback to propose advice; selection, retention, and final evidence are separate from the proposal. Baseline and learned arms use the same model and execution limits, with randomized order. Exact decisions and citations are checked by the host.

The audit studies require selection and final gains, no paired regressions, and no unsupported positive decisions. A tie does not establish improvement. The original study makes a candidate eligible for simulated shadow monitoring, with receipts binding its lesson, model, evaluator, and budget. A later paired loss, invalid positive, drift, expiry, or interrupted monitoring run can remove eligibility. Newly registered cohort studies export evaluated experimental advice; they do not yet enter that monitoring path. Neither track authorizes operational activation.

This is task-scoped procedural learning. Synthetic evidence can establish behavior on the evaluated cases; it cannot establish generalized intelligence, clinical reliability, successful production repair, or improvement on unrelated tasks.

## Why a continuous loop sometimes waits

A persistent scheduler can keep looking for eligible work without making an inference every time it wakes. Exhausted evidence remains exhausted: changing IDs, prose, source names, or timestamps cannot turn the same audit case into an independent test. Repeatedly trying candidates against the same final set until one wins would produce a misleading success claim.

The shared native Hermes allowance is 20 sessions per UTC day. An audit study reserves eight sessions before running; a paired shadow check reserves two. Unused reservations are conservatively retained. The separate Claude review ceiling remains $25 cumulative and is not a budget available to the automatic loop. The loop never resets accounting or silently switches to paid inference.

At setup on 2026-10-12, all 20 native sessions were reserved, the frozen audit study was queued, and no audit improvement had been accepted. Waiting for the next UTC budget window is an expected state, not evidence of learning. Future status and immutable receipts are authoritative for subsequent outcomes.

## Inspect the evidence

The bridge is `scripts/agentos_bridge.py` in this checkout. Its host lock serializes scheduled and manual work. The controller commands are:

```sh
python3 scripts/agentos_bridge.py autoresearch-enable
python3 scripts/agentos_bridge.py autoresearch-status
python3 scripts/agentos_bridge.py autoresearch-tick
python3 scripts/agentos_bridge.py autoresearch-pause
```

Enable and pause persist across process restarts. Once configured, pausing also suppresses the legacy scheduled audit retry path so that the next cycle cannot bypass the pause. It does not disable unrelated maintenance collection. Each tick can run at most one study or one paired shadow check. Scheduled bridge cycles provide repetition. The outcome ledger distinguishes `keep`, `discard`, `crash`, and `wait`; a `keep` during monitoring means the candidate remains eligible, not that another independent improvement was proved.

To submit a host-authored simulated shadow task:

```sh
python3 scripts/agentos_bridge.py autoresearch-submit --task /absolute/path/to/task.json
```

The task must contain exactly `id`, `family`, and `bundle`; the bundle follows the typed schema in `src/nerve_awim/agentos_audit_evidence.py` and requires `simulated: true`. Admission checks canonical identity and family against development cases, study cases, and queued evidence. This intake is for monitoring an accepted candidate; it does not create a new training cohort. A producer must supply independently grounded tasks. The controller does not manufacture its own supposedly independent evidence.

When the candidate needs more monitoring evidence, status reports `awaiting_fresh_evidence`. After the original study finishes, the scheduler also consumes new registered cohorts, one per tick, whenever there is no pending legacy shadow task. Once all registered cohorts are consumed without an eligible legacy candidate, it reports `awaiting_fresh_cohort`.

## Register a fresh learning cohort

The host can now admit additional reviewed cohorts without changing the original evaluator, study source, or pending queue:

```sh
python3 scripts/agentos_bridge.py autoresearch-register-cohort \
  --task docs/evidence/agentos-audit-composition-v2.json \
  --review docs/evidence/agentos-audit-composition-v2-independent-review.json \
  --profile qa-release
```

Each JSON cohort contains `id`, `scope`, `limitation`, and `splits` with exactly 2 training, 4 selection, 4 retention, and 6 final cases. Cases contain `id`, `family`, `bundle`, and independently authored `expected` answers. The review binds the canonical JSON SHA-256 through `manifest_sha256`, identifies a `reviewer` and `method`, and attests `gold`, `novelty`, and `split_separation` in `checks`. This is a local host review record, not authenticated reviewer identity. Candidate model output must never serve as its own review.

Admission reserves all case identities and families atomically, checks typed gold against the fixed evaluator, and rejects overlap with earlier cohorts, controls, shadow episodes, or the monitoring inbox. A canonical hash detects cosmetic reuse; independent review must still assess substantive novelty. Registered content and reviews are immutable. Changing an admitted file does not change the stored cohort. Registry/evaluator/runner revisions are bound when an experiment first attempts to run; drift stops a deferred experiment.

The v2 cohort adds 16 public simulated compositions independently checked against the previous 30 cases. It shares the same reasoning primitives and is not a sample of independent production incidents. It supplies one additional learning experiment; more experiments require further independently reviewed cohorts. Advice is evaluated against each cohort's unchanged capable baseline, not cumulatively merged into an operational incumbent skill. No test generator or unlimited source of independent tasks is claimed.

Registered studies now freeze up to four distinct historical lessons and their
independently regraded training-baseline counts, capped at 8 KiB, before proposing
the next lesson. Exact profile, requested model, runner revision and task scope
must match. Training/proposal receipts, source snapshots and requests are
revalidated; rejected or failed studies may contribute valid training evidence
without revealing their later results. Selection, retention and final outcomes
are never supplied to this proposal context. The model's `:free` name is not an
attestation of immutable provider weights. Historical lessons remain untrusted
hypotheses, with no effectiveness or deployment authority. Empty history retains
the previous exact proposal prompt and eight-call budget.

The immutable `learning_snapshots` row and mirrored `learning.json` file bind the
full context and digest to the study. Export verification checks that frozen
context rather than reconstructing a newer history. This adds learning between
attempts; whether it helps must still be measured on untouched tasks.

Enabled ticks also collect bounded failed-mission metadata into the existing
autoresearch ledger's `research_findings` table. These are pending research
leads, not benchmark answers or permission to generate/approve a study. See the
[continuous improvement programme](cce/continuous-improvement.md) for the nested
loops and completion requirements.

`cohort-registry.sqlite3` preserves admission and evidence reservations. `cohort-study.sqlite3` records consumption, prepaid calls, exact requests, responses, and outcomes. Every accepted result is regraded against its frozen input and receipts before export to `autoresearch-cohort-skills/<study-id>/`. Its eligibility is explicitly `experimental_unmonitored`; later controller visits revalidate it and mark mismatches ineligible. Interrupted studies remain consumed and are never replayed. The existing original study remains first in the queue.

Underlying audit inspection commands are:

```sh
python3 scripts/agentos_bridge.py audit-status
python3 scripts/agentos_bridge.py audit-shadow-status
```

Runtime state lives under `~/.agentic-os/nerve`. `autoresearch.sqlite3` stores enablement, an immutable event history, and the evidence inbox. `audit-study.sqlite3` and `audit-shadow.sqlite3` preserve experiment records and receipts; the study snapshot directory preserves its frozen inputs. Receipt-verified accepted advice is exported to `autoresearch-skills/<study-id>/SKILL.md` with `provenance.json`, outside installed Hermes skills. These experimental artifacts are not automatically loaded into production agents. `status.json` and `~/AgentOS-Vault/Memory/nerve-status.md` are summaries, not substitutes for acceptance records. Editing a summary or candidate file cannot approve a lesson.

The installed `com.aliyildirim.nerve.learning` launch agent invokes the bridge cycle every 900 seconds while the Mac is awake and the user session is available. A durable scheduled cycle is the continuous loop; no terminal needs to busy-wait. See [learning operations](agentos-learning-operations.md) for the scheduler and underlying study commands. The earlier [v01 autoresearch prototype](autoresearch-integration.md) is a separate synthetic learning-rate experiment.

The Hermes entrypoint for this workflow is [nerve-autoresearch](../integrations/hermes/nerve-autoresearch/SKILL.md). Its procedural instructions do not confer approval on their own candidate outputs.
