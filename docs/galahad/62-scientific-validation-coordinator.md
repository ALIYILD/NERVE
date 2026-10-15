# Scientific interface validation coordinator

This cycle connects a completed scientific interface development experiment to
one fixed validation experiment and an explicit review decision. The preceding
cycle made concrete progress by implementing and exercising the paired interface
workflow; it did not establish the overall self-improvement objective. This
coordinator adds bounded follow-up execution and receipt-based restart behavior.
Reliable general self-learning and self-adaptation remain unproven.

## Fixed graph and existing components

`scientific_research_coordinator.run` executes three registered nodes:

1. Adopt the completed development experiment using its stored report, digest,
   source pins, approved evidence and external consumed-work journal.
2. Run the fresh fixed validation experiment once, with independent pre-call claims
   and a separate journal.
3. Retain the baseline or produce `candidate_requires_independent_review` from the
   frozen validation screen.

There is no arbitrary executor, generated-code dispatch or automatic promotion.
The implementation reuses the gateway and original bounded local inference
adapter, the registered trusted-task interface, file locking, and atomic fsynced
report publication. Existing experiment modules remain unchanged and retain their
source identities.

The coordinator records its source, predecessor, paths and budget in a durable
SQLite claim before dispatching validation. All six supplied coordinator,
development and validation paths must be distinct; journals are outside the
experiment directories. Changing the configuration cannot authorize another run
under an existing claim.

## Fresh validation tasks and unchanged treatment

The new registry has eight tasks, each with two approved records:

- Two measurement-decoy tasks, requesting mass or volume.
- Two entity-decoy tasks, requesting mass or volume.
- Two exact-unit mismatch tasks requiring abstention.
- Two conflicting-value tasks requiring abstention.

There are four supported tasks and four abstention tasks. Supported evidence is
first in two tasks and second in two. All sample names, measurement values and
source identifiers differ from both preceding task registries.

Each task is paired across `baseline_json` and `trusted_task`, totaling sixteen
real completions. The direct instruction, output grammar and scoring semantics
are unchanged. The baseline carries the instruction and question in the original
user JSON interface. The candidate places only the host-registered instruction
and question in the trusted system task interface. Evidence remains untrusted
user data. Both arms receive the same approved evidence and task capabilities;
answer keys and stratum labels are not model inputs.

This is a fresh fixed validation set. It is not model-weight training, online
feedback learning, a clinical evaluation or a guarantee of out-of-distribution
generalization. Neither prompt is revised in response to validation outputs.

## Exact screen and limits

Raw answers must match the frozen tuple contract or `ABSTAIN`, with only outer
whitespace removed. The evaluator never repairs answers or citations. It records
`strict_correct`, `format_failure` and `non_abstaining_contract_failure`; the last
metric is a contract failure, not a semantic unsupportedness judgment.

The candidate passes only if it:

- Is strictly more accurate overall than the baseline.
- Gets all four supported tasks and all four abstention tasks correct.
- Does not regress on either supported/abstention grouping or any of the four
  semantic strata.

A tie, incomplete run or failure of any screen condition cannot promote the
candidate. Even a pass only requests independent review. The always-abstain
reference scores four of eight tasks without extra model calls; it is not a
separately executed model arm.

The validation protocol permits at most sixteen inference calls, one preload and
two metadata checks. Each completion has a 128-token cap and a 90-second socket
timeout, using the CPU research profile and temperature zero. A socket timeout is
not a hard total experiment deadline. Model digest and source hashes are checked;
outputs require review. Raw outputs, measured usage and per-attempt evidence are
retained without inventing successful responses after a transport failure.

## Restart and consumption behavior

A first invocation may dispatch the one registered validation experiment. A
resumed coordinator may only adopt an already complete validation receipt through
`validate_receipt`; it cannot initiate missing or incomplete model work again.
Failed or interrupted consumed experiments remain consumed.

Completed coordinator output is checked against recomputed receipt evidence and
its stored digest. A missing completed output or changed output fails closed.
An interrupted coordinator claim can finish publishing its report only when the
child experiment already has complete validated evidence. This reconciliation
can perform local verification work; it does not issue new model calls. Ledger
initialization can write local authority/schema state, so adoption is not described
as entirely read-only database access.

No feedback utility updates occur in this experiment. A validation result does
not grant deployment, source-code rewriting or clinical authority.

## Verification and execution evidence

The full regression passed **1,809 tests in 161.359 seconds**, including all
34 new task, runner and coordinator tests. Independent review passed before
execution. A separate post-run review recomputed all sixteen scores and verified
source/model identities, scoped evidence, consumed claims and the rejection.
The actual coordinator completed on 14 October 2026 and selected
**retain_baseline**, with no promotion.

| Interface | Exact correct | Supported correct | Correct abstentions | Format failures |
|---|---:|---:|---:|---:|
| Baseline JSON | 4/8 | 0/4 | 4/4 | 1/8 |
| Trusted task | 2/8 | 0/4 | 2/4 | 2/8 |
| Always abstain reference | 4/8 | 0/4 | 4/4 | 0/8 |

The candidate selected `Poplar|mass|20.1|mg|validation-m` and
`Alder|volume|23.8|mL|validation-p` despite conflicting approved values. These are
failed conflict-handling cases, not merely formatting errors. The baseline
abstained correctly on both. The candidate also returned `Sample Spruce|volume|mL|6.4|validation-d`
and `Sample Aspen|volume|14.8|mL|validation-g`, which fail the exact contract.
The baseline's supported Spruce answer was prose containing the correct value and
source; its formatting failure is not described as factual falsity. No outputs
were repaired and no scores were changed after observing results.

The earlier development gain did not replicate: the candidate regressed on fresh
conflict cases. The automatic screen rejected it. This is evidence that the
coordinator can block a worse candidate, not evidence of a better language model.
Both interfaces still fail reliable supported extraction under the strict contract.

All sixteen calls completed with the same model digest before and after the run.
All 26 validation source hashes and 29 coordinator source hashes matched. The
local model was `qwen2.5-coder:1.5b` at digest
`d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668`, running
with Python 3.10.0 on macOS x86-64 using the CPU research profile. Inference
sections totalled 881.723 seconds, median 57.654, range 35.756–70.080 seconds.
Usage totalled 7,805 prompt and 122 completion tokens; preload took 3.287 seconds.
Prompt lengths differ, so these are descriptive timings, not a matched-token
speedup claim. GPU energy, financial cost and persistent KV reuse were not measured.

An actual fresh Python process resumed the full graph with metadata, preload and
model inference patched to fail if called. It returned the identical coordinator
report, preserved its bytes and modification time, and left both experiments'
reports and attempt claims plus all three journals unchanged. There were zero
network/inference calls. This validates historical evidence; it does not certify
current model health. The local journals are not independently sealed custody.

Artifacts:

- [Coordinator report](evidence/scientific-research-v1.json), SHA256
  `09d9144cb2ae393b20d46603ae746814dad74badaa0b6afd4cf6eda553b5cfda`.
- [Full validation outputs](evidence/scientific-interface-validation-v1.json), SHA256
  `140e627c72b89265fb200e0fa9fc59f2070a80d7c826b1187f9e45f898799925`.
- [Summary](evidence/scientific-research-summary.json).
- [Fresh-process resume](evidence/scientific-research-resume.json).
- [Test evidence](evidence/scientific-research-tests.json).

Live records and journals are under `/Users/aliyildirim/nerve-research-runs/` at
the exact paths in the reproduction command. The full regression log is
`/private/tmp/nerve-scientific-validation-tests.log`. No feedback utility or model
weights were updated. No source-pinned historical module was modified.

The next candidate must address conflict handling as well as output formatting.
Changing output syntax alone cannot be assumed to correct the observed conflict
regression. A new hypothesis requires a separately registered experiment and
fresh evaluation; the consumed validation set cannot become fresh evidence again.
The broader self-learning/scientific-discovery objective remains incomplete.

## Reproduction

From the repository root, after preserving the existing development artifacts:

```sh
PYTHONPATH=src .venv/bin/python scripts/run_scientific_research.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-research-v1 \
  --journal /Users/aliyildirim/nerve-research-runs/scientific-research-claims.sqlite \
  --development-directory /Users/aliyildirim/nerve-research-runs/scientific-interface-v1 \
  --development-journal /Users/aliyildirim/nerve-research-runs/scientific-interface-claims.sqlite \
  --validation-directory /Users/aliyildirim/nerve-research-runs/scientific-interface-validation-v1 \
  --validation-journal /Users/aliyildirim/nerve-research-runs/scientific-interface-validation-claims.sqlite \
  --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
```

Supply the original completed development directory and shared journal, and the
full verified model digest. Reuse exactly the same arguments for receipt-based
resume after completion. Do not create replacement journals to repeat consumed
work. Full regression is separate:

```sh
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

## Follow-up hypothesis, not executed in this study

Ollama documents JSON-schema structured output and OpenAI-compatible
`response_format` support in its [official structured-output guide](https://docs.ollama.com/capabilities/structured-outputs)
and [compatibility reference](https://docs.ollama.com/api/openai-compatibility),
accessed 14 October 2026. This is documentation evidence, not verification of the
installed server's implementation or correctness.

A future registered experiment could compare schema-constrained generation with
unconstrained generation using the same JSON task contract, fresh evidence and
separate format/correctness metrics. A schema must constrain structure only,
without encoding task answer keys, source choices or expected values. Raw model
answers still require independent grounding checks; syntactically valid JSON is
not evidence of a correct scientific answer. No such experiment or repair is
applied to the consumed validation tasks here.

## Changed implementation and release boundaries

New code consists of `scientific_interface_validation_tasks.py`,
`scientific_interface_validation.py` and `scientific_research_coordinator.py`
under `src/nerve_awim/memory_gateway/`, with two runnable CLIs and three
corresponding test modules. The verification script registers all new tests;
README and the final report point to this evidence. The finite graph is opt-in,
locally executed and restart-tested. Fault tests use mock transport, while the
sixteen reported completions used the actual local model.

This branch has not been deployed or merged, and no PR or remote push was made.
Real Galahad GPU restoration and commercial licensing remain unverified. Clinical
integration remains synthetic-only. No clinical decision authority or general
autonomous scientific discovery is established.
