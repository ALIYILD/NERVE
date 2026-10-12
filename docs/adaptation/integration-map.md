# Lifecycle integration

`ArcRuntime.propose` checks opted-in task state before accepting a new plan and
records that plan in the same transaction as the ARC decision. Existing duplicate
fingerprints return the existing decision without consuming another task step.
`ArcRuntime.execute` writes intent before dispatch; the governed dispatcher checks
the task again when consuming the execution permit. The final ARC outcome and
task receipt commit together. A crash leaves intent/pending state and cannot
silently replay the effect. Reconciliation consults ARC's authoritative ledger;
external uncertainty must first be resolved by the host operator.

AdaptationCoordinator owns reference-only task context. A host planner reads
verified corrections and proposes a new ordinary ARC decision. Corrections do
not rewrite tool policy, approve a write, or select a new global release. The
synthetic heading/fallback planner in adaptation_replay exercises this boundary.
Every revised plan still traverses ARC approval and evidence validation.

The task grant API is a trusted host boundary. It does not authenticate remote
users or decide patient access. Production hosts must map their authenticated
subject permissions into grants; those integrations remain intentionally off.
A task-specific snapshot records evidence authorization before that reference
can be used in a correction or adapted decision. Direct agent-scoped evidence
from another task is rejected. Agent sharing is not enabled.

A restored process needs fresh grants and explicit re-affirmation of corrections
whose original reviewer capability no longer exists. Checkpoints cannot rewind
receipts or reset budgets. A kill switch pauses tasks with constraints intact.
The host can inspect events and metric counts without retrieving protected bodies.

All currently shipped agent adapters remain unchanged unless an explicit
AdaptationCoordinator is attached to ARC. Existing non-ARC adapters are ineligible
until host authentication, independent verifiers and task lifecycle hooks are
provided; this is a named integration boundary, not verified live integration.

Continuation: `adaptation_repository.py` registers the existing regex/AST inventory
functions with the same governed dispatcher and an independent token-stream verifier.
`adaptation-run` authorizes only bounded local Python source paths. Normal execution
starts with AST; an explicit `recover-regex` scenario demonstrates recovery and memory
reuse without modifying/executing source. This local repository boundary is now wired;
remote Hermes/MCP/clinical/device boundaries retain their existing eligibility limits.
