# Automatic outcome-feedback execution

This continuation closes the manual host `observe()` step for NERVE's existing synthetic registered-tool agent. `AutomaticLearningRun` selects approved evidence through a host-bound adaptive session, executes the existing `DemoAgentBridge`, independently evaluates the actual output through `VerifiedOutcomeLearning`, and automatically writes the resulting utility observation. Later episodes use the updated preference.

It reuses the verified gateway, existing memory ranker, authority checks and registered tools. It does not create a second candidate/release authority: `governed_learning_v20.py` still owns frozen candidates, independent holdout, operator activation and rollback. There is no automatic production promotion, arbitrary code executor, new clinical authority or weight-training operation.

## Execution and stopping rules

The trusted host supplies the evaluator and tasks. Agents cannot provide their own rewards or answer keys. Only one approved, intact, eligible strategy is permitted in strict execution. Missing/malformed/conflicting evidence and ranking outages cannot trigger the legacy agent fallback in this mode. Ordinary agent callers retain their existing behaviour because strict mode defaults off.

Claims are stored before execution in SQLite. They bind the tenant/agent/run to frozen context, evaluator revision/window, agent database identity and budgets. Reopening cannot change those settings or reset consumption. Episode IDs and document fingerprints are unique across runs for a tenant/agent. A pending claim after a crash blocks continuation pending host investigation; it is never silently rerun. Raw task, document and output values are not stored by the runner. New run IDs do not permit reusing already claimed episodes/documents.

Execution stops at the episode budget or consecutive-failure limit. Each call executes at most one fixed two-step registered pipeline. The host's evaluator remains trusted in-process code and must itself be bounded; this is not an OS sandbox or hard wall-clock deadline for arbitrary callbacks. No background daemon or indefinite loop is started.

Durable claims intentionally retain identifiers and unsalted document hashes even after deleting source utility. These hashes are pseudonymous and may be guessed for low-entropy inputs; they are not anonymisation or complete erasure. They are local research audit/replay metadata, not encrypted storage or a production retention policy. Starting a genuinely new host-authorised run with different fresh tasks is possible. SQL admission caps limit each tenant/agent to128 run records and10,000 claimed episodes, including failed and no-evidence cases; reaching either cap requires host investigation rather than automatic deletion/reset. This is a bounded synthetic research store, not an indefinitely running scheduler or a global infrastructure compute quota. Access is rechecked around execution and feedback, and revoked scopes cannot continue.

## Reproduction

```sh
cd /Users/aliyildirim/nerve-galahad
PYTHONPATH=src .venv/bin/python scripts/memory_autoadapt_demo.py
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_memory_auto*.py' -v
.venv/bin/python scripts/verify_galahad.py baseline
```

The demo runs16 distinct synthetic episodes. The first eight require trimming; the next eight preserve spaces. It reopens the runtime between phases. The host never selects a strategy or separately calls `observe`. Actual registered tools produce outputs, the frozen evaluator judges them, and the ranker switches preferences after changed outcomes. Both phases must finish with the correct strategy. Errors during adaptation are counted, not hidden. This is a constructed deterministic drift fixture, not evidence of general model intelligence or clinical effectiveness.

## Current limits

One evaluator per gateway and one synthetic agent tool family are supported. Automatic ingestion/approval of new knowledge, model-weight training, free-form agent skill creation, multi-context production wiring and clinical decisions are not implemented by this runner. The local Galahad GPU/licence/connector and encrypted operations blockers remain. Original external API/MCP feedback remains pending proposals; this trusted host runner adds no reward/approval endpoint.

The feedback call is also bound to the source snapshot used by the execution. If approved content changes before feedback starts, the old output cannot earn credit for the new source. Cross-context replay checks deliberately share the tenant/agent namespace; changing context does not let the same run/document be replayed.

Initial equal-utility ties follow the existing lexical record order, which may vary with generated record identifiers. Therefore individual demo runs can show different adaptation-error counts. The assertions require correct final strategy in both phases and preserved bounds; they do not hide initial errors or demand a fabricated speedup. The committed trace records the actual observed run.
