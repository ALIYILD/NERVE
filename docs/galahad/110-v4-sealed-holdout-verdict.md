# Sealed v4 holdout verdict: promote_proposal

**The frozen v4 candidate scored 93/100 on sealed bank-v3 slice 1 versus adapted v1 at 72/100. The registered verdict is promote_proposal. The proposal remains unsigned and unretained; existing skill v1 is unchanged. All six pods are confirmed EXITED.**

This is evidence of improvement in the adapted deterministic extraction pipeline on a sealed synthetic holdout. Candidate design used only completed L4 aggregate failure counts after bank sealing. The source-selection schema candidate remained unchanged through development and holdout. Model weights did not change, and this is not clinician-verified real-world evidence.

## Stratum results

All results below are aggregate counts. Intervals are descriptive 95% Wilson intervals for v4. Small strata give wide uncertainty: even 11/11 has a 74.1% lower bound. The registered gate required strict overall gain versus the three controls, no per-stratum regression versus adapted v1 and zero observed domain violations; it did not require a 90% or 95% confidence lower bound in every stratum.

| Stratum | V4 correct | V4 interval | Adapted v1 | Always abstain | Random |
|---|---:|---:|---:|---:|---:|
| supported-measurement | 12/12 | 75.8–100.0% | 6/12 | 0/12 | 0/12 |
| measurement-decoy | 11/11 | 74.1–100.0% | 7/11 | 0/11 | 1/11 |
| entity-decoy | 11/11 | 74.1–100.0% | 5/11 | 0/11 | 1/11 |
| unit-mismatch | 11/11 | 74.1–100.0% | 11/11 | 11/11 | 3/11 |
| conflict | 11/11 | 74.1–100.0% | 11/11 | 11/11 | 3/11 |
| multi-source-agreement | 8/11 | 43.4–90.3% | 7/11 | 0/11 | 1/11 |
| stale-vs-current | 11/11 | 74.1–100.0% | 9/11 | 0/11 | 0/11 |
| format-variant-agreement | 7/11 | 35.4–84.8% | 5/11 | 0/11 | 2/11 |
| dissenter | 11/11 | 74.1–100.0% | 11/11 | 11/11 | 3/11 |

Totals: v4 93/100, adapted v1 72/100, always-abstain 33/100 and random 14/100. V4 improved by 21 correct answers with no stratum regression. Seven wrong-provenance answers remain: four in format-variant agreement and three in multi-source agreement. Zero observed domain violations, invalid formats and false abstentions do not mean zero errors.

Development previously scored 839/900 versus 581/900, with 61 wrong-provenance errors. Development and holdout are separate dev and holdout splits within bank v3 and are not pooled into a stronger confidence claim. The result supports this exact candidate/pipeline, model digest and synthetic task contract.

## Execution and evidence

Slice 1 was consumed once after exact candidate, prior eligibility, sealed-bank, fresh calibration, runtime, source and time-budget checks. Slice 2 and slice 3 were not registered or evaluated. Holdout completed all 400 rows with 134 logical/physical model calls, zero timeouts and 461.789785 seconds study wall time. Median request latency was 1.653597 seconds and maximum 2.031293 seconds. Fresh public calibration added five calls with zero timeouts; max 5.412097 seconds gave a 16.236291-second timeout with two identical-request timeout retries. The cumulative shared ledger contains 2,854 attempts: 2,715 prior plus 139 new.

The model was qwen2.5-coder:7b, digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, served by Ollama 0.40.5 on NVIDIA A40 pod 5xndo7i7s5r9zn in EU-SE-1 at $0.59/hour. All inference was remote; the laptop performed CPU orchestration and replay only. Accuracy and efficiency are measured here; robustness beyond this seed is not measured; safety diagnostics are harness-specific; UX is n/a.

The single controller process was approved and observed waiting before pod creation. It then completed upload, watchdog admission, restore, backup round trip, bootstrap, fresh calibration, holdout registration/run/replay, final backup/download and stop request within that one invocation. This actual run had no intervening per-stage approval gaps. The prior failed approval-delayed window remains documented in document 108.

Local offline replay passed with network calls disabled. It reconstructed new calibration/holdout requests, scores and aggregates, verified every prior claim hash plus all 2,854 contiguous ledger entries, and reconciled the exclusive slice marker with the frozen candidate and exact prior dev/calibration registrations. Historical parent journals were checked against their completed offline proof and original archive, without rerunning the 900-item scientific study. Item-level evidence remains private.

## Shutdown and cost

Provider start was 2026-10-16T17:58:15.091Z. Root independently verified the final pod EXITED at 18:15:10 UTC and all six pods EXITED by that time, before the 18:28:15.091 stop deadline. Exact stop-effect time is unavailable, so cost accounting uses the later confirmation time. This interval is at most 1,014.909 seconds, approximately $0.166332 compute.

Cumulative conservative usage is 21,869.049 seconds (6.074736 GPU hours), approximately $3.584094 compute at $0.59/hour, below the explicitly revised 6.5-hour cap. Storage is excluded; these are estimates, not invoices. Earlier registrations and the prior six-hour cap were not retroactively rewritten.

## Durable artifacts and decision boundary

Final private archive: `/Users/aliyildirim/nerve-research-runs/final-holdout-20261016/final-holdout-evidence.private.tar.gz`, mode 600, 466,918 bytes, SHA `5216c3fe3532e9bbc5f9d79bdae8c0ed234ee448747339c5df63240df0e97d1e`. It contains all new journals, complete shared ledger and bank-consumption metadata. Historical dev/calibration/L5 evidence remains in predecessor archive SHA `d82ff7929f9e174a28d4d2fe93fae8d30e9258a073c9fcd9bd405521883903ff`; the original sealed-bank archive remains preserved separately.

Public evidence includes final-v4-holdout-registration.json, final-v4-holdout-aggregate.json, final-holdout-offline-verification.json, final-holdout-orchestration.json, final-holdout-slice1-consumed.json and final-holdout-exit-readback.json under evidence/. No private item content is published.

No promotion signature, incumbent supersession or retained-skill registry write occurred. Retention/signing is a separate decision. The earlier sequential gate remains unsigned and inactive because its simulation accepted zero good proposals; the pre-written-handler 8/8 result remains excluded as evidence of learning.
