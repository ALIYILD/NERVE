# Explicit CPU research inference profile

The earlier local-model diagnostic reached an output-limit rejection with 32 output tokens; the original 128-token attempt failed near its 30-second timeout. Those failures remain recorded. This increment adds an explicit host-selected budget for slow CPU research, without treating incomplete output as valid.

## Configuration and boundaries

`LocalInferenceAdapter(..., runtime_profile="cpu_research", max_output_tokens=128, timeout_seconds=90)` permits at most 128 output tokens, up to 90 seconds of socket timeout, and one concurrent request per adapter instance. Profile selection is strictly allowlisted. The profile requires an explicit output cap at or below 128; the existing constructor default 256 is intentionally not silently changed.

The standard profile retains its prior defaults and limits: default 10-second timeout, maximum 30 seconds, default 256 output tokens, maximum 2,048 and four slots. Its prompt is unchanged. CPU research appends a fixed concise-answer instruction to the trusted system message; untrusted-evidence, citation, abstention, clinical restrictions and human review remain intact. A shorter answer is requested, not assumed correct.

The runtime service configuration's exact-key validation does not expose `runtime_profile`, and no API caller can select it. Only trusted Python construction and the explicit diagnostic CLI flag opt in. This is a local research capability, not a production service configuration change.

Both profiles require a complete stop response, expected model identity, bounded content and usage, no tool calls, and post-inference scope/source rechecks. Output-limit responses still fail closed. Proxies/redirects remain disabled. Timeouts are socket-operation limits, not a hard process-wide wall deadline. No automatic retry, model download, weight update, deployment or Galahad KV restoration occurs.

## Frozen diagnostic

After full regression, one empty-prompt preload followed by at most one 128-token diagnostic inference is run with the pinned installed `qwen2.5-coder:1.5b` model. The same synthetic readiness marker is used for operational diagnosis, not held-out evaluation. This changes budget and concise instruction together; a successful result cannot isolate their individual effects or establish model intelligence improvement. Earlier consumed accuracy-benchmark questions are not reused.

**The real local diagnostic completed successfully.** Exactly one preload and one inference were attempted; one completion was accepted. Preload took **3.317 seconds** and gateway inference **72.684 seconds**. Usage was **262 prompt tokens, 15 completion tokens, 277 total tokens**. The model digest matched before and after.

Actual synthetic output:

> Synthetic readiness marker is READY42. Source_id: readiness-source

Both expected marker and source tokens were present. The adapter also required a complete stop response, bounded text/usage, the configured model identifier, and unchanged authorised evidence after generation. The fixture uses a separately issued read-only caller. This was genuine local model execution through the gateway, not a mocked completion; no network service was deployed. [Full diagnostic evidence](evidence/cpu-readiness-v3.json).

This single result establishes a working integration path for this request under the CPU research profile. It does not establish a model accuracy gain, speedup, reliable workload latency, scientific discovery, persistent KV restoration or improved model weights. The 72.684-second measurement includes retrieval, prompt processing and generation, not isolated prefill/TTFT. No representative cost or energy study was performed. The concise instruction and larger timeout/output allowance changed together, so their contributions cannot be isolated. Previous failures remain valid evidence for their configurations.

Full regression: **1,173 tests passed**, zero failures/errors, 52.936 seconds. This adds six CPU-profile tests and three readiness tests to the previous suite. Independent review passed 19 overlapping offline tests, confirming unchanged standard behavior and rejection of truncation/model/usage violations. The full suite completed before the actual model probe began. Recorded diagnostic source hashes match the executed files. [Validation metadata](evidence/cpu-readiness-validation.json).

Files modified: `memory_gateway/inference.py`, `scripts/probe_local_memory_readiness.py`, `scripts/verify_galahad.py`, `tests/test_local_memory_readiness.py`. Added `tests/test_inference_cpu_profile.py` and this report/evidence. The actual model and gateway functionality are locally tested; CPU research is opt-in, not enabled by service configuration. No PR, deployment, clinical use or learning-policy promotion occurred.

## Reproduction

```sh
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/probe_local_memory_readiness.py --cpu-research --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668 --output /tmp/nerve-cpu-readiness.json
```

The CLI reserves a new output file before requests and refuses overwrite. Installed local Ollama/model and loopback permission are required. The previous standard diagnostic remains available by omitting `--cpu-research`. No default learning policy or clinical workflow is promoted.
