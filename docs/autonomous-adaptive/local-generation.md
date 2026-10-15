# Executable local generation handoff

This increment connects approved generation notes to the existing pinned Ollama
adapter. It is a development workflow, not operational cue activation, a new
scheduler or a reproduction of Anthropic's inference-setup experiment.

```sh
python3 scripts/agentos_bridge.py runtime-inventory
python3 scripts/agentos_bridge.py generation-local-scope --profile local-handoff-research
python3 scripts/agentos_bridge.py generation-local-run --profile local-handoff-research --task request.json --allow-local-inference
```

`generation-local-scope` returns the exact current scope for note proposals. It
binds installed model artifacts, rendering/sampling/executor identity, generation
and memory authority implementation, and the independent handoff grader source.
Use this scope through the existing generation-note review/freeze workflow.
`request.json` contains exactly `snapshot_id` and `task`; task uses the existing
host evidence schema (`id`, `exit_code`, `artifact_exists`, `qa_passed`,
`memory_written`). Supplied task values are host observations, not untrusted
claims from a model. No expected answer is inserted into the model request.

The command requires explicit local inference permission and enabled pinned
local configuration. It revalidates all inherited notes, approval/revocation,
scope, model identity and context budget before reserving a call. One fresh
adapter makes at most one generation using the shared 80-call UTC-day ledger.
There is no retry/refund. The 120-second socket timeout is not a whole-operation
or system-wide cancellation deadline. The existing host lock serialises dispatch.

Immutable `generation_local_attempts` and `generation_local_receipts` tables in
the existing learning database retain snapshot lineage, task digest, independent
correctness, output-schema check, measured usage and failures. A process death
may leave an attempt without a terminal receipt; that is not success and must
not trigger automatic replay. Default receipts exclude task, output and note text.
Model-reported confidence remains uncalibrated. A valid schema is not a general
safety verdict. This command cannot approve a candidate or change deployment.

## Observed protocol diagnostic

On 13 October, one fresh `qwen2.5-coder:1.5b` local call used one approved note
and an already exposed synthetic handoff pattern. Independent grading found
the answer correct and structurally valid. The call measured 323 input tokens,
32 output tokens and 57.588 seconds. External API fees were zero; local compute
cost is not measured. See [the receipt](local-generation-protocol-20261013.json).

The note was a host-reviewed existing rule, not a model-discovered improvement.
This is a successful inheritance/dispatch check with no held-out or causal gain
claim. No new clinical permission, operational cue or model weight change occurred.

## Runtime observation

The inventory observed this one configured model on Darwin/x86_64 with 16
logical CPUs and 16 GiB physical memory. It performs metadata inspection only;
it does not start/install models or scan hosts. Allocatable memory, GPU ability,
matched quality, throughput and comparative cost remain unknown. No automatic
selection benefit can be claimed from a single observed runtime.

## Reviewed workspace artifacts

`GenerationWorkspace` uses the same ledger authority. A host with existing
approval rights captures a manifest containing review ID and exact hashes for
at most eight public/synthetic UTF-8 text files (64 KiB each, 256 KiB total).
Only `.txt`, `.md`, `.json` and `.csv` are admitted. Links, traversal, sensitive
paths and detected secrets are denied. Classification still needs host review;
pattern screening is not a comprehensive data-loss prevention system.

Capture stores immutable file content bound to an approved generation snapshot.
Restore revalidates generation and artifact revocation, stages private directories
and read-only nonexecutable files, then publishes a new directory with atomic
no-overwrite rename. It runs no captured content. CLI restore is:

```sh
python3 scripts/agentos_bridge.py generation-workspace-restore --profile PROFILE --task restore.json
```

The exact fields are `scope`, `artifact_id`, `destination_parent` and
`directory_name`. Roots must be absolute and have no linked path components
(use canonical `/private/...` paths on macOS). CLI callers cannot approve or
capture artifacts; privileged capture uses the existing host API with an
independently reviewed manifest. Revocation denies future restores but cannot
retract files already delivered. Hostile same-user processes and privileged
database writers remain outside this local boundary.

Automatic generational orchestration, independently measured retained gains,
hardware-driven selection and distributed deployment remain incomplete.
