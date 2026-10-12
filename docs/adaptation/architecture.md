# ADR: task adaptation and experimental external memory

The governed SQLite ledger remains the persistence boundary. ARC is the only
dispatcher; adaptation hooks execute in ARC's proposal, dispatch-intent, dispatch
permit and outcome transactions. Existing ARC limits (five decisions per task)
are stricter than the proposed twenty-action ceiling and remain authoritative.
Off and shadow do not modify decisions. Explicit active-development tasks use
host-issued per-task grants, including a subject binding. A host operator must
reauthenticate subject permission and issue fresh grants after process restart.
The local capability authority is not an identity provider.

Episode bodies are protected-storage references, not document text. SQLite files
inherit host access controls and must never contain identifiable patient data in
these demonstrations. Event receipt order is monotonic; occurred_at preserves
late arrival without rewriting prior decisions. Schema v1 is additive. Forward
recovery rejects unknown schema versions. Disabling the code never drops tables
or receipts: opted-in tasks fail closed if the coordinator is absent.

Formatting and registered recovery-tool corrections require a separately issued
operator capability, task permission and current immutable evidence. Clinical
and factual corrections fail closed until domain-specific reviewer authority is
implemented. No observation or retrieved prose can become an instruction.
Corrections are task-local; training eligibility is separate and defaults false.
Task reset removes reusable corrections, never constraints, budgets or receipts.
A checkpoint cannot rewind execution history. Unknown effects require ARC's
operator reconciliation. No automatic retry of a side-effecting action exists.
The kill switch is durable and pauses open tasks with constraints intact.

Context size uses conservative UTF-8 byte accounting. Mandatory information that
does not fit stops planning; it is never silently summarized away. Older events
remain in the scoped ledger. Ordinary metrics contain mode/backend/category,
without subject/task identifiers or payloads.

Provider requests under adaptation are denied: zero USD is a hard budget, not
unlimited. Optional learned weights never enter production initialization.
Promotion remains in GovernedLearning/ArcOperations; adaptation cannot promote
itself or weaken approval. Existing ARC work at the starting checkout is an
uncommitted prerequisite, preserved by this change.

# ADR: fast memory research contract (before implementation)

Use a small NumPy external linear associative memory, float64 W of shape [8,8].
Keys and queries are normalized eight-dimensional vectors; values are one-hot
evidence-class vectors of shape [8]. Read q @ W before observing the current
label. A subsequent authorized, verified observation writes with the analytic
MSE gradient 2 outer(k, k @ W - v)/8. Bound the update Frobenius norm to 1 and
weight norm to 8; reject nonfinite inputs/state. No optimizer momentum. W0 is an
immutable approved initialization, copied per episode, and versioned checkpoints
are JSON with a digest (integrity check, not authentication). Reset clones W0.

Slow trainable parameters are the key/query/value projection matrices, W0 and
positive learning rate. The one-hot encoder is fixed. NumPy implements analytic
reverse derivatives through bounded inner updates; finite-difference tests check
all parameter groups. Reverse gradients detach at each sequence segment while
numerical fast state carries across segments. W0 receives gradients through the
first segment only. Episode boundaries reset to W0. Unit tests check masking,
reset, finite gradients and forward sensitivity on the simpler scalar ablation.
Sequence action forcing is not applicable: there is no flow-matching action head.
No upstream implementation or weights are used. This is not RoboTTT reproduction.
