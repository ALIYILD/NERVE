# Persistent uncertainty operator guide

This package preserves conflicts through NERVE's existing execution and memory
paths. A successful tool call, an agent's summary, a model vote, a hash match or
a human status label does not establish factual resolution. An unresolved report
remains open for action gating. Existing tenant permissions and release review
remain necessary.

The current verification is local and synthetic. No live provider inference,
paid call, patient data, clinical activation or deployment is authorized by
these commands. The pilot evaluation remains ineligible for promotion.

## Reproduce the offline workflow

Run from the repository root. The commands below use one disposable SQLite file
for the governed engine, uncertainty records, checkpoints and evaluation receipts.
They do not modify the running Agent OS database:

```sh
UNC_ROOT=$(mktemp -d /private/tmp/nerve-uncertainty.XXXXXX)
UNC_DB="$UNC_ROOT/learning.sqlite3"
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli --help
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli doctor --state "$UNC_DB" --json
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli demo --state "$UNC_DB" \
  --offline --output "$UNC_ROOT/demo" > "$UNC_ROOT/demo-command.json"
```

`doctor` describes offline readiness, not provider or deployment readiness. The
demo runs the real `HermesAgentRuntime` adapter with an explicitly scripted,
adversarial provider and uses the actual governed dispatcher/policy path. The
fixture provider's behavior is not a measurement of an LLM.

Extract identifiers from the actual receipt instead of inventing task/run IDs:

```sh
UNC_TASK=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["task_id"])' "$UNC_ROOT/demo/demo.json")
UNC_CONFLICT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["conflict_ids"][0])' "$UNC_ROOT/demo/demo.json")
UNC_RUN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_id"])' "$UNC_ROOT/demo/demo.json")
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli inspect --state "$UNC_DB" \
  --task-id "$UNC_TASK" --json
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli verify --state "$UNC_DB" \
  --conflict-id "$UNC_CONFLICT" --config configs/uncertainty.offline.json
```

The offline verifier has no authenticated external primary record. An
inconclusive verification normally returns **exit 4**, leaves the conflict open
and receives no resolution credit. Exit 5 means budget exhaustion; exit 6 means
an unavailable verifier/dependency. Do not interpret a nonzero verification exit
as a reason to erase or recreate the task. Resume the existing demo checkpoint:

```sh
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli resume --state "$UNC_DB" \
  --run-id "$UNC_RUN"
```

Expected: the authoritative open conflict is still present, the output preserves
its qualification, and `repeated_calls` is zero. `resume` does not trust old
checkpoint conflict lists over current ledger state. Deleted/stale sources and
missing state produce an explicit unavailable result.

CLI exit codes are 0 completed, 2 invalid input, 3 denied, 4 inconclusive/failed
verification, 5 budget exhausted, 6 unavailable dependency, 7 stale/concurrent or
consumed state, and 8 integrity failure. A successful report command can describe
an unsuccessful or ineligible experiment.

## Evaluate, freeze and report

Run selection before opening the sealed final split. The code, dataset and policy
hashes must remain unchanged between selection, freezing and final evaluation:

```sh
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli evaluate --state "$UNC_DB" \
  --suite paired-conflicts --split selection > "$UNC_ROOT/selection.json"
UNC_EVAL_RUN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_id"])' "$UNC_ROOT/selection.json")
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli freeze --state "$UNC_DB" \
  --run-id "$UNC_EVAL_RUN"
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli evaluate --state "$UNC_DB" \
  --suite paired-conflicts --split sealed-final --run-id "$UNC_EVAL_RUN" \
  > "$UNC_ROOT/sealed-final.json"
PYTHONPATH=src python3 -m nerve_awim.uncertainty.cli report --state "$UNC_DB" \
  --run-id "$UNC_EVAL_RUN" --format json > "$UNC_ROOT/report.json"
```

A sealed split is reserved before execution and remains consumed after an
interruption. Do not repeatedly restart exposed final cases until they pass.
Fresh databases are useful for reproducing the published smoke suite, but they
do not make public cases unseen or independent again. A new promotion claim
requires new, independently reviewed evaluation families.

The four arms measure existing behavior with the fixture provider, an extra
prompt instruction, persistent conflict state, and full verification/gating.
Report fixture calls, abstention, answer coverage, preservation, unsupported
certainty and uncertainty-policy completion together. These fixtures lack
independent factual-outcome and blinded human labels: factual accuracy,
factual confident-error rate and model benefit are **unmeasured**. A reduction
in unsupported certainty is not proof of fewer factual errors. Differing answer
coverage prevents a matched-coverage benefit claim. No calibrated probabilities
are inferred from model confidence or source counts.

## Identity, flags and integration boundaries

CLI identity comes from the local host UID and a host-issued in-process capability.
There is no tenant, approver or authority-granting flag. `--state` selects a file,
not a different identity. In-process capabilities are not remote authentication.
Do not expose this CLI or its capability issuer as an unauthenticated service.

Existing applications remain unchanged until their host explicitly configures
uncertainty support. The pilot/release recommendation is `shadow`. Host adapters
use the existing store and authority:

```python
from nerve_awim.uncertainty.ledger import Ledger
from nerve_awim.uncertainty.policy import Policy
from nerve_awim.uncertainty.adapters import UncertaintyAdapter

# engine, runtime_actor and task_id must come from the authenticated host.
ledger = Ledger(engine)
policy = Policy(ledger)
adapter = UncertaintyAdapter(
    ledger, runtime_actor, task_id=task_id,
    dependency_claim_ids=host_selected_claim_ids, required=True,
)
```

`Ledger(engine)` performs additive schema creation in that engine's SQLite file.
This is an explicit experimental construction step, not permission to migrate a
production database. The CLI's default path is
`~/.agentic-os/nerve/uncertainty.sqlite3`, overridden by
`NERVE_UNCERTAINTY_STATE`; use explicit disposable state for this handoff. A real
application integrates `Ledger` with its existing engine/database rather than
creating another orchestrator or memory service.

Implemented boundaries include:

- **Hermes learning:** `propose_and_evaluate(..., uncertainty=adapter)` passes a
  mandatory authoritative envelope to research and skill-builder roles, restores
  conflicts omitted from summaries, gates dependent learning and validates the
  final uncertainty result. The context's persistent binding rejects later
  adapter omission, including after restart.
- **Scoped memory:** enabled `TrustedMemoryLedger.retrieve` and `approved_pool`
  require the adapter and return records with their uncertainty envelope.
  Ordinary approved memory remains advisory; approval does not resolve a newly
  discovered conflict or confer action authority.
- **Governed execution:** `Policy.assess` binds host-owned dependencies and risk
  requirements; `Policy.bind` connects that assessment to an execution identity.
  The actual `GovernedLearning.execute` boundary checks the current revision,
  status, action, expiry and existing permissions. Enabled contexts cannot omit
  an assessment. Direct training/evaluation, shadow and canary alternative paths
  reject bypasses of that context.
- **Memento world models:** `WorldModelUncertainty` requires the same store and
  authority as the rulebook. Reviewed rule/dependency bindings are immutable.
  Disputed rules remain hypotheses; coordinator, registry/planning and release
  hooks retain uncertainty and invalidate stale dependent plans. A replay score
  or rule proposal is not contrary-evidence resolution.
- **Release and monitoring:** `ReleaseEligibility.enable(operator, context)` and
  `bind(evaluator, candidate_id, run_id)` refer to complete stored, scoped,
  hash-bound evaluation receipts. Existing activation, canary start/promotion
  and monitoring enforce the gate. Current scripted evidence remains ineligible,
  even if a caller changes a JSON `eligible` flag. Existing canaries stop or
  monitored releases return to the compatible incumbent when the gate denies.

Unrelated older standalone agents, external dashboard workers, network services
and deployment environments are not automatically uncertainty-enabled. No live
API endpoint is invented by these adapters. The combined adaptation/Memento demo
and its source-manifest readiness evidence are documented separately in the final
implementation report; do not infer that evidence from the standalone demo.

## Budgets and unavailable verification

The reviewed offline profile allows at most three checks per conflict, twelve per
task, 30 seconds per call and 180 seconds per task, with zero paid-call budget.
Reservations are durable before tool invocation. Canonical duplicate requests
reuse receipts; repetition requires an observed permitted reason and does not
reset counters. A completed check with empty or irrelevant evidence does not close
a conflict.

Verification enforces a host response deadline with four bounded daemon read
workers. A timed-out callback may continue executing trusted read code; its late
result cannot update the ledger. Its receipt remains uncertain and is not blindly
replayed. These registered read callbacks must enforce their own destination,
access and side-effect constraints. A daemon worker is not an OS sandbox and does
not forcibly terminate arbitrary Python. Saturated worker slots yield an explicit
unavailable result rather than unbounded threads.

The provider integration has no new paid fallback. A missing credential,
unavailable source/service, malformed response or unresolved disagreement stays
visible. Live provider verification requires a separate authorized configuration,
known pricing and finite spending limits. These offline commands perform no paid
inference or training.

## Migration, retention and rollback

Back up a disposable or otherwise explicitly authorized existing store before
constructing new adapters. SQLite's backup API captures a coherent snapshot:

```sh
python3 - "$UNC_DB" "$UNC_ROOT/pre-change.sqlite3" <<'PY'
import sqlite3, sys
from pathlib import Path
source_uri = Path(sys.argv[1]).resolve().as_uri() + '?mode=ro'
with sqlite3.connect(source_uri, uri=True) as source:
    with sqlite3.connect(sys.argv[2]) as target:
        source.backup(target)
PY
```

Do not copy a database file over a running service or automatically migrate
production storage. Unsupported schema versions fail explicitly. Additive tables
preserve historical governed rows; use the existing repository migration and
release review process for any operational adoption.

Rollback changes the compatible policy/model/release route through the existing
`GovernedLearning.rollback` or world-model release interface. It must preserve
current uncertainty records, source revisions, checks, reservations and events.
Do **not** restore an old database/checkpoint to remove conflicts. Rebuild decision
assessments and cached plans against the current ledger revision. Shadow work and
read-only investigation can continue while promotion is blocked.

The uncertainty ledger does not introduce an automatic destructive retention job.
Use the host's authorized retention policy; source deletion invalidates dependent
assessments while retaining necessary provenance/history. Reports and ordinary
logs must not contain credentials, patient data or unrestricted source payloads.
The example artifacts stay under `/private/tmp` and contain synthetic records.

## Verification commands

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_uncertainty_*.py' -v
PYTHONPATH=src python3 -m unittest discover -s tests
node --test tests/test_checkpoint_discovery.cjs
```

See `implementation-report.md` for observed test counts, research limitations,
blocked environments, source revisions and deployment status. Passing local tests
establishes implemented/offline-verified behavior, not provider verification,
clinical efficacy, calibrated uncertainty or production readiness.

## Combined demonstration

From the repository root, choose a new disposable database path:

```sh
PYTHONPATH=src python3 -m nerve_awim.uncertainty.combined_demo --state /private/tmp/nerve-combined-demo.sqlite3
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_uncertainty_combined.py" -v
```

The demo requires a fresh database and preserves an existing one by refusing to overwrite it. Its explicit synthetic host composes ARC, task adaptation, uncertainty and Memento with one authority and database. Expected receipt: `passed: true`; an initial failed tool result, a verified correction, a later affected action blocked with zero handler effects, independent work verified, affected world-model freeze denied, and conflicts/receipts preserved after restart/reset. Provider calls and paid cost are zero. Production activation and learned-model gain remain false.
