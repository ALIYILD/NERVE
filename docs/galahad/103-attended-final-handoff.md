# NERVE attended-run handoff — 16 October 2026

**Harder-bank result: adapted v1 scored 581/900. V4 is registered but unevaluated. No new holdout, signing or retained skill resulted from this run. All three pods are confirmed EXITED.**

Shutdown verification missed the 10:30 UTC deadline: the final fresh provider read was at 11:47:51 UTC, 77 minutes 51 seconds late. The stop request followed a RUNNING read at 10:15:08; its eventual result was EXITED, but the provider exposes no stoppedAt timestamp. The actual stop-effect time is unknown. Do not describe the pod as confirmed stopped at the request time. Conservative cumulative compute accounting through 11:47:52 is at most 15,597.911 seconds = 4.332753 GPU hours, estimated $2.556324 at $0.59/hour, excluding storage and not an invoice. This remains under the six-hour GPU cap, but timely shutdown assurance failed.

## Research outcome

- **L3 completed:** real family-B bank v3, 900 dev + 300 sealed holdout items, nine strata. Manifest `5095941f6aa42b369bcd72dece08406ee87290ea7c56e71ca5e1017c738afa43`. All three holdout slices remain unused.
- **L4 completed and replay-verified:** adapted v1 581/900, adapted bootstrap 356/900, always-abstain 300/900, random 136/900. Measurement-decoy was worst at 33/100, with 67 decoy selections. [Doc87](87-bank-v3-dev-study.md) contains the full stratum table and descriptive intervals. This measures adapted preparation on a harder synthetic bank, not unchanged retained skill v1 or clinical generalization.
- **L5 completed:** one reviewed extraction-schema candidate restricts source_id choices to current records matching query entity/mass/mg. It preserves prompt facts/order, numeric values, decoder and abstention rule. Its predicted risk is wrong numeric values paired with forced relevant citations. Four focused tests passed, with no model calls. Registration completed 10:14:51 UTC, SHA `945f3719f2e58ac4b9984b1cff7288f1e0812d82f9d632eaf982c3ae62c44310`; [doc88](88-v4-registration.md). Independent review verified source/hypothesis/proposal/episode/history bindings. This is a deterministic pipeline hypothesis, not model learning.
- **L6 not run:** no candidate dev or holdout registration/inference. The remaining window could not fit the complete dev study after evidence preservation; the inference cutoff was not extended. No efficacy verdict exists for v4.

The existing retained skill-v1 record remains unchanged. No registry/trust changes or signature occurred. The historical 8/8 pre-written-handler selection remains excluded as evidence of learning. No de-identified clinician-verified cases were supplied or invented.

## Calls, runtime and preservation

All inference used Runpod A40 with qwen2.5-coder:7b digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, served by Ollama 0.40.5. No laptop inference occurred. Cumulative physical attempts were 1,510: two five-call calibrations plus 1,500 L4 calls, zero timeouts. L4 wall time was 2,076.0616 seconds; allocated study compute was about $0.34024, separate from startup/idle costs.

The root bulk-backup operation did not complete successfully; it eventually returned SSH 255 / connection closed. Fallback read-only SCP preserved the actual full L4 journal, including 3,000 attempt receipts and 3,600 row receipts, plus all 1,510 shared claims. Nothing was reconstructed. Exact local replay with network disabled passed at 10:13:52. The complete private archive is `/Users/aliyildirim/nerve-research-runs/attended-20261016/nerve-canada-final.private.tar.gz`, mode 600, SHA `c387c9d9bb04bd536d521f7e4636cd249d141756cdc0f65604b55b8c4e39a8f6`. The separate sealed-bank archive and both calibration histories remain durable outside Git. Public aggregate/registration/replay receipts are versioned; private items remain private. All 283 L4 source pins and 17 protected pins still match.

Pod intervals for conservative accounting:

| Pod | GPU | Running interval / upper bound | Seconds |
|---|---|---|---:|
| lg0svvuenxvbno | A40 | 15 Oct 23:08:59.019 to 23:28:19.802 UTC |1160.783|
|97vr620wnmtuga|A40|16 Oct 06:27:28.749 to 07:13:45 UTC upper bound|2776.251|
|b7qj6qyx9ij6gg|A40|16 Oct 08:33:31.123 to 11:47:52 UTC conservative upper bound; actual stop time unavailable|11660.877|

All three were freshly read EXITED at 11:47:51 UTC. Preserved storage may still bill. No pod or storage was deleted. The additional Canada pod was explicitly authorized after both preserved hosts failed to restart.

## CPU lane and retained limitations

The separately registered CPU preflight passed the exact 2,228-test inventory: 2,226 passed, two dependency skips, zero failures/errors, sources unchanged. Skips were jsonschema OpenAPI validation and the official MCP SDK. Earlier 180-second/1,200-second timeouts remain recorded; this is not a retroactive pass of the original timeout policy. The 18 bank/harness tests, five generic L5 checks and four candidate checks are distinct scoped validations.

The experimental sequential gate remains unsigned/inactive. Its 200-proposal simulation accepted 0/40 harmful **and 0/100 good** proposals, using 16,386 rather than 20,000 items. The 18.07% item saving meets the literal nominal criterion but does not demonstrate useful promotion power. The fixed-process analytical bound for 80% expected good acceptance exceeds 26,103 expected good-only items; no new simulation or model calls were added.

## Next authorized work requires a new execution window

Preserve v4 unchanged for a prospective dev study against adapted v1 and controls on the same bank, with fresh runtime/clock/source verification and cumulative budget accounting. Only a complete eligible dev verdict can permit the single conditional slice 1; slices 2/3 stay sealed. No signing follows automatically. A new calendar window must be recorded before any new inference; this run's 10:15 UTC cutoff has expired. Clinical cases remain a separate unfulfilled real-data prerequisite.

Final source/hypothesis freeze before evaluation: `80e5551`; final publication commit is recorded in the Desktop handoff after push. This closes an operational run with incomplete research, not a completed self-improvement demonstration.
