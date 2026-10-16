# Overnight resumption handoff — 16 October 2026

**No new self-improvement result was measured.** The revised adapter and harder-bank tooling passed 18 focused tests, but the execution approval delay carried the run beyond the registered 07:00 London wrap-up. The actual bank was not generated or sealed, and no model study or candidate design occurred. The pod is stopped. No new skill awaits signature.

The initial completed attempt is preserved in [doc 90](90-overnight-handoff.md). The user subsequently authorized a separately versioned adapter and CPU preflight budget; [doc 91](91-overnight-resumption.md) records that resumption. Historical results remain unchanged.

| Loop | Resumption outcome | Evidence |
|---|---|---|
| L0/L1 integrity | All 17 original protected hashes unchanged | `evidence/resumption-wrapup-integrity.json` |
| L1 CPU preflight | 1,200-second run timed out; revised 3,600-second preflight passed: 2,228 tests, 0 failures/errors, 2 skips | Doc 93; durable CPU directories |
| L1 pod/runtime | Exact Ollama 0.40.5 and exact model digest verified by read-only API; stopped during CPU preparation | `evidence/resumption-pod-lifecycle.json` |
| L2 | Initial sequential simulation accepted 0/40 harmful **and 0/100 good**, using 16,386 items; useful promotion power not demonstrated | Doc 85; analytic follow-up doc 94 |
| L3 preparation | New adapter, generator, independent truth validator, nine-stratum sealer and study harness; 18/18 focused tests passed | Doc 92 and source-hashed receipt |
| L3 actual bank | Not generated; not sealed; no real manifest or holdout location | No bank generation executed |
| L4 | Not run; no bank-v3 accuracy measurement | Wrap-up cutoff |
| L5/L6 | No candidate designed, no candidate dev study, no holdout consumption | Wrap-up cutoff |
| L7 | Pod EXITED; protected integrity checked; revised CPU preflight passed; publication below | This handoff and conductor status |

The adapted protocol preserves raw near-duplicate names, source IDs, record order, stale records and qualified quantities. Both comparator arms receive identical facts. These are **adapted pipelines**, not unchanged retained skill v1. The intended bank remains 900 development plus 300 holdout items across nine strata, three sealed 100-item holdout slices. The temporary 1,200-item bank used by a unit test is a test fixture, not the research bank.

The final focused run passed 18 tests in 19.442 seconds with mocked transport and zero model calls. Independent review verified source/log hashes and the original protected paths. Prospective limits include L4 1,800 seconds, cumulative candidate-development plus holdout L6 2,400 seconds, 6,000 physical attempts, six total running GPU hours, and the London wrap-up cutoff. The previous 17-test receipt is preserved separately; no test outcome was silently replaced.

## Compute and inference

Pod `lg0svvuenxvbno` is an NVIDIA A40 at the live-read rate of $0.59/hour. The user-started interval began at 2026-10-15T23:08:59.019Z and was stopped/read back EXITED at 23:28:19.802Z. The conservative running upper bound is **1,160.783 seconds (0.32244 GPU hours), approximately $0.19024 compute**. Storage charges are separate; this is an estimate, not an invoice. No replacement pod was created.

Fresh readback at **2026-10-16 06:04:02 UTC** confirmed **EXITED**. Total resumption model calls: **0**. Runtime recovery verified `qwen2.5-coder:7b` digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`; no other model was used. The original initial attempt used zero GPU hours, so the resumption interval is the only new running interval in these overnight records.

## Evidence and next run

- The actual retained skill-v1 consumer previously passed 16/16 checks with zero inference. Initial slow tier passed 521 tests in 247.012 seconds. Neither is mislabeled as a pass for the new full preflight.
- The sequential gate remains experimental and inactive. Its 18.07% item reduction came with zero good accepts; there is no useful promotion claim. For the fixed sequential-process family analyzed in doc 94, 80% expected good-proposal acceptance requires at least 26,103.67 expected items for the 100 good proposals alone, exceeding the 20,000-item budget. This is a scoped analytic bound, not a claim about every possible sequential gate. The follow-up does not draw new validation outcomes or retune the completed simulation.
- Existing registry, trust, canonical gates, model-bound retention evidence and sealed older banks remain unchanged. No signing or activation occurred.
- The earlier 8/8 selection among prewritten handlers is **not evidence of learning**; a fixed handler also achieved 8/8.
- Source freeze and test evidence are published on `feature/galahad-persistent-memory`. Private old evidence remains outside temporary storage. New research item-level evidence does not exist because studies were not run.

CPU admission completed after the research window had closed. The next research run needs a new prospective execution window and revalidation of the frozen source/runtime identity, with appropriate checks if code changes. Then generate and independently validate the real bank, seal it before candidate design, calibrate on the exact Runpod model, and run adapted-v3 development. Design a candidate only from observed aggregate failures, with holdout conditional on its preregistered dev eligibility. Clinician-verified real cases remain necessary for claims beyond synthetic tasks; none were invented or supplied here.

The revised CPU preflight completed in 439.471 seconds of suite execution and 470.021 seconds wall time. Its exact selected inventory and registered source hashes matched. Of 2,228 tests, 2,226 passed and two dependency checks skipped: `test_actual_inference_and_scope_responses_match_openapi` needed `jsonschema`, and `test_optional_mcp_real_stdio_inspection_binding` needed the official MCP SDK. Those checks were not executed or counted as passes. This is a pass under the separately registered 3,600-second protocol; it is **not** a pass of the unchanged canonical 180-second gate. Earlier timeout evidence remains preserved.

Final publication SHA is recorded in the Desktop handoff after push; this versioned document does not embed its own circular commit hash.
