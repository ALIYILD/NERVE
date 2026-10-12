# Declarative world-model research increment

This is an **incomplete implementation of the Memento 3 loop plan**. It supplies
an executable, default-off, offline foundation. It does not implement a general
LLM world-model learner or establish an independently useful improvement.
See [implementation-report.md](implementation-report.md) and [backlog.json](backlog.json)
for the distinction between exercised code and remaining work.

## Run from a fresh checkout

Python 3.12 is used by CI. The new core uses only the standard library. The
existing full test suite additionally uses the dependencies already declared in
`.github/workflows/tests.yml` (PyJWT crypto and official MCP SDK).

```sh
export PYTHONPATH=src
python -m nerve_awim.world_model.cli doctor --json
python -m nerve_awim.world_model.cli --db /tmp/nerve-world-model-demo.sqlite3 demo --json
python -m unittest discover -s tests/world_model -v
python benchmarks/world_model/benchmark.py
```

Use a **new database filename for each demo**. A repeated demo cannot reuse its
consumed final sources. The JSON returns real `run_id` and `model_id` values.
Use them with `status`, `report`, `verify`, `shadow`, or `resume`. Flags selecting
the database and fixed scope precede the command. Example:

```sh
python -m nerve_awim.world_model.cli --db /tmp/nerve-world-model-demo.sqlite3 report --run-id RUN_ID --format json
python -m nerve_awim.world_model.cli --db /tmp/nerve-world-model-demo.sqlite3 verify --model-id MODEL_ID --suite replay
python -m nerve_awim.world_model.cli --db /tmp/nerve-world-model-demo.sqlite3 shadow --model-id MODEL_ID --manifest benchmarks/world_model/shadow-manifest.json
```

The demonstration records a wrong prediction before the host produces its
outcome, revises structured rules from evidence, rejects a deliberately bad
executable by replay and independent structural review, freezes the artifact,
consumes final evidence once, reports inconclusive eligibility, marks an
unexecuted shadow alternative unknown, and simulates an atomic rollback. The
scripted proposer sees only training transitions. **Selection/final demo episodes
reuse mechanics and states**, so their replay results are integration evidence,
not independent generalization evidence. The separate benchmark intentionally
uses disjoint parameters and reports the resulting abstentions and no gain.

## Storage, configuration and recovery

`init --config configs/world_model.offline.json` explicitly adds versioned `wm_*`
tables in one transaction; it does not alter legacy tables. Never point this
research tool at production storage. The supplied configuration has `enabled:
false`; copy it outside Git and explicitly set `enabled: true` for `run` or
`resume`. The `demo` command explicitly opts into a synthetic experiment.
`ingest` imports the included training manifest transactionally and labels it
retrospective, without inventing advance predictions. It does not create sealed
evaluation sets. Normal `run` therefore requires a trusted host to populate all
four splits; the standalone runnable path is `demo`.

A run checkpoints each phase, a content hash, attempts, work reservations, and
lease fence. A new process can `resume --run-id ... --config ...` with the exact
original policy. An expired claim can be recovered after 30 seconds. An active
claim rejects a second worker. Phase retries stop after three attempts. A final
evaluation interrupted after consumption stops honestly without reopening its
evidence. Stop reasons distinguish resource exhaustion, missing evidence,
verification failure and inconclusive independent gain. No external writes are
dispatched; an external-effect outbox is not implemented.

Runtime SQLite files and logs belong outside Git. Tombstones remove logical
payloads and invalidate dependent models. They are **not physical erasure**;
operators must separately handle SQLite free pages, backups and copied artifacts.
Only synthetic observations are supported by this increment.

## Boundaries and limitations

The executable language is a finite exact-state transition table. It has no
imports, expressions, arbitrary functions, loops or system calls. A fixed trusted
interpreter runs in a separate process with bounded JSON, CPU/file/output limits,
a clean environment and a process-group timeout. It is **not an OS sandbox** for
hostile Python. Arbitrary Python always fails closed. Linux applies a 256 MiB
address-space cap; macOS does not reliably enforce that cap and `doctor` reports
it unavailable. Memory-hard isolation on macOS is not demonstrated.

The structural fidelity reviewer is separate from the compiler. It checks the
finite representation, not the truth of environmental rules, and is not a formal
proof or LLM review. Hidden-state contradictions cause abstention/revision needs;
there is no learned hidden-state reconstruction. No live provider adapter is
available; the Hermes bridge accepts explicit offline fixtures only and denies
live calls until durable cost reservations are integrated. There is no API key
configuration or credential reading in this package.

The trusted local host reuses NERVE `LearningAuthority`; local capabilities are
not remote authentication. The CLI is locked to a synthetic scope and denies all
operator endpoints. The existing MCP server exposes only inspection when a host
injects an auditor binding; the normal server is unchanged. No caller-supplied
tenant can alter that binding. Simulated release bundles exercise generation
checks, integrity fallback and whole-bundle rollback; they never activate tools,
clinical actions or devices. The sensor adapter reports unavailable on outage
and supplies no stochastic prediction or control-readiness claim.

JSON `operation_completed: true` means the operation/report succeeded, not that
the model is eligible. Exit codes: 0 operation completed, 2 invalid input,
3 authority/policy denied, 4 verification failure, 5 budget exhausted,
6 unavailable dependency, 7 stale concurrency, 8 integrity failure. A reported
inconclusive run can return 0; inspect its `stop_reason` and `eligibility`.
