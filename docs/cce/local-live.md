# Frozen local handoff research

This generated public procedural task set tests instruction-cue transport and
rule-following on handoff facts. It is not the paper benchmark, a representative
production benchmark, or evidence of general reasoning improvement. No private
tasks or records were used. A live model run would produce measured provider
receipts; generated questions do not justify marking those receipts synthetic.
No model has been executed as part of creating this artifact.

The frozen [dataset](local-handoff-dataset.json) contains one discovery task, four
selection tasks, four retained-capability regression tasks and 30 untouched
holdout tasks. One discovery plus both arms for every evaluated task requires
77 model calls. The evaluation adapter needs a 76-call cap; an 80-call local daily
allowance would leave three calls spare. This arithmetic does not configure or
raise any allowance, and never changes the native Hermes 20-call daily cap.

Each instruction is exactly compact sorted-key JSON with id, exit_code,
artifact_exists, qa_passed and memory_written. The trusted provider adapter
supplies the explicit handoff rule separately and validates these facts before
dispatch; a dataset task cannot supply prompt prose. Null means missing evidence. Explicit failure takes precedence over
unknown; memory_saved is true only for an observed true memory_written. Expected
answers are compact, sorted-key JSON results from the existing expected_handoff
function: {status, passed, memory_saved}. They remain host-side for grading and
must not be appended to provider requests or discovery input.

Families hash all four logical facts, excluding task IDs and split labels. The
loader verifies unique instructions/IDs and disjoint families. This prevents the
same complete logical pattern crossing partitions; it does not establish semantic
independence. Tasks share one rule, patterns can share completion status, and
changing memory_written can leave the core completion decision unchanged.
Selection deliberately includes missing-evidence cases; regression uses four
straightforward cases. These choices precede all model results. Never alter the
partition or retry a consumed holdout to chase a passing result.

## Source and deterministic generation

Source URI: `fixture:nerve-handoff-facts-v1`. The frozen source revision is SHA256
of compact sorted-key JSON for the protocol below. Its rule hash covers the exact
UTF-8 Python function source returned by inspect.getsource(expected_handoff).
The source checkout was a51cfa8e1a314e2129ac672755d13230e517c25f; the rule's named
revision is handoff-judge-v1. This is explicit local fixture provenance, not an
authenticated external dataset or an arXiv reproduction.

```json
{
  "name": "nerve-handoff-facts-v1",
  "facts_keys": [
    "exit_code",
    "artifact_exists",
    "qa_passed",
    "memory_written"
  ],
  "domains": [
    [
      0,
      1,
      null
    ],
    [
      true,
      false,
      null
    ],
    [
      true,
      false,
      null
    ],
    [
      true,
      false,
      null
    ]
  ],
  "fixed_partitions": {
    "discovery": [
      {
        "exit_code": 0,
        "artifact_exists": true,
        "qa_passed": true,
        "memory_written": null
      }
    ],
    "selection": [
      {
        "exit_code": null,
        "artifact_exists": true,
        "qa_passed": true,
        "memory_written": null
      },
      {
        "exit_code": 0,
        "artifact_exists": null,
        "qa_passed": true,
        "memory_written": false
      },
      {
        "exit_code": null,
        "artifact_exists": false,
        "qa_passed": null,
        "memory_written": true
      },
      {
        "exit_code": 1,
        "artifact_exists": null,
        "qa_passed": null,
        "memory_written": null
      }
    ],
    "regression": [
      {
        "exit_code": 0,
        "artifact_exists": true,
        "qa_passed": true,
        "memory_written": true
      },
      {
        "exit_code": 1,
        "artifact_exists": true,
        "qa_passed": true,
        "memory_written": false
      },
      {
        "exit_code": 0,
        "artifact_exists": false,
        "qa_passed": true,
        "memory_written": true
      },
      {
        "exit_code": 0,
        "artifact_exists": true,
        "qa_passed": false,
        "memory_written": false
      }
    ]
  },
  "holdout": "first 30 unused patterns sorted ascending by SHA256 of compact sorted-key JSON facts",
  "rule_revision": "handoff-judge-v1",
  "rule_sha256": "1a78f72e4926efb054cff135201b49a6d995f8aee0d79a3667bdfe6a3f660f36",
  "instruction_encoding": "compact sorted-key JSON of id=task_id and all four facts; no prose; trusted provider prompt supplies handoff rule"
}
```

Source revision: `sha256:f6dc5d80d9d3784b0bd091e32fbf59914dac10358b17fd06bb4484e35b630d0b`.

Validated canonical dataset digest: `cd7ede2f94341a4b8a8fe8d1b5dde235273a10ab9871cc47f1da7fedd98a1f57`.

The generator enumerates the 81 Cartesian fact patterns, excludes the nine fixed
discovery/selection/regression patterns, sorts the remainder by the fact hash,
and takes the first 30 for holdout. Each instruction is compact sorted-key JSON of the task ID and four facts,
without prose. The JSON artifact is authoritative for exact prompt bytes.

## Interpretation and release boundary

Strict independent host grading can assess these procedural outputs, but format
correctness is not a general safety evaluation and confidence must come from a
validated measurement contract. Grader correctness must never be substituted for
answer confidence. Local fees, compute costs, missing receipts and truncations
remain explicit. Regression and holdout results are evaluated once under the
existing governed gates. No candidate is approved or routed merely because this
file exists or because an experiment completes.

A result from this small rule family supports only a narrow local task claim.
There is no independence, causal generalization, production efficacy or clinical
safety claim. No live execution result is recorded in this document yet.

## Two-study frozen programme

A [second frozen dataset](local-handoff-dataset-02.json) was prepared before any
live outputs. It reuses the same discovery, selection and regression partitions
only within their original roles. Its 30 holdout patterns are the next 30 unused
patterns (zero-based offsets 30–59) under the original deterministic hash order.
Both directions were checked: neither dataset's holdout IDs, instruction hashes
or complete-fact families appear in any partition of the other dataset.

This is a finite two-study programme, not endless self-training. Together the
studies reserve 60 distinct logical-pattern holdouts from the 81-pattern domain.
Each complete study needs 77 calls, so an 80-call daily allowance cannot fund both
on one day; the existing durable budget may defer the second study. Neither a
failed first study nor a promising result changes the second frozen task set.
There is no causal generalization or production-benefit claim. Do not select only
the favorable study for reporting, reset reservations, or recycle these holdouts.

Second dataset source URI: `fixture:nerve-handoff-facts-v1-study-02`.

Second source revision: `sha256:5429da0920dbde4353c750dce97711aea1a48145e4021845eaa807f818337f85`.

Second canonical dataset digest: `70ec6849fc52dc557b893f274e4cf31d8c2e2700f12ad681f5dd17f948bbdfab`.

The second source revision hashes compact sorted-key JSON of this protocol:

```json
{
  "name": "nerve-handoff-facts-v1-study-02",
  "parent_source_revision": "sha256:f6dc5d80d9d3784b0bd091e32fbf59914dac10358b17fd06bb4484e35b630d0b",
  "holdout": "patterns at zero-based offsets 30 through 59 in same unused-pattern SHA256 ordering as study 01",
  "fixed_partitions": "discovery, selection and regression copied unchanged from study 01",
  "instruction_encoding": "compact sorted-key JSON id and four facts",
  "expected_rule": "handoff-judge-v1"
}
```

## Local response measurement contract

The scheduled local adapter uses the separately pinned `handoff-confidence-v1`
contract. The model returns status, passed, memory_saved and its own numeric
probability that the whole answer is correct. The adapter extracts that reported
probability; it is not a calibrated probability or a host-generated certainty.
Invalid, missing or truncated contract outputs fail rather than receiving an
invented confidence score. The host independently recomputes the expected answer
from canonical input facts and binds the grader to the just-observed output.

Local calls use a separate durable maximum of 80 attempts per UTC day, with a
77-call maximum per job and a 600-second job budget. Failures consume reservations.
No paid API is selected and native Hermes limits remain unchanged; local compute
cost is unknown. Both local research and the exact CCE host profile must be
explicitly enabled. Completing research still cannot approve or deploy a cue.
