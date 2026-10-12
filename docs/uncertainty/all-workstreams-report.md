# Connected workstreams: implementation and evidence

The integration branch combines ARC, task adaptation, Memento frame learning,
persistent uncertainty, Galahad text memory and the Cognitive Cue Engine (CCE).
The Hermes runtime adapter participates in the connected research workflow.
Native AgentOS/Hermes request boundaries also carry host uncertainty and reject
responses when the supporting state changes in flight.

## Imported work

- Memento: `5b77b1d`, merged as `54053c2`.
- Galahad: `274e1d0`, merged as `cfb1f96`.
- CCE: `340040a`, merged as `84be85f`.
- Latest adaptation changes: hash-checked source snapshot, recorded in
  [all-workstreams-import.json](all-workstreams-import.json). Existing integration
  uncertainty guards and scoped SQL improvements were retained during import.
- ARC and uncertainty were already present in the integration worktree.

The source windows were left untouched. These are pinned imports, not a claim
that future edits in those windows automatically synchronize.

## What the connected run demonstrates

`nerve_awim.integrated_learning` uses one fresh SQLite store and authenticated
scopes throughout. It parses three actual repository files without executing or
modifying their source.

1. A regex inventory fails independent verification. A host-reviewed AST
   correction succeeds, and the next file reuses that persisted correction.
2. Two independently verified ARC receipts become world-model observations.
   Predictions are reserved before the tool effects, with timestamps checked
   against the actual ARC outcome records in tests.
3. Symbolic inference produces a declarative frame rule. A frozen research model
   plans an AST inventory for a third file. It is not runtime eligible.
4. A host-approved learning summary is retrieved through Galahad's text gateway
   and passed with mandatory uncertainty metadata into the Hermes runtime adapter.
5. Thirty explicitly synthetic cue pairs show no accuracy gain. Promotion is
   rejected and the research record remains pending memory.
6. A planted contradictory audit claim invalidates the dependent plan, queued
   ARC action and cue guidance. The conflict survives memory retrieval, agent
   handoff and restart. An independently supported task still executes and
   verifies successfully.

The connected run reports `offline_verified`, two verified training receipts,
one learned frame rule, correction reuse, two scripted Hermes responses, zero
native provider calls and zero provider spend. This is evidence of bounded
learning and adaptation plumbing, not a comparative capability benchmark.

The merged-source frame-learning smoke study completed **6/6 synthetic final
tasks**, versus **0/6** for exact-state memory and **6/6** for a capable scripted
control. It demonstrates generalization within those deterministic families,
with **zero gain over the capable control**. The repository study completed
**6/6 curated read-only workflows**, versus **0/6** for its limited direct-finish
baseline. These small, repeated smoke studies do not establish a new independent
held-out improvement claim. Both keep eligibility and deployment authorization
false.

## Boundary repairs

- Memento's newer registered-planner path now checks persistent uncertainty.
  Frozen models are restricted to explicit evaluator research; runtime requires
  eligibility. Evaluation checks uncertainty before consuming final data.
- Galahad preserves authoritative uncertainty in typed responses, bounded text
  context and HTTP responses. Omitting an adapter after persisted opt-in fails.
- CCE binds immutable task dependencies to its scope, rechecks them before
  selection and promotion, and exports source-linked pending memory. An opted-in
  failure cannot silently fall back to an uncued call.
- Native Hermes requests preserve the strict CCE worker contract. The host adds
  the uncertainty companion to the prompt, checks it before and after the worker,
  and supplies authoritative response metadata. Mocked tests cover an in-flight
  conflict and restart omission without spending provider credits.

## Reproduction

Validation on the merged source: **1,345 Python tests passed, no skips**, in
258.632 seconds; **7 Node checkpoint-discovery tests passed**. Both the package
CLI and AgentOS bridge command produced `offline_verified` in separate fresh
stores. Full logs are under `/private/tmp/nerve-all-workstreams-evidence/`.
Committed [combined receipts](all-workstreams-evidence/combined-report.json),
[bridge receipts](all-workstreams-evidence/bridge-report.json) and the
[source manifest](all-workstreams-evidence/source-manifest.json) preserve the
tested inputs and receipt identifiers. The SQLite files remain in that local
evidence directory.

All **62 commands** selected from the merged research and Galahad workflows
passed, including multiline frame/repository studies and folded memory-research
commands. [Command results](all-workstreams-evidence/ci-results.json) record
actual arguments, durations and log names. This includes the 7 Node tests and
some repeated focused Python suites; it is not 62 independent improvement
experiments. [Resumable status](all-workstreams-progress.json) records blockers.

From the repository root, with Python 3.12 and the project's optional test
dependencies available:

```bash
python -m pip install 'numpy==2.2.6' 'PyJWT[crypto]>=2.10,<3' 'mcp==2.3.0'
PYTHONPATH=src python -m unittest discover -s tests -v
node --test tests/test_checkpoint_discovery.cjs
PYTHONPATH=src python -m nerve_awim integrated-learning \
  --repository . --directory /tmp/nerve-integrated-new-run
PYTHONPATH=src python scripts/agentos_bridge.py integrated-study \
  --repository . --output /tmp/nerve-integrated-bridge-new-run
```

Each demonstration requires a new output directory and refuses to overwrite
earlier evidence. It writes `report.json` and `integrated.sqlite3`; the report
includes source and implementation hashes plus receipt IDs. The merged CI
workflow also executes the connected command.

## Limits and remaining work

- No learned rule or cue has earned production promotion from this combined run.
  A fresh, matched baseline study on unseen tasks is required to establish gain.
- Hermes responses and cue comparisons in this run are fixtures. The native
  bridge is tested with mocked subprocesses; this is not a live-provider result.
- Galahad supplies verified text prefill. GPU/KV runtime and its deployment
  prerequisites remain unverified.
- No LLM weights were updated, no continuous unattended service was started,
  and no dashboard/production deployment was activated.
- Existing JEV, GBrain and Obsidian integrations were not exercised live in this
  run. Their presence does not establish an additional learning benefit.
- The larger Memento implementation plan and prior component benchmark blockers
  remain tracked in their respective reports. Earlier benchmark results do not
  automatically become results for this merged source.
