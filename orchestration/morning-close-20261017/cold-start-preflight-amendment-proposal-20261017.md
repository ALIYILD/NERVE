# Proposed infrastructure preflight amendment — not active

The sole-W0 preflight remains incomplete_infrastructure. Its first historical latency request took 66.33078790735453 seconds, above the registered maximum 62.35253082308918 seconds. The following four requests took 1.6275664907880127, 1.6983141107484698, 1.6885026609525084 and 1.553256728220731 seconds. No dev replay or holdout ran. These observations are consistent with startup overhead; they do not by themselves prove its cause.

## Decision requested

Authorize one prospectively registered infrastructure recovery attempt that separates model loading from steady-state latency. This changes the historical preflight procedure and therefore requires explicit approval; a general continuation does not silently amend it. Existing failed receipts remain immutable and count toward pod failure limits.

## Proposed procedure

1. Recheck integrity and focused-module source receipts, then obtain fresh MCP inventory. At most one pod runs for recovery. Do not retry the capacity-unavailable original host. Keep A40, Ollama 0.40.5 and the full dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364 digest mandatory.
2. Before any dispatch, register a new private run directory, assigned pod/connection, worker source hashes, existing request hashes, this amendment hash, timeout/retry rules, wall-time budget and remaining spend/call limits.
3. Perform one explicitly registered model-load request with no study input and no requested generated answer. Count it as one physical model-endpoint call, journal the exact request and response, and record its full loading latency and cost. This request is not a study observation. Allow no result-driven loading retries. Validate the installed Ollama request format before authorizing execution.
4. Run the same five historical latency requests, preserving their order, decoding settings and original inclusive latency band [1.5230746129527688, 62.35253082308918] seconds. Do not discard slow observations or select a passing subset. Any out-of-band result fails this attempt.
5. Only after all five pass, replay the first ten doc-106 candidate-v4 dev items in registered order. Require canonical decoded bytes to match for all ten. Preserve deterministic no-model items; expected endpoint calls are five latency plus seven dev plus one load, with every registered transport attempt separately counted.
6. Write preflight_ok only if all requirements pass. Otherwise stop the pod, verify EXITED, and record incomplete_infrastructure. A second consecutive infrastructure failure retires that pod for the night. No holdouts, candidate changes, gate changes, signing or retention are authorized by this amendment.

## Approval text

“Authorize one cold-start-separated preflight recovery attempt as proposed in orchestration/cold-start-preflight-amendment-proposal-20261017.md. Preserve the failed run and all existing model, replay, budget and stop rules.”

Until approved: no extra model calls, no pod start, no preflight_ok. CPU-only worker tasks may continue.
