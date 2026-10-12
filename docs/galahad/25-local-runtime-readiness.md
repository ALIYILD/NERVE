# Local runtime readiness and safe diagnostics

The previous eight-call evidence experiment stopped on its first request after approximately 30 seconds and remains consumed. Its sanitized error could not distinguish a timeout from a malformed response. This change adds that distinction without changing the public error text, production timeout limits or evidence authorization.

`InferenceUnavailable` remains a `RuntimeError` with message `inference_unavailable`. Its host-side `reason` is an allowlisted category: timeout, transport, invalid_response, circuit_open or capacity. For invalid responses, an additional allowlisted detail distinguishes output limits, model mismatch, completion/message shape, unexpected tool calls, content, usage and response size. Raw exceptions, prompts, responses and provider addresses are never included in these categories. Existing callers can continue catching RuntimeError. Circuit/failure counters and scoped source rechecks remain authoritative.

A separate operator diagnostic uses [Ollama's documented preload behavior](https://docs.ollama.com/faq) and [generate endpoint](https://docs.ollama.com/api/generate): one empty-prompt request with a two-minute keep-alive, followed by at most one 32-token gateway inference request. Preload and inference times are reported separately. Socket timeouts are 45 and 30 seconds respectively; these are not a hard process-wide wall-clock deadline against arbitrary trickling transports. Proxies and redirects are disabled and the runtime stays on literal loopback. No retries, downloads, global runtime configuration changes or production activation occur.

The diagnostic pins model digest before and after. It uses a new synthetic readiness marker, not any question from the consumed evidence benchmark. A successful readiness marker is a single integration check, not an accuracy benchmark or an independent model-improvement result. Warming model weights is not persistent attention KV restoration. Server residency can be extended by subsequent requests; the script does not forcibly unload models or disrupt other users.

## Execution evidence

The first preload completed in **3.700 seconds**. Its approved probe failed contract validation after **24.491 seconds** (including fixture setup), with no accepted completion. This independently establishes that the warmed request returned within its timeout, but the initial diagnostic did not identify the rejected field. [First attempt evidence](evidence/local-readiness-v1.json).

A second manually initiated diagnostic uses the same request/output limits and adds a static validation detail. It is not a rerun of the consumed benchmark and does not tune or score model accuracy. Both diagnostic attempts are retained. The second preload completed in **4.222 seconds**. Its probe failed after **25.937 seconds** (including fixture setup), with `reason=invalid_response` and **`detail=output_limit`**. That detail is emitted when the provider reports length termination or reports completion tokens beyond the requested cap. No incomplete output was accepted, no raw provider error was logged, and there were zero accepted completions. [Instrumented attempt evidence](evidence/local-readiness-v2.json).

The 32-token probe returned before the 30-second socket timeout but did not satisfy the complete-response contract. This cannot establish the exact cause of the earlier 128-token timeout, nor that simply preloading fixes the original benchmark. It identifies an output-budget incompatibility in the smaller probe. Resolving it requires a separately tested generation/budget configuration or a runtime able to complete the intended workload; validation remains fail-closed. The previously measured online-adaptation gain remains a separate synthetic tool result, not real-model improvement.

## Reproduction

```sh
.venv/bin/python scripts/verify_galahad.py baseline
PYTHONPATH=src .venv/bin/python scripts/probe_local_memory_readiness.py --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668 --output /tmp/nerve-local-readiness.json
```

The installed Ollama service and pinned qwen2.5-coder:1.5b model are required. Output creation is exclusive and precedes requests. Use an unused output path for independent diagnostic reproduction; the previous failed benchmark is not resumed. Local network/process permissions may be required. All task content is synthetic.

The preliminary full regression passed 1,162 tests in 61.757 seconds before the finer validation-detail change. Final regression: **1,164 tests passed**, zero failures/errors, 64.588 seconds. Independent review passed 18 overlapping offline tests. Final diagnostic source hashes match the executed files. [Validation metadata](evidence/local-readiness-validation.json). No default learning policy, clinical operation, deployment or model weights were changed.

Changed files: `memory_gateway/inference.py`, `scripts/verify_galahad.py`; added readiness CLI, two test modules, this report and three evidence files. No API endpoint, model weights or deployment configuration was added or activated.
