# NERVE v2.0 — learning from executed agent tasks

Status: opt-in local research runtime. This extends routing among registered
Python tools. It does not train model weights, generate executable code, or
activate a policy in DeepSynaps Clinical OS, an external agent service or a device.

## Implemented lifecycle

1. A trusted host registers `RegisteredStrategy` handlers, an independent judge,
   a baseline route for each task context, and a versioned contract identifier.
2. An operator bootstraps a tenant/agent deployment namespace. The baseline
   release is immutable and remains available for rollback.
3. A trainer supplies actual `AgentTask` inputs. `learn_from_task` executes all
   registered alternatives for the context and asks the trusted judge to check
   their outputs. Callers cannot supply rewards. Handler failures count as failed
   tasks; evaluator failure stores no partial training rewards.
4. `freeze_candidate` learns a route from training outcomes only, requiring at
   least three complete matched task observations per strategy. Ties preserve the
   current route. The resulting route and evidence snapshot do not change with
   later training.
5. A separate evaluator supplies fresh held-out tasks after freezing. Both the
   candidate and current baseline execute the same tasks, once per arm. Every
   context needs at least five cases. Activation eligibility requires at least
   80% candidate accuracy in every context, no per-context accuracy regression,
   no increase in handler errors, a changed route and a strict total improvement.
   These are functional research gates, not statistically powered or clinically
   validated release thresholds.
6. Passing evaluation does not change runtime behaviour. An independently issued
   operator capability must activate the candidate with the expected current
   generation and a bounded review-reference ID. Concurrent or stale approvals
   fail closed, including after a rollback to an earlier release.
7. `execute` reads one immutable approved route snapshot, executes its registered
   handler, and returns the output with release/generation provenance. It does not
   automatically turn unjudged live outputs into training rewards.
8. An operator can restore a previously approved, same-scope release using
   `rollback`. Subsequent calls use the restored route; already-running calls are
   not cancelled and remain tagged with their original release.

## Host integration

```python
from nerve_awim.agent_learning_v12 import AgentTask
from nerve_awim.governed_learning_v20 import LearningAuthority, GovernedLearning
from nerve_awim.repository_agents_v20 import (
    CONTEXT, REPOSITORY_STRATEGIES, repository_judge,
)

authority = LearningAuthority()  # Keep in trusted host/control-plane code.
trainer = authority.issue('tenant-a', 'inventory-agent', 'trainer')
evaluator = authority.issue('tenant-a', 'inventory-agent', 'evaluator')
operator = authority.issue('tenant-a', 'inventory-agent', 'operator')
runtime = authority.issue('tenant-a', 'inventory-agent', 'runtime')

engine = GovernedLearning(
    'agent-outcomes.sqlite', authority=authority,
    strategies=REPOSITORY_STRATEGIES, judge=repository_judge,
    contract_revision='python-inventory-tools-and-token-judge-v2',
    baseline_routes={CONTEXT: 'regex-inventory'},
)
initial = engine.bootstrap(operator)  # Once per deployment namespace.

# Host supplies actual source-file tasks: >=3 training files, >=5 fresh holdouts.
for task in training_tasks:
    engine.learn_from_task(trainer, task)
candidate = engine.freeze_candidate(trainer)
report = engine.evaluate_candidate(evaluator, candidate, fresh_heldout_tasks)

# After external operator review, not from agent/model output:
if operator_approved and report['status'] == 'passed':
    current = engine.status(operator)
    engine.activate(operator, candidate,
                    expected_generation=current['generation'], reason='review-123')

result = engine.execute(runtime, AgentTask('request-1', CONTEXT, source_text))
# If an operator later requests rollback:
current = engine.status(operator)
engine.rollback(operator, initial['active_release'],
                expected_generation=current['generation'], reason='rollback-124')
```

`training_tasks`, `fresh_heldout_tasks`, `operator_approved` and `source_text` are
host-provided inputs in this integration example, not built-in globals or a public
network API. After process restart, re-create the engine with the same registry,
judge, contract revision and database, issue new host capabilities and call
`status`; do not call `bootstrap` on an existing namespace.

## Separation and persistence

The SQLite ledger stores exact tenant/agent scopes, task IDs, payload hashes,
training outcomes, immutable candidate snapshots, held-out aggregates, releases,
active generations and audit events. Payloads, tool outputs, expected answers and
exception text are not written to the ledger. IDs and hashes can still be sensitive;
this is not anonymisation, encrypted clinical storage or a retention policy.

A task ID or exact canonical payload can be consumed only once within a scope.
Training/holdout overlap is rejected even if the task is renamed. A held-out task
cannot later become training data or be used to evaluate another candidate. A
failed or interrupted evaluation cannot pass or be retried on exposed outcomes.
Training reads only training rows. Exact-match checks do not establish semantic
independence; dataset sourcing and independent labels remain host responsibilities.

`contract_revision` must change when handlers, evaluator semantics, tool/model
versions or policy meaning change. The engine refuses a changed contract in an
existing namespace. It does not cryptographically attest callback code or detect
a host that reuses an old revision incorrectly. Use a new independently reviewed
deployment namespace for a new contract.

The local capability issuer proves only that an object was issued by the current
trusted host. It is not a remote identity provider or proof of human approval.
Do not pass the issuer, database or mutable Python engine to untrusted agent code.
A production service must authenticate users externally, issue narrowly scoped
capabilities and protect the database. No new public MCP write or release tools
are exposed by this change.

Handlers must be trusted pure/read-only operations: training and evaluation replay
alternatives. Python callbacks are not sandboxed and there is no hard callback
execution-time or network isolation. Do not register clinical decisions, device
controls or irreversible tools. Slow, stateful or stochastic model calls require
an isolated host adapter and an appropriate evaluation protocol before use here.

## Actual repository task and measured comparison

```bash
PYTHONPATH=src python benchmarks/v20_governed_repository_learning.py
```

This benchmark uses actual checked-in public NERVE source files, not invented
rewards: four training files and eight disjoint held-out files. The task is to
inventory top-level Python functions. A naive regex tool includes methods and
nested definitions; the other tool uses the AST. A separate token/indentation
implementation judges outputs without calling the AST handler.

At implementation time:

| Policy | Correct held-out files |
| --- | ---: |
| Initial regex route | 2/8 |
| Outcome-selected route | 8/8 |
| Capable fixed AST control, without learning | 8/8 |

The benchmark records source SHA-256 values for reproducibility and exercises
activation and rollback in a temporary database using a simulated host operator.
These results show selection of an existing useful tool. They do not show a gain
over the capable fixed control, live LLM improvement, new skill invention or
clinical performance. Repeated CI executions reuse these known files; they are
regression checks, not fresh independent validation studies.

The full CI suite runs the lifecycle tests and this repository benchmark. Tests
cover successful execution and rollback, process restart, capability forgery and
revocation, tenant/agent isolation, held-out leakage/reuse, insufficient evidence,
evaluator errors, handler-error denominators, per-context regression, capable
baseline rejection, frozen snapshots, contract changes and concurrent approvals.

## Still required for a live agent service

The reusable runtime and real repository-task adapter are implemented. No external
LLM provider or Clinical OS production traffic has been connected. A live service
needs host integration with its authenticated identities, registered read-only
tools, independently verified task outcomes, fresh evaluation datasets and its
own release/rollback controls. Keep proposals separate from operator approval.
