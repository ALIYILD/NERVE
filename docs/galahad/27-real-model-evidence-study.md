# Matched real-model evidence study

This study follows the successful single CPU readiness request. It measures a narrow integration behavior: whether the real pinned model can extract and cite a synthetic fact supplied through approved scoped memory, and what it says when the approved evidence does not contain the answer.

## Frozen protocol

Four fresh synthetic registry questions, each with two conditions, produce at most eight real inference requests. Relevant evidence contains the queried object's random code. Control evidence contains an equal-character-length fact about another object, with another code. Both use the same source identifier for the pair, the same query, capable model, CPU research profile, output budget and scoped gateway. Condition order alternates across pairs. Character length is matched, not tokenizer length; actual input-token counts are retained. Expected codes never appear in the query and are absent from control evidence. The original failed benchmark's questions are not reused.

The installed qwen2.5-coder:1.5b model is pinned by digest before and after execution, and implementation source hashes are rechecked before aggregates are produced. Endpoint metadata cannot detect a transient model swap followed by restoration between checks. A single empty-prompt preload precedes generation. The CPU research profile allows one concurrent request, 128 output tokens and a 90-second socket timeout. These are not hard process-wide wall deadlines. No retries or parameter tuning occur. The first request failure stops the study, and partial evidence is retained. Claim and checkpoints live in an operator-owned SQLite ledger; they are not independent sealed evaluation custody.

The main grounded-extraction metric checks exact expected-code and source-identifier tokens in relevant responses. Controls report target-code and decoy-code inclusion separately. A lexical abstention indicator is a heuristic, not proof of semantically correct refusal. Zero code extraction from missing evidence is not counted as a model failure. Full synthetic outputs are retained for review. This is four matched cases, not representative accuracy, statistical proof, causal learning or scientific discovery.

No outcome-learning feedback or model-weight update occurs during this study. Standard API defaults remain unchanged; CPU research runs only through trusted host construction. No real patient data, deployment or Galahad persistent KV restoration is involved. Normal runtime caching may affect timing and is not measured or attributed as an improvement.

## Results

Executed on 13 October 2026 with Python 3.10.0, macOS 26.5.2 x86_64 and local CPU qwen2.5-coder:1.5b. All **8/8 inference requests completed**, with one preload and no retries. Model digests and pinned source hashes matched before and after execution; the final SQLite checkpoint matches the exported report. [Full protocol, outputs, usage and timings](evidence/cpu-memory-evidence-v1.json).

| Observation | Relevant evidence (4 cases) | Irrelevant control (4 cases) |
| --- | --- | --- |
| Expected target code present | 4/4 | 0/4 |
| Expected code plus supplied citation | 3/4 | Not a control success metric |
| Decoy code present | 0/4 | 4/4 |
| Lexical abstention indicator | 0/4 | 0/4 |
| Prompt / completion tokens | 1,144 / 85 | 1,158 / 103 |
| Median request wall time | 37.791 seconds | 43.361 seconds |
| Request wall-time range | 35.501–44.118 seconds | 36.265–49.573 seconds |

The relevant response for JV24 returned the correct code but omitted its source identifier. Manual inspection found a more serious failure in **all four controls**: the model attributed the decoy object's code to the queried object. For example, evidence about KW63 produced “The access code for object JV24 is QAHN-7952.” Thus zero unsupported *target-code* matches does **not** mean zero unsupported answers. The frozen automated metric is narrow and does not measure this relationship error; the full responses expose it. No scoring rule or prompt was tuned after seeing the results.

Total measured inference wall time was 327.762 seconds, plus 3.704 seconds for preload; input/output totals were 2,302/188 tokens. These are request wall times, not separately measured prefill, restore or first-token latency. No GPU-energy, monetary-cost or KV-restoration measurement was made. Condition timing differences are descriptive only; this small CPU study does not establish a speed improvement.

**Disposition: integration completed; answer-grounding reliability failed on the control cases.** Do not promote this model configuration as reliably grounded or clinically suitable. The next bounded research candidate should address entity-to-fact matching, citation completeness and unsupported-answer abstention, evaluated on fresh cases with a separately frozen relationship-correctness evaluator. This report records an actual failure, not a completed fix or a self-learning improvement.

## Reproduction

```sh
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/benchmark_cpu_memory.py --database /tmp/nerve-cpu-evidence-reproduction.sqlite --run-id cpu-evidence-reproduction --output /tmp/nerve-cpu-evidence-reproduction.json --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
```

Use unused paths for independent reproduction; repeating the published dataset does not make it fresh held-out evaluation. Model/runtime and local permissions are required. Output overwrite is refused and consumed datasets cannot be replayed in the same ledger. Keep historical failed attempts intact.

Independent read-only review passed all nine mocked transport/claim tests and found no blocking issue. Those are fixture tests, not real-model outcomes.

Full regression before model execution: **1,182 tests passed**, zero failures/errors, 81.538 seconds. [Validation metadata](evidence/cpu-evidence-validation.json).
