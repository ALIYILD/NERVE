# Attended Runpod latency calibration

The five prospectively registered public fixtures completed on replacement A40 pod `97vr620wnmtuga`: **five physical attempts, zero timeouts**, 23.580 seconds study wall time. The previously interrupted launch made no calls; this was the first dispatch.

Measured request times were 15.372752 seconds (cold load), 2.097603, 2.200731, 1.701292 and 1.757324. Median:2.097603 seconds; maximum:15.372752 seconds. The registered downstream timeout is three times the maximum, **46.118255 seconds**, with up to two identical-request retries on timeout only. All physical attempts share the 6,000-attempt budget; five are now consumed.

Registration SHA-256:`e2f3ac8b54c2bb531974da1f8f70892863c58a9201388ca6d6d82890690d62b2`. Public registration and aggregate are `evidence/attended-calibration-{registration,aggregate}.json`. Full private journal is durably copied under `/Users/aliyildirim/nerve-research-runs/attended-20261016/nerve-attended-calibration`. Runtime/model identity remains the exact registered Ollama0.40.5 and full qwen2.5-coder:7b digest.

These are public stress fixtures selected prospectively for large payloads, not research development or holdout observations. Calibration accuracy is not a basis for candidate design. No candidate has been designed; all actual holdout slices remain sealed.

Before L4, the 30-minute cap needs a feasibility assessment: the expected1,500 logical calls multiplied by the largest-fixture median is about52.4minutes. That is a conservative stress-fixture extrapolation, not a measured runtime for the smaller/bootstrapped tasks. The cap must not be silently expanded; any prospective amendment or stop is recorded before dispatch.

Allocated calibration compute estimate is about$0.00386 at$0.59/hour. This is only the study allocation; all startup, download, SSH configuration and approval-wait time remains part of total cumulative GPU billing.
