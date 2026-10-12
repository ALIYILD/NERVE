# Local commands and operational recovery

Run from the repository root with Python 3.10+. Runtime has no new dependencies.
Research additionally uses NumPy 2.2.6 (BSD-3-Clause), on CPU. No upstream RoboTTT
code or weights are vendored. The checked sources are the
[NVIDIA project](https://research.nvidia.com/labs/gear/robottt/) and
[paper](https://arxiv.org/abs/2607.15275); neither establishes NERVE performance.

```sh
export PYTHONPATH=src
python3 scripts/agentos_bridge.py adaptation-inspect --output /tmp/nerve-inspection --state /tmp/nerve-adapt
python3 scripts/agentos_bridge.py adaptation-validate-config --config configs/adaptation/default.json --state /tmp/nerve-adapt
python3 scripts/agentos_bridge.py adaptation-demo --scenario resume --synthetic --state /tmp/nerve-demo-resume
python3 scripts/agentos_bridge.py adaptation-demo --scenario injection --synthetic --state /tmp/nerve-demo-injection
python3 scripts/agentos_bridge.py adaptation-demo --scenario budget --synthetic --state /tmp/nerve-demo-budget
python3 scripts/agentos_bridge.py adaptation-demo --scenario kill-switch --synthetic --state /tmp/nerve-demo-kill
python3 scripts/agentos_bridge.py adaptation-status --task-id demo-resume --synthetic --state /tmp/nerve-demo-resume
python3 scripts/agentos_bridge.py adaptation-reset --task-id demo-resume --reason operator-reset --synthetic --state /tmp/nerve-demo-resume
python3 scripts/agentos_bridge.py adaptation-replay --suite configs/adaptation/suite-v1.json --adaptation-mode shadow --state /tmp/nerve-shadow --report /tmp/nerve-shadow.json
python3 scripts/agentos_bridge.py adaptation-evaluate --candidate adaptation-v1 --split development --suite configs/adaptation/suite-v1.json --state /tmp/nerve-evaluation --report /tmp/nerve-development.json
python3 scripts/agentos_bridge.py adaptation-evaluate --candidate adaptation-v1 --split heldout --suite configs/adaptation/suite-v1.json --state /tmp/nerve-evaluation --report /tmp/nerve-heldout.json
python3 scripts/agentos_bridge.py research-fast-memory-train --synthetic --config configs/adaptation/research-config.json --budget configs/adaptation/research-budget.json --state /tmp/nerve-research --report /tmp/nerve-fast-memory.json
python3 scripts/agentos_bridge.py research-fast-memory-evaluate --synthetic --checkpoint /tmp/nerve-fast-memory.json --suite configs/adaptation/research-suite.json --budget configs/adaptation/research-budget.json --state /tmp/nerve-research --report /tmp/nerve-fast-evaluation.json
```

Use a fresh synthetic task ID or directory for a fresh demonstration. Reusing an
existing task ID is intentionally rejected. Do not delete production ledgers to
work around idempotency checks. The public synthetic suite is frozen by digest;
it is not a secret clinical holdout. A revised candidate after held-out evaluation
requires a genuinely fresh batch and reviewed suite version, not renamed examples.
Direct replay cannot read held-out cases. Evaluate consumes the claim before work,
so an interrupted held-out attempt remains consumed.

Mode off is the constructor/config default. Shadow adds no extra tool execution
and does not apply corrections. Active-development is explicit for synthetic
commands. No live provider spending is supported; nonzero provider budgets are
rejected. Learned memory stays outside production startup and routing.

Backend outage or corrupt checkpoint: stop the opted-in task and inspect its ARC
decisions and protected tool receipts. Do not attach an unguarded dispatcher or
fall back to a fresh task. Restore a SQLite backup with its receipts, use the same
schema/configuration, reauthenticate the task grant and resume only a current
checkpoint. Unknown schema/config versions fail closed. Additive schema rollback
means disabling new tasks while retaining all existing tables and receipts;
there is no destructive down migration.

Uncertain tool execution: use `ArcRuntime.reconcile` only after observing the tool's
authoritative state, then `AdaptationCoordinator.reconcile` to repair the task's
receipt gap. Impossible reconciliation remains review-required. Transport failures
open a per-task tool circuit; only a registered alternative may be selected.
Transient verifier readback retries have bounded exponential backoff and never
re-execute the effect. Deadlines are checked at planning, dispatch and outcome
boundaries; a synchronous external handler must supply its own cancellable timeout.
This code does not safely preempt arbitrary external side effects.

Suspicious correction or scope breach: revoke the correction/capability, then
use the scoped kill switch. Constraints, unresolved risks and receipts remain.
Clinical/factual corrections are refused until a domain reviewer authority exists.
Task reset removes reusable influence, not executed actions, mandatory constraints,
unknown outcomes or consumed budgets. Close clears active memory and denies reuse.

Unexpected cost: adaptation makes zero provider requests; a cost event therefore
indicates another host path that must be disabled and reviewed. Regression: kill
adaptation for the scoped host immediately:

```sh
python3 scripts/agentos_bridge.py adaptation-kill --synthetic --reason regression --state /tmp/nerve-demo-resume
```

Existing deployed route/mode rollback stays in `ArcOperations.rollback` and the
existing `arc-rollback --manifest-id <id> --review-ref <review>` command. It checks
the exact current release and operator authority. No adaptation candidate in this
change is deployment-approved or mapped to an executable release. Incompatible
task checkpoints pause for review; rollback never silently drops task constraints.
See `tests/test_arc_review.py` for exercised existing release/rollback gates.

Retention: examples and fast-memory artifacts here are synthetic only. A production
host must configure protected-store retention/deletion covering referenced bodies,
derived examples and numerical checkpoints before enabling real data. Hashes do
not anonymize data. No production retention policy or live connector is supplied.

# Continuation: actual repository work

`adaptation-run --repository <root> --state <local-state-directory>` inventories
NERVE source files using the existing capable AST tool and independent verifier.
`--source <relative-python-file>` selects a different authorized file.
`--scenario recover-regex --restart` explicitly tests recovery from the weaker regex
tool and reopened task state. This command acts only on local source; it needs no
`--synthetic` flag because it is a real read-only repository operation. It makes no
provider calls or source edits. The general production feature default stays off.
See [observed behavior and reproduction commands](continuation/observed-behavior.md).

The fresh evaluation suite is `configs/adaptation/repository-suite-v2.json`.
Candidate `adaptation-repository-v2-final` was frozen on development, evaluated once
on the fresh held-out split and rejected. Its capable-control success gain is zero;
p95 overhead remains above the ceiling. Do not reuse either consumed held-out batch
for another revised candidate. The v2 fixture suite does not establish clinical or
provider-backed learning benefit.
