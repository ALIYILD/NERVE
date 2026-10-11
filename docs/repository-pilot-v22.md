# Sealed repository pilot v2.2

The pilot runner adds a persistent study plan to v2.1 shadow collection. Each plan
pins a repository identifier, canonical source paths, training/holdout assignments
and content hashes. Evaluators reserve held-out tasks **before training begins**.
The core learner and shadow collector reject those exact reserved tasks as training.
The pilot additionally refuses to reassign a source path across splits, even if
the file has changed. This improves provenance without changing active routing.

## Run a complete local pilot

Use a durable host-managed database path. The commands below use a disposable
database as an example and execute against the current repository checkout:

```bash
PYTHONPATH=src python scripts/repository_pilot_v22.py plan \
  --db /tmp/nerve-pilot.db --study pilot-001 \
  --manifest benchmarks/repository_pilot_manifest_v22.json
PYTHONPATH=src python scripts/repository_pilot_v22.py collect \
  --db /tmp/nerve-pilot.db --study pilot-001
PYTHONPATH=src python scripts/repository_pilot_v22.py freeze \
  --db /tmp/nerve-pilot.db --study pilot-001
PYTHONPATH=src python scripts/repository_pilot_v22.py evaluate \
  --db /tmp/nerve-pilot.db --study pilot-001
PYTHONPATH=src python scripts/repository_pilot_v22.py review \
  --db /tmp/nerve-pilot.db --study pilot-001
```

Each command may run in a new process. Supply the same `--tenant`, `--agent`, DB
and repository root across calls. The default namespace is compatible with the
v2.1 CLI. Schema creation is additive for existing v2.0/v2.1 databases. A study
cannot reserve tasks already trained, evaluated or reserved for another study.
Do not run the supplied manifest in a namespace that has already used its holdouts.

`plan` requires evaluator/operator authority and reads files only to validate and
hash them; it executes no tool or judge. `collect` runs the active AST inventory
tool on planned training files, then drains shadow learning. It preflights all
training hashes before executing any of them. `freeze` requires complete judged
training evidence for those files, records one candidate and is idempotent.
`evaluate` loads only the pinned held-out inputs after freezing, with the existing
one-use paired evaluation. Changed inputs are rejected before scoring. `review`
reports the manifest hash, candidate, evaluation, current release and recommendation.

The plan is stored in SQLite; source payloads and tool outputs are not. Paths are
metadata and may themselves be sensitive. JSON reports go to stdout, so the host
can store them under its existing access and retention controls.

## Repeat runs and recommendations

A new study needs a new identifier and unused holdout content. It can reuse
previously judged training evidence in the same namespace, but cannot relabel
known source paths from holdout to training or vice versa. The repository ID must
be stable and assigned by the trusted host. Renames, related revisions and semantic
duplicates are not independently detected; source independence still requires
curation. The core APIs only know task IDs/hashes: path-level protection applies
through this pilot runner, not to arbitrary direct submissions of changed files.

Hashes detect accidental changes, not malicious database edits. The host and
local SQLite storage remain trusted. A host with raw database or authority access
can bypass this research workflow. The CLI issues local capabilities for testing;
it does not authenticate separate people. An independently operated evaluator
requires integration with the deployment's identity system.

Recommendations are explicit:

- `collect_training`: no candidate yet.
- `await_independent_evaluation`: candidate frozen, not evaluated.
- `reject_rollout`: no demonstrated gain, failed or incomplete evaluation.
- `stale_candidate_reject_rollout`: the active generation changed.
- `quality_passed_operator_review_required`: the small research quality gate
  passed; review data provenance, cost/latency budgets and the deployment plan.

None of these recommendations activates a release. Operator-controlled activation
and rollback remain available through v2.0; the optional
[v2.3 controller](canary-learning-v23.md) now implements local canary routing.
No provider billing or Clinical OS traffic is connected. Scheduling also remains
the host's responsibility; this change does not create a recurring automation.

Training accumulates at the namespace level, so frozen routes may use previous
studies' training outcomes as well as this manifest's files. Evaluation uses exactly
the manifest's held-out files. Collection should have a single host owner; concurrent
freezes retain one study candidate but may leave an unused candidate record.
The v2.1 bounded queue, resource and failure limits still apply.

## Verified result

```bash
PYTHONPATH=src python scripts/verify_repository_pilot_v22.py
```

The five-process check plans three actual repository training files and five
holdout files, collects evidence, freezes, evaluates and restores a review.
Baseline and candidate both score 5/5, yielding `reject_rollout`, generation zero
and an unchanged active release. These repeatable fixtures verify mechanics;
they do not prove improvement on future or independently sourced tasks.
