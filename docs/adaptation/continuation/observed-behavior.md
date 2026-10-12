# What NERVE actually did

The continuation adds a real, read-only repository workflow to the existing Agent OS
CLI, using NERVE's registered regex/AST tools, ARC dispatcher, independent token
verifier, SQLite receipts and task correction memory. No source code is executed
or modified, and no model/provider requests are made.

| Run | Observed result |
|---|---|
| Normal workflow | Starts with the capable AST tool; both real files verified, no corrections needed |
| Explicit `recover-regex` scenario | Regex returned seven names on `arc_contracts.py`; verifier expected three top-level functions |
| Verified correction | Host deterministic review checked the alternative against the token-stream verifier and authorized task-local `ast-inventory` reuse |
| Recovery | Reopened the database with new capabilities, resumed the checkpoint and explicitly reaffirmed the correction |
| Next action | AST returned `_identity`, `_strings`, `_timestamp`; independent verification passed |
| Reuse | On `repository_agents_v20.py`, reused AST and verified `ast_inventory`, `regex_inventory`, `repository_judge`, `token_inventory` |
| Completion | Closed the task with three receipts; one correction, one later reuse, one counted review probe |

This is deterministic tool recovery, not an LLM learning new weights or a claim
that NERVE improved on an already-correct AST baseline. The normal starting tool
remains AST. The deliberately weaker regex start is an explicit recovery scenario.
The operator review is a local deterministic verification policy, not a claim
that a human reviewer or a remote identity provider approved the result.

```sh
cd /Users/aliyildirim/nerve-review
PYTHONPATH=src python3 scripts/agentos_bridge.py adaptation-run \
  --repository /Users/aliyildirim/nerve-review \
  --state /tmp/nerve-local-run --report /tmp/nerve-local-run.json

PYTHONPATH=src python3 scripts/agentos_bridge.py adaptation-run \
  --repository /Users/aliyildirim/nerve-review --scenario recover-regex --restart \
  --state /tmp/nerve-local-recovery --report /tmp/nerve-local-recovery.json
```

A single different source can be supplied with `--source path/inside/repo.py`.
The local workflow allows at most three Python files, each at most 12 KiB, inside
the authorized root. It rejects path escapes and invalid Python before dispatch.
The authenticated host boundary remains local capability issuance; this command
is not a remotely exposed authorization service.

Evidence: [normal run](normal-repository-run.json),
[recovery run and complete event trace](recovery-repository-run.json).

# Fresh comparison and performance

A new, digest-frozen version-2 batch uses different Python source templates:
methods, nested functions, quoted definitions, commented definitions, async methods
and decorated methods. There are 60 development and 30 held-out episodes, each with
two files. Reserved templates combine different syntax; the consumed v1 held-out
batch was never reused. Model, provider and clinical validity are not assessed.

| Policy | Development | Fresh held-out |
|---|---:|---:|
| Fixed regex | 0/60 | 0/30 |
| Structured state, no correction reuse | 0/60 | 0/30 |
| Verified correction reuse | 60/60 | 30/30 |
| Capable fixed AST | 60/60 | 30/30 |

Against the capable control, success improvement is **0 percentage points**, with
an observed paired-bootstrap interval of [0, 0]. This finite toy suite does not
prove the policies equivalent for all possible inputs. The recovery path's p95
end-to-end overhead was **95.8%**, above the predeclared 20% ceiling. It includes
additional verification, correction, storage and restart work. Candidate
`adaptation-repository-v2-final` was therefore **rejected**, despite correct recovery.

The profiler identified database setup, connection churn and repeated task-state
work. Initialization now batches adaptation schema creation in one transaction;
planning reuses its current transaction for context checks; duplicate dispatch
checks retain their authorization checks without rewriting the same intent. An
experimental WAL change was discarded because the local profile became slower.
The before/after profiler samples were approximately 0.787/0.757 seconds for twelve
heading episodes; single samples are diagnostic and not a statistically established
speedup. No durability setting, scope check or acceptance threshold was weakened.

The previous optional fast-memory study remains negative versus exact structured
memory. There is no reason to enable learned weights on these results. Production
learning, clinical corrections and live provider spending remain disabled.
