# What NERVE demonstrated in the continuation

NERVE now induces reusable, schema-guarded operational rules from observed
transitions, compares them with exact-state memory, and uses the selected model
for bounded planning. It also learns and executes a read-only repository workflow
through existing NERVE tools. **The full 20-loop plan remains unfinished.**

The continuation starts at `2d422018fce3f703d68415aae9f84998291e77a6` on
`codex/memento3-world-model-20261012`. The original working checkout remains
untouched. No push, merge, production activation or live-provider call occurred.

## Measured capability

Final cohort: **240 tasks**, 80 each of workflow prerequisites, bounded API retry,
and string data preparation. Final seed **9003** was declared before execution;
training uses seed 1729 and selection uses 3001. Final source claims were stored
before induction, and final tasks were generated after candidate freezing.

| Condition | Completed | Interpretation |
|---|---:|---|
| Premature direct-finish baseline | 0/240 | Intentionally weak control |
| Exact-state memory | 0/240 | Abstained on unseen parameters |
| Learned frame rules | **240/240** | Generalized the permitted operations to new inputs |
| Selected bounded population | 240/240 | **No extra gain** over the single frame model |
| Latest-family-only learning | 80/240 | Only data-preparation tasks remained supported |
| Capable scripted planner | **240/240** | Learned rules **did not outperform** this control |

Retaining the full training history supported 160 more cases than retaining only
the latest family. This is a controlled evidence-retention ablation, not a claim
about neural catastrophic forgetting. Population selection had zero added success
on this cohort. The frame model and capable script each used 720 simulated host
actions; the frame model additionally used **4,320 planning nodes**. It matched
the capable control's quality while doing more search.

The workflows required ordered prerequisites; retry tasks required a token refresh
before a bounded retry; data preparation required stripping, lowercasing and
exporting new strings. The proposer received recorded training transitions, not
the host simulator's implementation or final outcomes. The operation vocabulary
is supplied by trusted code; NERVE inferred guards and assignments within it.
This is constrained program induction, not unrestricted intelligence or an LLM
learning new weights.

All 240 selected-model result handoffs passed the existing Agent OS host judge.
Explicit denied-workflow and schema-drift probes abstained. Provider usage was
**0 calls, 0 tokens, 0 spend**. The observations are deterministic synthetic
measurements; there is no statistical, clinical or broad real-world claim.

## Actual repository tool use

A separate study trained on two NERVE Python files, then evaluated six different
source files. It used the existing `repository_pilot_v22.file_task`,
`repository_agents_v20.ast_inventory`, independent `token_inventory`, and
`AgentOSLearning.observe` interfaces.

The learned sequence was **inventory → verify → handoff**. It completed **6/6**
read-only repository tasks; premature handoff completed **0/6**. Each candidate
used three registered tool calls. Actual JSON inventories were created in the
external study directory, verified against the independent token reader, and
checked again before completion was reported. Source files were never executed
or modified. Source hash changes and derived-artifact tampering are tested.

This demonstrates learning a useful order for registered tools. It does not
show code repair, arbitrary tool invention or superiority to a hand-written
inventory/verification procedure. The sample is small and curated.

## Integration and boundaries

- The durable coordinator now creates exact and frame candidates, replays them,
  compares selection/regression results, records its objective and winner, and
  opens final evidence only after freezing. Candidate and population counts are
  bounded. Per-category conservative work reservations survive restart.
- Frame rules preserve untouched fields and require an exact scalar schema.
  Constant, copy, bounded integer addition, strip, lowercase and strip/lowercase
  operations are allowlisted. Unknown schemas, overlapping guards and unsupported
  mechanics produce unknown. No expression evaluation or arbitrary Python exists.
- Model artifacts pin trusted interpreter/evaluator source hashes, Python
  major/minor and evaluation policy. The registry rejects runtime drift. The
  registered planner denies runtime access to ineligible artifacts and clamps
  research planning to the pinned limits. Evaluator roles can exercise frozen
  candidates without granting deployment authority.
- Existing policies load with their original exact-model defaults. Configured
  artifact-size, planning and work budgets are enforced. Default behavior remains
  disabled; read-only studies are explicit local research commands.
- Code-only repair now requires referenced replay failures. An unchanged rulebook
  without such failures is retained rather than being labelled a code repair.

## Validation

**921 Python tests passed**, including **46 focused world-model tests**; all
**7 Node checkpoint tests passed**. A fresh staged-tree export ran the original
offline demo successfully. Its inconclusive outcome and simulated rollback remain
available; no prior negative result or gate was rewritten to manufacture a gain.

[continuation-evidence.json](continuation-evidence.json) contains exact commands,
exit codes, model identifiers, source hashes and external evidence paths. The
final synthetic cohort ran against the completed code. The repository measurement
preceded final manifest/policy checks; the final suites exercise those checks on
the same bounded six-file workflow. The earlier 48 research-script checks are
retained as earlier evidence, not claimed as rerun during this continuation.

## Run it

From the worktree, with Python 3.12 and `PYTHONPATH=src`:

```sh
python -m nerve_awim.world_model.cli study --directory /tmp/nerve-study-new --final-per-family 80 --final-seed 9010
python -m nerve_awim.world_model.cli repository-study --repository . --directory /tmp/nerve-repo-study-new
```

Use fresh directories. Reusing a generator seed produces the same tasks and must
not be called fresh independent evidence merely because storage changed. New
study seeds do not establish independence beyond the declared synthetic task
families. See [README.md](README.md) for recovery and configuration details.

## Remaining plan work

The experiments do not complete the original assignment. [backlog.json](backlog.json)
tracks the remaining typed provenance contracts, full rule lifecycle, isolated
sealed evaluator authority and cross-store semantic contamination controls,
multigeneration revision, complete live-provider cost reservations, precise
retention/deletion dependencies, stochastic sensor validation and governed
operational release integration. Arbitrary-code isolation is unavailable; the
restricted declarative backend is the supported path.

All study models remain `eligibility=false` and `deployment_authorized=false`.
That distinction is deliberate: a narrow research result cannot authorize
production, clinical or device actions.
