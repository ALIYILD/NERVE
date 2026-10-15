# Real-model strategy learning pilot

This pilot connects approved strategy memory to actual local model completions,
independent scientific-evidence scoring and persistent outcome preferences.
Existing automatic learning executes synthetic string tools; it is not silently
relabelled as language-model learning. The new host-owned path reuses verified
outcome memory, scoped retrieval and the bounded local inference adapter.

Four frozen synthetic tasks test measurement/entity binding, unit support and
conflicting evidence. Two fixed registered strategies receive the same scoped
records for each task. Outputs must follow the exact measurement tuple grammar
or `ABSTAIN`; no deterministic answer repair is credited to the model.

Eight completions are training/development evidence only. Feedback updates
strategy preferences using actual raw-output correctness. A training preference
is not an independent improvement result. The default policy cannot be promoted
from this pilot; fresh validation remains necessary. No model weights are trained,
no scientific discovery is established, and no patient data or clinical actions
are involved.

## Frozen execution contract

The local model is `qwen2.5-coder:1.5b`, operator-pinned to digest
`d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668`.
Both strategies use the existing `cpu_research` adapter profile: temperature zero,
128 output tokens, one concurrent call and a 90-second socket timeout. This is
not a hard total process deadline. One preload and two model-identity lookups are
permitted. No transport failure is automatically retried.

The direct and checklist strategies share the same output contract and approved
facts. The checklist adds a reminder to check entity, measurement, units,
conflicts and citation. Retrieval uses the unchanged task query; the prefix is
inserted only into the model request. The runner verifies record order and
context digest for each pair instead of assuming retrieval preserves insertion
order. Answer keys remain in the trusted evaluator, outside the model query.

An approved strategy record contains a registered identifier, not executable
instructions. Host code maps that identifier to a fixed prefix. Fact evidence and
strategy memories occupy separate scoped contexts. Existing `VerifiedOutcomeLearning`
credits independently judged raw outputs to strategy utility with window four
and an eight-observation quota. `AutomaticLearningRun` supplies durable claims,
consumption and failure accounting; its original email-specific execution remains
unchanged.

The exact answer contract is `entity|measurement|value|unit|source_id`, or
`ABSTAIN` when unsupported in the requested unit or contradicted. Surrounding
whitespace is ignored; explanatory prose, repaired citations and converted units
are not accepted. `non_abstaining_contract_failure` describes a failed output
contract, not a proof of factual falsehood. An always-ABSTAIN control scores 2/4
per strategy (4/8 across the call roster), so overall accuracy alone is inadequate.

Completed restart validates all eight claims, feedback task hashes, raw scores,
usage, scoped evidence and ranking without a network request. It verifies the
historical study, not current model health. Failed identity/source checks and
interrupted studies invalidate rewards while preserving consumed attempts.

## Actual result

All eight actual model requests completed on 13 October 2026 with the pinned
model and unchanged source hashes. Every raw output was `ABSTAIN`.

| Strategy | Exact correct | Supported answers | Correct abstentions | Format failures | Final training utility |
|---|---:|---:|---:|---:|---:|
| Direct | 2/4 | 0/2 | 2/2 | 0/4 | 0.5 |
| Checklist | 2/4 | 0/2 | 2/2 | 0/4 | 0.5 |
| Always abstain control | 2/4 | 0/2 | 2/2 | 0/4 | Not learned |

The control is calculated from the frozen contract and makes no model requests.
Both strategies fail supported extraction. Neither is superior, and neither is
promoted. Four feedback observations per strategy were genuinely persisted; the
learning mechanism works, but this experiment does not show useful adaptation.
The nominal Beta-smoothed utility is (1 + 2 successes)/(2 + 4 observations) = 0.5.

Measured prompt/completion totals were 3,686/32 tokens. The eight timed
inference-and-feedback sections totalled 317.879 seconds, median 37.497 seconds,
range 35.403–54.909 seconds; preload took 5.395 seconds. These timings include
feedback work and are not separate prefill/restore/first-token measurements or
speedup evidence. The local environment was Python 3.10.0 on macOS x86-64 using
the CPU research profile. No GPU, energy or monetary savings were measured.

The complete result passed independent review against all 19 pinned sources,
model metadata, raw scores and SQLite records. A separate fresh process resumed
with metadata, preload and model-response functions disabled: zero new network
calls, identical report/utility/claim records, eight claims and eight feedback
rows. This proves persistence of the historical learning result, not improvement.

The unresolved failure is universal abstention, not malformed output. A revised
instruction/evidence interface is a plausible next hypothesis; this pilot does
not isolate its cause. Future work must freeze a new candidate and use fresh
cases rather than repeatedly tuning against these four public tasks.

## Evidence and reproduction

The live synthetic research database is
`/Users/aliyildirim/nerve-research-runs/scientific-model-learning-v1/memory.sqlite`.
The [full result](evidence/scientific-model-learning-v1.json),
[measured summary](evidence/scientific-model-learning-summary.json),
[restart verification](evidence/scientific-model-learning-resume.json), and
[validation receipt](evidence/scientific-model-learning-validation.json) are archived.
Full-result SHA-256:
`fb4310758a7e72ae435d6f0d96d46dd457a811707199c6fc48776e1a12692510`.

```sh
PYTHONPATH=src .venv/bin/python scripts/run_scientific_model_learning.py --directory /private/tmp/nerve-scientific-learning-reproduction --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_scientific*.py' -v
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
```

Use a fresh directory for independent replication; repeat the same command for
completed resume without inference. The published cases remain development data
when reproduced. The CLI needs the operator-owned local model service. Failures
consume the run; do not clear its ledger or silently retry the same failed study.

Before model execution, full regression passed **1,747 tests in 143.832 seconds**,
with zero failures/errors. The 22 new focused tests use mocked transport with
real memory/claim/feedback machinery; they are distinct from the eight actual
model completions. No source changes followed that verification.
