# Real-task shadow adapter v2.1

This adapter connects the governed learner to an executable repository-inventory
workflow. The default active tool is the capable AST inventory tool. Shadow
training can select among registered tools, but cannot change an active release.
It does not connect a downstream clinical application, external LLM providers or
patient traffic.

## Run on selected repository files

From the repository root with Python 3.10+:

```bash
PYTHONPATH=src python scripts/repository_shadow_v21.py run --db /tmp/nerve-shadow.db \
  --file src/nerve_awim/identity_v26.py \
  --file src/nerve_awim/recovery_v24.py \
  --file src/nerve_awim/key_rotation_v28.py
PYTHONPATH=src python scripts/repository_shadow_v21.py report --db /tmp/nerve-shadow.db
PYTHONPATH=src python scripts/repository_shadow_v21.py propose --db /tmp/nerve-shadow.db
```

Use a durable host-managed database path for persistent collection. `/tmp` above
is a disposable example. `--tenant` and `--agent` select the local namespace;
they are not authentication. Only the trusted host should invoke this CLI.

`run` executes the active tool, then drains shadow collection in a separate phase.
An application host should return the result to its caller before scheduling
`drain`; this CLI is a sequential batch runner. Explicitly selected UTF-8 `.py`
files must resolve within `--root`, including symlink resolution. Source is read,
never executed. Each file and canonical task payload have a 16 KiB limit.
The tool result is available through the Python API; CLI output contains only
aggregate evidence and release metadata, not source or function inventories.

After freezing, give the candidate ID to a separate evaluator using at least five
previously unused files. Example for a fresh database trained only as above:

```bash
PYTHONPATH=src python scripts/repository_shadow_v21.py evaluate --db /tmp/nerve-shadow.db \
  --candidate CANDIDATE_ID \
  --file src/nerve_awim/adaptive_calibration_v19.py \
  --file src/nerve_awim/recovery_v25.py \
  --file src/nerve_awim/drift_v14.py \
  --file src/nerve_awim/coverage_v18.py \
  --file src/nerve_awim/risk_v17.py
```

The learner sees no held-out outcomes before freezing. Exact task IDs and payload
hashes cannot be reused across training/holdout in a namespace. Atomic reservation
happens before shadow judging. Failed judging consumes the task without rewards;
it cannot be retried until a favourable answer appears. Semantic duplicates and
independence of data sources remain the evaluator's responsibility. The same
person running this example is not independent human evaluation.

There is deliberately no CLI activation command. Review candidates through the
existing v2.0 operator API, with independently authenticated host identities,
generation checks and rollback references. No activation is attempted by this
adapter, its verifier or its CI workflow. The separate
[v2.3 controller](canary-learning-v23.md) provides operator-approved local canary
routing. Provider billing integration is not included.

## Host integration

```python
from nerve_awim.shadow_learning_v21 import ShadowLearning

# engine and actors come from the trusted host's v2.0 setup.
shadow = ShadowLearning(engine, runtime=runtime_actor, trainer=trainer_actor)
result = shadow.execute(task)   # same result shape as engine.execute
# Return result to the caller. Later, outside the request path:
collection = shadow.drain(limit=32)
report = shadow.report(auditor_actor)
```

Only host-registered, bounded, pure/read-only handlers are appropriate: shadow
training re-executes all alternatives. The active handler executes once for the
caller. Its actual output is independently judged; separate matched re-executions
provide training rewards. These are different observations and are labelled as
such. Mutable returned values cannot change the queued observation.

`execute` snapshots the active release and preserves the handler's original
exception. It performs no judging or alternative execution. Input validation,
the release read and copying still add overhead. Training failures never replace
the active result. Collection may affect shared resources if the host runs it
concurrently; this library is neither a process sandbox nor a latency guarantee.
One adapter instance has one owning thread; the host controls scheduling, timeouts,
resource budgets and remote authentication. Capabilities are local process objects.

The pending queue is bounded to 32 tasks by default (maximum 128), lives only in
memory, and drops additional observations when full. Registered output size must
also be bounded by the host. The queue is not durable and is lost on restart;
drained aggregates and training survive. Interrupted drains remain explicitly
pending/unjudged in the database and cannot be replayed. Drops are counted only
within the current adapter process. This is suitable for an opt-in research pilot,
not lossless production telemetry.

## Evidence and limits

`gl_shadow` stores IDs, hashes, release/generation, strategy, collection timestamps,
judged success, handler errors, unjudged/interrupted status and measured active
handler latency. It stores no source, output or exception text. IDs and hashes
are not anonymisation. Apply appropriate access controls and retention to the DB.
Reports count unique accepted tasks, not every repeated traffic request; rejected
duplicates/holdouts and queue drops are separately reported by collection.

Costs are `null` with an explicit unknown status. They are not guessed as zero.
There is no external LLM billing data and no cost or latency promotion gate yet.
The existing quality gate still requires strict improvement with no context
regression. Do not use these small sample thresholds as a production rollout
standard.

Run the cross-process integration verifier:

```bash
PYTHONPATH=src python scripts/verify_shadow_v21.py
```

It collects three actual NERVE source-file tasks, restores aggregates in another
process, freezes a proposal and evaluates five disjoint source files. Both active
and proposed tools score 5/5. The proposal is **rejected because there is no gain**,
and the active release remains unchanged. It also proves that a held-out task
cannot subsequently become shadow training. These are fixed same-repository CI
fixtures, not fresh external validation or evidence of general model improvement.
For a real study, supply independently sourced future tasks and retain the strong
fixed control; do not claim repeat CI runs as new evidence.
