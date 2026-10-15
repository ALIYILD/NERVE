# Memory-guided research coordinator

The host entry point `run_memory_research_coordinator.py` now connects the approved
research-memory planner to an executable, fixed diagnostic. It has one registered
node and bounded subloops over the completed study's 128 training episodes,
20-step windows, eight arms and two regimes. No agent-provided command or source
code can become a task. No plant episode is executed by this coordinator.

The planner revalidates the source study, predecessor chain and scoped approved
memory. A known rejection triggers the diagnostic; other advice returns a waiting
status without claiming or dispatching work. The diagnostic validates the exact
training roster and traces, reports phase/window summaries, and compares paired
goal and prediction errors against the matched frozen and adaptive controls.
Ground-truth gains appear only in retrospective summaries. Validation and holdout
outcomes do not enter diagnostic arithmetic. Prediction calibration is a next
hypothesis, not a demonstrated mechanism or automatically approved experiment.

## Execution and recovery

A shared SQLite journal claims the protocol/scope/receipt identity before work.
Its configuration binds the source hashes, study paths, memory identity and output
location. Concurrent calls at the same output root use the existing nonblocking
supervisor lock. Changed configuration or location cannot reuse the same claim.
A terminal failure is consumed, with no blind retry.

Completed resume recalculates the deterministic diagnostic and requires identical
saved evidence; it does not rewrite the report or run plant episodes. An
interrupted claim can reconcile a complete matching report. Missing or partial
artifacts fail closed. Pure arithmetic may be recomputed for verification, which
is distinct from replaying an experiment. Recreating/deleting the shared journal
is outside these local host guarantees and must not be used to bypass consumption.

Before publishing, the coordinator rechecks memory visibility, authorization and
source hashes. A plan grants no lasting capabilities. The CLI uses local host
research capabilities, not production network authentication. Completion of this
node stops at `new_registered_experiment_required`; it does not select a candidate,
relax acceptance gates, train neural weights or deploy a controller.

## Commands

With the previously generated synthetic receipt and memory artifacts:

```sh
PYTHONPATH=src .venv/bin/python scripts/run_memory_research_coordinator.py \
  --memory /private/tmp/nerve-research-memory-v1/memory.sqlite \
  --directory /private/tmp/nerve-memory-research-v1 \
  --journal /private/tmp/nerve-memory-research-claims.sqlite \
  --study /private/tmp/nerve-evidence-window-study-v1 \
  --claims /private/tmp/nerve-evidence-window-study-claims.sqlite \
  --supervisor /private/tmp/nerve-research-supervisor-v1
```

Repeat the identical command to verify/resume. Preserve the journal and source
pins. For validation:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_evidence_rejection_diagnostic.py -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_memory_research_coordinator.py -v
.venv/bin/python scripts/verify_galahad.py baseline
```

The source manifest pins the research chain, planner, bridge, diagnostic,
coordinator and CLI. It does not yet hash every transitive memory-gateway and
runtime dependency; source hashes are local reproducibility checks, not a signed
supply-chain attestation. Power-loss and storage-device durability have not been
fault-tested, although report publication flushes both file and directory before
recording completion.

## Executed result

The actual coordinator dispatched from approved memory
`59dc328c34e3416eba2ff7ef961269f5`, completed the diagnostic, and journaled one
complete node. A fresh Python process repeated the command, verified the same
report SHA-256 `35d1b0b284b6de803e8714cd6810bc5227126bf7164ddeb17e3d54305bd573f1`,
and preserved both report bytes and modification time.
[Resume evidence](evidence/memory-research-resume-v1.json),
[full diagnostic receipt](evidence/memory-research-coordinator-v1.json.gz).

The diagnostic reconciled 128 training episodes, 10,240 recorded steps and 1,398
recorded updates. It generated 64 windows and 128 matched-control comparisons.
These are reanalyses of completed training evidence, not additional trials.

For the retain-window horizon-1 candidate versus matched adaptive horizon-1,
the drift steps 20–39 had mean goal-error delta **−0.00191449** but prediction-error
delta **+0.00680784**. Steps 60–79 had goal delta **−0.01189233** and prediction delta
**+0.00550098**. Each window pairs eight seeds; negative means lower error. This
localizes the measured tradeoff to portions of the trace, but does not establish
its cause or prove prediction calibration will solve it. The baseline remains
retained, with no new validation or holdout use and no candidate promotion.

Six diagnostic tests isolate roster/arithmetic and confirm that the real worker
rejects fake traces; 16 coordinator tests isolate dispatch, journal, restart and
fault behavior. Their stubs are complemented by the actual saved-receipt run and
fresh-process resume above. These tests do not establish GPU restore, production
remote authentication or clinical deployment readiness.

Full regression: **1,475 tests passed in 110.226 seconds**, zero failures/errors.
[Validation record](evidence/memory-research-coordinator-validation.json).
