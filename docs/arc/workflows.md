# Local and synthetic workflow verification

The ARC workflow adapter extends `GovernedLearning.execute` and its existing
SQLite database. It registers the repository's real `ast_inventory` handler and
checks its output independently using `token_inventory`. Submitted Python text
is parsed, never executed. Outcomes and dispatch intent are persisted in the
same database as the governed engine's releases and audit events.

`src/nerve_awim/arc_workflows.py` exposes:

- `build_workflow_engine(path, tenant='synthetic', ...)`: host-created engine,
  scoped runtime/operator capabilities, ARC runtime and registered tools.
- `run_workflow(path, scenario, mode='full')`: an opted-in local workflow run.
  The default path enforces decision checks and outcome verification. Existing
  unrelated execution entry points are not enabled by this factory.
- `SyntheticClinicalBoundary`: a typed, synthetic-only referral preparation
  boundary. No DeepSynaps referral API contract, endpoint or credential was
  found in this repository. Real API verification remains blocked on an
  authorized contract and integration environment.

Registered actions are `inventory`, `prepare-draft`, `request-information` and
`await-review`, plus provider-selectable `no-action` for explicit abstention. No external referral submission or treatment action is
registered. The clinical draft always has `submitted: false` and
`review_state: awaiting_clinician_review`.

A clinical assessment requires `assessment_id`, `tenant_scope`, `captured_at`,
`valid_until`, `findings` and boolean `approved`. The adapter excludes wrong-scope
and inaccessible records before validation, snapshots or output. Missing facts
produce clarification; stale, future-dated, unapproved or conflicting facts
produce review. A fresh approved assessment can populate a synthetic draft.
Arguments are bound to the content hash of the authorized evidence at both
proposal and dispatch. Verification checks exact source fields, citation hashes,
unknowns and review state. These are engineering checks, not clinical efficacy
claims.

The returned `verified` flag means the requested inventory or draft objective
completed. A correctly recorded clarification can have a verified runtime
outcome while the original task's `verified` remains false. The distinction is
intentional: abstention is not fabricated task completion.

Run the focused acceptance suite from the repository root:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p test_arc_workflows.py -v
```

Run the real local slice and its missing-input, parser failure and restart cases
in disposable storage:

```sh
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from nerve_awim.arc_workflows import run_workflow
with TemporaryDirectory() as root:
    source = Path('src/nerve_awim/repository_agents_v20.py').read_text()
    cases = [
        {'task_id': 'success', 'source': source},
        {'task_id': 'missing', 'source': None},
        {'task_id': 'failure', 'source': 'def : invalid'},
        {'task_id': 'restart', 'source': source, 'restart': True},
    ]
    for i, case in enumerate(cases):
        r = run_workflow(Path(root) / f'{i}.sqlite3', case)
        print(case['task_id'], r['action'], r['status'], r['verified'],
              r.get('restart_same_outcome'))
PY
```

Expected rows: success/inventory/succeeded/true; missing/request-information/
succeeded/false; failure/inventory/failed/false; restart/inventory/succeeded/
true with `restart_same_outcome: true`. The restarted dispatcher returns the
persisted outcome without a second handler invocation.

`mode='baseline'` and `mode='structured'` are offline evaluation ablations and
require explicit host argument `offline_evaluation=True`. They are not release
modes. The baseline uses the existing governed dispatcher; the structured
ablation retains decision authorization but intentionally omits semantic
verification to measure unsupported completion. Both retain the same inputs,
registered handlers and host selection policy. They do not constitute a
historical clinical baseline: the clinical boundary is new and synthetic.
`outcome_verified=False`, `tool_failure=True`, fixed `now` and
`strategy='conservative'` are deterministic local fixture controls. No paid
provider, training job or external tool is called.

Persisted ARC `shadow` mode yields a proposed decision without handler effects;
`off` blocks this explicitly opted-in workflow's ARC execution rather than
falling back to an unguarded path. Both retain audit history. Other legacy
entry points and production rollout remain governed by the release and coverage
report in the implementation handoff.
