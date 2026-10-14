# Scientific task interface development comparison

This experiment compares two system interfaces for a fixed host task in the local model request.
It uses four fresh synthetic measurement tasks and two interface arms, for eight
real completions. It does not tune prompts from observed outputs, train model
weights, promote a strategy or establish general scientific reasoning capability.

## Fixed task contract

The task registry contains four strata: a different measurement for the same
entity, a measurement for a different entity, a requested unit absent from the
evidence, and conflicting values for the requested measurement. Each task has two
approved evidence records. Names, numerical values and source identifiers differ
from the preceding measurement experiment. These are fresh development examples,
not a sealed independent holdout or an unbiased confirmation after prior prompt
engineering.

A supported answer must be exactly `entity|measurement|value|unit|source_id`.
Otherwise the answer must be `ABSTAIN`. Unit conversion is prohibited; unresolved
conflicts require abstention. The evaluator strips outer whitespace only. It does
not repair formatting, add citations, extract an answer from prose or replace the
model's response with a deterministic answer.

The recorded metrics are `strict_correct`, `format_failure` and
`non_abstaining_contract_failure`. The last metric can overlap formatting failure:
a response containing a correct fact in the wrong format still fails the exact
contract. It is not a classification of semantic unsupportedness.

## Paired interfaces

`baseline_json` uses the previous direct strategy through the original inference
interface: the fixed instruction and question appear in the user JSON task field,
under the existing system instruction that treats user JSON and evidence as
untrusted data.

`trusted_task` places the same registered direct instruction and question in the
host-controlled system task interface. Only a whitelisted task identifier can
select this instruction. Caller-provided prose, evidence content and answer keys
cannot become system instructions. Evidence remains untrusted data in the user
payload.

Both arms receive the same approved records and task capabilities. They use the
same model, temperature, output limit and exact evaluator. The treatment changes
task placement and priority and replaces the generic concise-prose system wording
with the exact output contract. It is a bundled interface comparison and cannot
isolate instruction placement as the cause of any difference. It provides no additional facts,
worked answers, tools or retries. Answer keys remain in the host evaluator and are
excluded from model prompts. Two non-answerable tasks still provide approved
records, ensuring that abstention is measured from an actual completion rather
than an empty-retrieval shortcut.

The bounded runner records attempted calls before dispatch, checks source and
model identity, and retains failed attempts. The shared journal prevents a changed
run directory from authorizing repetition of consumed work. There are no
outcome-dependent prompt revisions or utility updates in this experiment.

## Interpretation boundaries

The result can describe differences between these interfaces on four paired
synthetic tasks. It cannot establish a general causal improvement across models,
scientific domains or future tasks. Eight calls are not eight independent tasks.
The candidate has a longer system prompt, so timings are descriptive rather than
a matched-token efficiency claim. Formatting accuracy, evidence binding and abstention are distinct from discovery,
clinical validity or model-weight learning.

All records and identities are synthetic. Existing gateway scope checks and
post-inference evidence revalidation remain authoritative. No clinical deployment,
persistent GPU KV restoration or production authentication is demonstrated here.

## Execution evidence

All eight actual calls completed on 14 October 2026. Model identity matched the
operator-pinned digest before and after execution, and all 23 source hashes remained
unchanged. Full regression passed **1,775 tests in 146.970 seconds**, including 28
new tests. Independent code review passed before execution. A separate read-only review
subsequently verified the actual raw scores, scoped evidence, all source pins,
claims and absence of utility feedback.

| Interface | Exact correct | Supported answers | Correct abstentions | Format failures |
|---|---:|---:|---:|---:|
| Baseline JSON | 2/4 | 0/2 | 2/2 | 0/4 |
| Trusted task | 3/4 | 1/2 | 2/2 | 1/4 |
| Always abstain control | 2/4 | 0/2 | 2/2 | 0/4 |

The candidate returned `Maple|volume|3.8|mL|interface-d` correctly. Its other
supported answer was `Sample Linden|mass|18.7|mg|interface-a`, which fails the
registered entity format. That failure is retained without answer repair. Both
interfaces abstained correctly on unit mismatch and conflicting evidence. The
baseline abstained on every case. The result supports further development of the
interface; it does not establish reliable extraction or authorize promotion.

Measured inference sections totalled 412.775 seconds, median 53.772, range
32.443–63.081 seconds. Usage was 3,837 prompt and 53 completion tokens. One preload
took 0.452 seconds. These are local macOS x86-64 CPU-profile measurements with
Python 3.10.0 and `qwen2.5-coder:1.5b`; they are not GPU, energy, cost or KV-reuse
measurements. Socket timeout is 90 seconds, not a hard total-process deadline.

An actual separate Python process resumed the completed study with metadata,
preload and model dispatch patched to fail if called. It returned the identical
report, left all eight attempt claims and the one shared journal claim unchanged,
and made zero inference calls. This verifies the historical receipt, not current
model health. The journal is operator-local, not independently sealed custody.

Artifacts:

- [Full raw report](evidence/scientific-interface-v1.json), SHA256
  `e261fd2f78e07f2afa69e6bfaa798036a92bb4014c21547faa0874316c3fc3f8`.
- [Summary](evidence/scientific-interface-summary.json).
- [Fresh-process resume](evidence/scientific-interface-resume.json).
- [Validation](evidence/scientific-interface-validation.json).
- Live database: `/Users/aliyildirim/nerve-research-runs/scientific-interface-v1/memory.sqlite`.
- Shared journal: `/Users/aliyildirim/nerve-research-runs/scientific-interface-claims.sqlite`.
- Full regression log: `/private/tmp/nerve-scientific-interface-tests.log`.

No feedback utilities were updated in this comparison. Existing scientific strategy
learning remains separately available. A useful next registered experiment would
clarify the entity-field contract and test fresh cases, including unseen formatting
and conflicting-source cases. This is a proposed next hypothesis, not a validated
change or permission to retune the consumed dataset.

## Reproduction

From the repository root, run the task-contract tests:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_scientific_*interface*.py' -v
```

The runner interface is:

```sh
PYTHONPATH=src .venv/bin/python scripts/run_scientific_interface_study.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-interface-v1 \
  --journal /Users/aliyildirim/nerve-research-runs/scientific-interface-claims.sqlite \
  --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
```

Use the full independently verified installed-model digest; do not substitute a
model tag for immutable identity. Preserve the shared journal and consumed run
artifacts. A failed or completed run is not permission to repeat its eight calls.

## Implementation and status

New executable files: `memory_gateway/scientific_interface_tasks.py`,
`memory_gateway/scientific_task_interface.py`, `memory_gateway/scientific_interface_study.py`
under `src/nerve_awim/`, and `scripts/run_scientific_interface_study.py`.
Three corresponding test modules cover 28 scenarios. The verifier registers
these tests in its CPU/security groups. README and the final implementation
report link this evidence; historical source-pinned implementations are unchanged.

Reused components include verified-memory authority and retrieval, gateway scope
checks, local inference transport and revocation revalidation, the existing direct
strategy, source hashing, local model metadata/preload helpers, the root execution
lock and unique-dataset journal. The adapter and diagnostic runner are opt-in and
locally tested. Transport fault tests use mocks; the eight reported outputs are
actual model completions. Nothing was deployed. No PR or remote push was made.

Real Galahad GPU restoration and commercial licensing remain unverified, and
clinical integration remains synthetic-only. General self-learning, model-weight
training and scientific discovery are not established by this experiment.
