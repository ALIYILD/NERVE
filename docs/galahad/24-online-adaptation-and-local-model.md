# Online adaptation and real local inference

## Why this experiment differs

The prior v3 training traces show fast discounting can react better during continuing feedback while selecting a worse policy when learning is frozen. Frozen probes and online adaptation measure different behavior. This study does not relax v3 gates or re-score its holdout. It registers one fixed candidate on new episodes, scoring each action before updating from its outcome.

This follows the test-then-train approach described in [River's progressive validation implementation](https://github.com/online-ml/river/blob/main/river/evaluate/progressive_validation.py). We reuse NERVE's trusted evaluator and registered tools rather than adding River as a dependency. [Research on nonstationary contextual bandits](https://proceedings.mlr.press/v75/luo18a.html) also distinguishes performance against fixed policies from adaptation to changing environments; its guarantees do not apply to this heuristic.

## Registered online protocol

Sixteen fresh seeds 7001–7016, four scenarios (stationary, abrupt, recurrent, mixed), 32 episodes per trial and four arms produce exactly 8,192 tool executions. Candidate: window 3, relevance ties, per-observation discount half-life 1. Baseline: the same window/ties without discount. Fixed lower-only and trim-and-lower controls use the same registered tool capabilities. No candidate tuning occurs.

The agent never receives scenario, seed, expected answer or future outcomes. Only its selected memory receives independently judged feedback. The runner checks the feedback count before and after each episode. All online episodes are scored; none are retrospectively rescored after learning. Dataset/protocol claims survive interruption and prevent replay in the same operator-owned ledger. This is public synthetic prospective evaluation, not a sealed holdout.

The predeclared recommendation gate requires positive aggregate gain and no scenario loss. Any passing result is only a candidate for review; no default, clinical or deployment promotion is authorized by this experiment.

## Real local model smoke protocol

A metadata read confirmed local Ollama model `qwen2.5-coder:1.5b`, GGUF/Q4_K_M, 986,062,089 bytes, digest `d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668`. This is a 1.5-billion-parameter model; no download or remote provider is required.

Four frozen synthetic registry questions each receive two matched conditions: an approved relevant fact and an approved equal-character-length irrelevant fact. Both invoke the existing `LocalInferenceAdapter` through authoritative scoped memory. Arms alternate order. Maximum 8 model calls, 128 output tokens each, temperature 0, 30-second per-call timeout; the first failure stops the experiment. Model digest must match before and after. No API keys or clinical data are used.

The narrow score requires inclusion of the exact target code and supplied source identifier. It is an evidence-use smoke check, not a general semantic correctness, abstention-safety or intelligence metric. Control zero is the expected result when the target code is absent; it does not establish that the model abstained appropriately. Measured usage, actual synthetic outputs and end-to-end times are retained. Model/server timeout behavior is recorded honestly; an attempted invocation is not necessarily a completed generation.

The smoke test does not update outcome memory or model weights. It tests real local text prefill; persistent Galahad KV restoration remains unverified.

## Results

The fixed discounting candidate passed the prospective review gate: **1,727/2,048 (84.33%)**, compared with baseline **1,545/2,048 (75.44%)**. Difference: **+8.89 percentage points**, or 182 additional correct episodes. The descriptive paired seed-cluster bootstrap 95% interval is **+6.98 to +11.43 points** across 16 seeds (1,000 resamples). Temporal dependence exists within streams; the report's episode-level McNemar p-value is descriptive and should not be treated as independent-episode inference.

| Scenario | Baseline correct /512 | Candidate correct /512 | Difference |
| --- | --- | --- | --- |
| Stationary |505|505|0|
| Abrupt change |466|489|+23|
| Recurrent change |257|405|+148|
| Mixed |317|328|+11|

Fixed lower-only and trim-and-lower controls scored 1,040/2,048 and 1,008/2,048 respectively. These controls are secondary; the main comparison is against the capable existing adaptive learner. Neither arm saw future labels. Full [online evidence](evidence/online-adaptation-v4.json) retains per-episode outcomes, selected strategies, feedback counts and source hashes.

The study executed **8,192 two-stage pipeline episodes / 16,384 primitive transformations**, in 155.371 seconds on Python 3.10.0/macOS 26.5.2 x86_64. The historical `tool_executions` field is explicitly a compatibility alias for pipeline episodes, not individual primitive invocations. Regression tests and the local-model attempt overlapped, so wall time is not a comparative performance benchmark. No GPU energy or total monetary cost was measured.

**The local-model smoke benchmark failed and remains consumed.** The first relevant-evidence request returned the adapter's sanitized `RuntimeError` after 30.005 seconds, consistent with reaching its 30-second deadline. No accepted completion or token usage was returned, no second request was attempted, and no aggregate score was produced. The exact underlying exception was intentionally sanitized. A later `ollama ps` read showed the pinned model resident at 1.1 GB, 100% CPU, context 4096. This does not prove whether cold load, CPU inference speed or another runtime condition caused the failure. The benchmark was not rerun under a new name or relaxed deadline. [Failed real attempt evidence](evidence/local-model-evidence-v1.json).

Full regression: **1,146 tests passed**, zero failures/errors, 62.273 seconds, with authorized local-server/process-isolation permissions. Seventeen new tests cover the two harnesses. Independent review passed those 17 tests plus 7 subtests; these overlap, not additional distinct tests. Source hashes were rechecked against the exact executed files. [Validation metadata](evidence/online-adaptation-v4-validation.json).

## What is ready and what remains

The existing opt-in host configuration `VerifiedOutcomeLearning(..., window=3, tie_break="relevance", discount_half_life=1)` now has positive evidence for this particular continuing-feedback synthetic workflow. Recommendation: **candidate for review**. Existing defaults remain unchanged. This does not overturn the earlier negative frozen-policy study: rapid adaptation and frozen-policy retention are different objectives. No live service, clinical workflow or model weights were changed.

Real-model evidence-use accuracy, broader scientific tasks, delayed/noisy independent feedback, larger workloads and licensed persistent KV restoration remain unverified. Public synthetic seeds and an operator-owned claim database are not independent sealed test custody. General intelligence or scientific-discovery improvement has not been established.

## Reproduction

From the repository root with dependencies installed:

```sh
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/run_online_adaptation_study.py --database /tmp/nerve-online-reproduction.sqlite --run-id online-reproduction-v4 --output /tmp/nerve-online-reproduction.json
PYTHONPATH=src .venv/bin/python scripts/benchmark_local_memory.py --database /tmp/nerve-model-reproduction.sqlite --run-id model-reproduction-v1 --output /tmp/nerve-model-reproduction.json --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
git diff --check
```

Use unused paths for independent reproduction; do not use a new database to repeatedly tune against published episodes. The local-model command requires the specified model and localhost Ollama service and may fail at the same deadline. No download, deployment or remote paid calls occur. The full suite requires local-server and process-isolation permissions. A KeyboardInterrupt in the local-model harness leaves the durable status `consumed` and may leave an empty report; replay remains blocked.

Files added: `memory_gateway/online_adaptation_study.py`, `scripts/run_online_adaptation_study.py`, `scripts/benchmark_local_memory.py`, two corresponding test modules and this report/evidence. Existing gateway, authority, feedback learner, automation, registered tools, inference adapter, claim logic and statistical summaries are reused. CPU/security verification groups include both new test modules. No production implementation defaults were modified.
