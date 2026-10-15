# Goal-linked self-improvement supervision

Run the bounded offline goal:

```sh
PYTHONPATH=src python -m nerve_awim goal run --state /tmp/nerve-goal
PYTHONPATH=src python -m nerve_awim goal status --state /tmp/nerve-goal
```

`tick` advances one subloop; `run` advances up to 100 ticks; `cancel` stops future
ticks. The existing Agent OS bridge also accepts `goal-run`, `goal-tick`,
`goal-status`, and `goal-cancel`. Its goal state is under `--state/improvement-goal`.
Reusing a completed directory returns the evidence without repeating evaluation.

The goal supervises two domain groups. Each has study, sandbox adoption, and
monitoring subloops. A final verifier depends on both monitoring receipts.
Within each study, the existing improvement loop performs training-based
proposal, selection, retained-capability checks, and frozen final evaluation.
The supervisor requires independently validated receipts from every leaf before
marking a parent or the root complete. A failed child blocks the parent.

The clinical example selects a retrieval field from measured synthetic public
research examples. The PerfFlux example selects direct or memoized CPU digest
execution from measured training outcomes. Repeated payloads require 4 hash
operations instead of 12, with identical digest outputs. This measures operation
count, not runtime, GPU performance, energy, or cost. Both examples retain 8
already-working tasks and evaluate 12 final tasks and 12 fresh monitoring tasks.
The capable control already solves the final tasks: there is no gain over it.
The fixtures intentionally expose the weakness of the initial strategy.

Adoption changes only the sandbox policy stored in a receipt. Subsequent tasks
use that policy, including after a new process opens the checkpoint. Monitoring
applies verified feedback to versioned policy state. An isolated corrupted-output
probe verifies rejection, rollback, and execution through the previous strategy.
Healthy policy state remains active separately from that fault-injection copy.
This is a reproducible mechanism demonstration, not a representative application
benchmark or evidence of clinical efficacy, novel tool invention, weight
training, or general self-improvement. Fixture templates repeat across runs;
new state directories do not create scientifically independent holdouts.

## Host integration contract

`GoalOrchestrator` accepts a fixed hierarchy of monitoring groups and registered
leaf handlers with independent validators. Wrap existing bounded loops as leaf
handlers and return evidence; do not grant them deployment authority. Put
dependencies on leaves, with IDs declared earlier in the specification. Every
leaf is required. Include a final verifier of the actual target, rather than a
check that commands exited successfully. No existing production scheduler or
clinical/GPU control loop is globally replaced by this feature.

State is a local development checkpoint, not a new application database or
remote authorization boundary. The directory must be private to the trusted
host. One file lock serializes supervisors, and writes use flush/fsync and atomic
replacement. A running leaf is checkpointed before execution. If execution is
interrupted, a later process records `blocked` and requires host reconciliation;
it cannot safely infer whether external side effects happened. Do not delete
that checkpoint and blindly rerun a side-effecting handler.

Handlers are trusted and must bound their own external calls with timeouts.
The supervisor checks its one-hour-maximum deadline before and after execution;
it cannot preempt arbitrary Python callbacks. Cancellation takes effect between
ticks. Failed validation may retry up to three times when explicitly configured;
exceptions and interrupted execution block without automatic replay. Evaluation
leaves use one attempt to avoid repeatedly optimizing against final evidence.
Budget exhaustion, cancellation, and blocked execution never count as completion.

DeepSynaps and PerfFlux expose the same pinned implementation through their
offline `scripts/nerve_goal.py` entrypoints. These commands use synthetic inputs
and local goal checkpoints only. Live clinical policy and fleet approval gates
retain their existing authority.
