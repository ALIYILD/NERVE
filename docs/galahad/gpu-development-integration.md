# Versioned 7B development evaluator and goal reconciliation

This work is isolated on `codex/nerve-gpu-dev-integration-20261015`, based on
Galahad commit `cb65c81730faeb1efd219d5fc7057788b97a0a8d`. Historical scientific
sources, calibration receipts and the other session's uncommitted holdout work
are unchanged. `GoalOrchestrator` is copied without modification, with its ten core tests,
from outcome-release commit `36339ac06e97ab3f0f4f264098d2985418b21de0`.

## Problem and behavior

The initial exploratory Qwen2.5-Coder 7B adapter scored v3 100/100 against a
20/100 compact baseline. Eighty baseline outputs were format-invalid. That adapter
reused the old score and gate decision functions but did not exercise the full
approved-memory and receipt workflow. It is not a substitute for this integration.

`scientific_gpu_dev_transport.py` explicitly binds Qwen2.5-Coder 7B to the pod's
loopback Ollama API, with no proxy/redirect support. The new baseline uses the
existing six-field scientific JSON schema and abstention instructions. Candidate
v3's preparation, deterministic gates and strict decoder are unchanged. Both
model arms request seed 20261015, temperature zero and at most 128 output tokens.
Always-abstain and seeded-random retain their original deterministic definitions.
The baseline is fixed before this comparison, not repaired after observing it.

`scientific_gpu_dev_study.py` is a separately versioned development evaluator,
forked from the existing v3 study to preserve historical source pins. It restores
the complete approved-memory workflow: host-owned evidence proposal/approval,
retrieval, per-call pre/post authorization, source and dataset binding, durable
single-use external and per-call claims, frozen registration, budgets, negative
receipt preservation and independently replayable public `validate_receipt`.
It requires an explicit exploratory design with pilot-history disclosure; it
does not reuse the 1.5B calibration as authorization for the 7B model.

The primary comparison remains 100 reused development items in five strata,
400 total arm rows and at most 160 inference calls plus one empty preload.
Strict superiority over every control and no stratum regression against baseline
are required for `candidate_requires_review`. Ties retain baseline. This is a
development decision, not a holdout promotion decision or clinical evidence.

## Orchestrator and stores

`scripts/reconcile_gpu_dev_goal.py` binds a durable goal to the exact registration,
report hash and verifier source hashes. Its evaluate subloop calls the public
development receipt validator; it has no model-dispatch or independent scorer.
A complete evaluation can correctly retain baseline. Completion of this
verification goal never means that self-improvement or promotion was achieved.

The study's `claim.sqlite` / `report.json` and external claims journal are canonical
for scientific evidence. `goal.json` is coordination state. This work does not
create a second skill registry or grant Loop 41 promotion authority. The validated
retention contract still requires the complete verified evidence bundle and an
authorized signature; a dev receipt alone cannot select a retained skill.

## Validation and experiment records

The user explicitly lifted the validation pause for Runpod work. Outcome-release's
six retention tests passed. The full suite ran once: 1,479 tests, two errors,
12 skips. The two errors required Git commit metadata missing from the archive.
After restoring the real commit through a Git bundle (with no source changes),
all three tests in the affected adaptation-evaluation module passed. Both logs
are retained; the first run is not relabeled as passing. No full-suite rerun was
performed. Logs: `/Users/aliyildirim/nerve-research-runs/runpod-validation-36339ac`.

The new study and transport passed 13 mocked tests, including failure consumption,
raw-response preservation on revocation, source binding, immutable requests,
model identity, private inputs and zero-call receipt replay. Initial archive
extraction failed on macOS ownership metadata; re-extracting with
`--no-same-owner` fixed the deployment environment before those tests ran.

Real-run preregistration initially failed before claims/inference because the
Runpod shared volume did not preserve mode 0700. Evidence was placed under
`/root/nerve-gpu-evidence` instead. A second preflight found two missing historical
development receipts in the source manifest; those exact files were supplied.
Neither preflight consumed model calls or a registered study.

During execution, repeated hash checks on the network-backed source volume were
slow. All 73 registered source files were copied and verified byte-for-byte on
local pod storage. The source tree was then migrated behind the original path,
with a 0.032-second pause for the reversible path swap. Every registered hash
was verified afterward; the original tree was preserved. Requests, data, policy,
gate and inference budgets were unchanged. The migration receipt is retained,
and this run must not be cited as a clean throughput benchmark.

### Completed result

The public validator accepted the complete 400-row receipt: candidate v3 **100/100**,
stronger baseline **60/100**, always-abstain **40/100**, seeded-random **29/100**.
There were 40 paired gains, zero losses and 60 ties. All gains were correct
deterministic abstentions on conflict/unit-mismatch items; both model arms scored
60/60 on answerable items. The baseline produced 100/100 schema-shaped outputs,
but only 85/100 passed the semantic output contract; 15 conflict outputs failed
that contract and the other 25 abstention-required items were answered incorrectly.
Thus the advantage is not solely a formatting artifact, but it is a hybrid
rule/model policy result, not evidence of autonomous weight learning.

The gate verdict is `candidate_requires_review`; generalization remains
`insufficient_power`. The orchestrator completed its bound verification goal,
recorded `candidate_selected_for_review=true`, and used zero new model calls.
`retained_skill_selected` and `promotion_authorized` remain false. Reopening the
goal returned exactly the same state without reevaluating it.

The run used 160 inference calls (candidate 60, baseline 100) and one empty preload.
Public receipt replay and goal evaluation used no inference. The model was unloaded;
the pod and pre-existing PerfFlux collector were left running. No new candidate
was generated: v3 had no failures on this reused development roster, and this
experiment does not establish autonomous learning or adaptation to new conditions.

All 25 focused integration tests passed: 13 study/transport, two goal-bridge and
ten core-orchestrator tests. The initial copied orchestrator test file imported
unrelated domain helpers absent from this branch; only its ten core tests were
retained, then passed. That initial failure log is preserved.

Aggregate receipt: [runpod-gpu-development-summary.json](evidence/runpod-gpu-development-summary.json).
Full private development evidence, including raw outputs, durable claims,
registration, source-storage receipts and test logs, is archived at
`/Users/aliyildirim/nerve-research-runs/runpod-gpu-integration/nerve-gpu-evidence`.
The aggregate records SHA-256 hashes for the evidence files.
The registered model digest is
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
Bank manifest: `e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6`.

## Remaining boundaries

- Slice 2 is unopened. Its earlier local dry-run receipt is
  `failed_consumed / incomplete_infrastructure`; this GPU dev run does not
  qualify or retry it. No holdout or seed is present in the pod's bank copy.
- New failure-driven proposals must cite observed development failures. If the
  fixed candidate has no failures here, do not invent a mutation or claim learning.
- Broader strata, changed task families, independent confirmation and signed
  retention remain separate prerequisites. No weights were trained or updated.
- Real PerfFlux timings and independent labels are still required from the team;
  the synthetic telemetry workload is not a substitute.
- No promotion, clinical activation, hardware-policy activation or sealed reserve
  evaluation is authorized by this development integration.
