# 127 — Bank v5 dev discrimination and measured-rate gate v3.2 analysis

**Dev-only result: v5 wins43, loses0, ties57; v4 correct57/100, v5 correct100/100. No promotion or holdout verdict.** Gate v3.2 fails the registered narrow-candidate power target, and no signing payload is prepared. Gate v3 remains canonical; v3.1 is withdrawn.

## Pre-call authorization and identity

The current user explicitly authorized the fixed100-item dev study. The originally bound Sweden A40 `5xndo7i7s5r9zn` could not start because its host had no free GPUs; it remained EXITED. The previously authorized original Sweden A40 `lvojhtouu5gede` started at $0.59/hour. Before any model call or dev allocation, an [operational amendment](evidence/bank-v5-dev-study-operational-amendment.json) bound the replacement pod identity and copied worker/runner filenames. Candidate, incumbent, source logic, model, decoding, dev schedule, timeout, retries and budget were unchanged. Original registration/authorization are preserved privately and the original public registration remains unchanged.

Identity verified NVIDIA A40, Ollama0.40.5, qwen2.5-coder:7b digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`. Remote worker bytes matched the pre-call source hash. The model/runtime caches were restored; no model substitution or laptop inference occurred.

Dev seed2026102101, model seed20261016, temperature0, max_tokens128, concurrency1. Exactly50 items from each agreement stratum in the registered order,100 total. V4 used the recorded model path; v5 used its unchanged deterministic implementation with zero additional calls.

## Dev result

| Stratum | n | v4 correct | v5 correct | v4 error | Discordance | v5 wins/losses/ties |
|---|---:|---:|---:|---:|---:|---|
| format-variant-agreement | 50 | 18 | 50 | 64% | 64% | 32/0/18 |
| multi-source-agreement | 50 | 39 | 50 | 22% | 22% | 11/0/39 |
| pooled | 100 | 57 | 100 | 43% | 43% | 43/0/57 |

Pooled v4 error/discordance43% (Wilson95% interval33.73–52.78%); conditional v5 win fraction43/43 (interval91.80–100%). Agreement-specific discordance intervals: multi-source12.75–35.24%; format-variant50.14–75.86%. These are dev estimates, not sealed-holdout promotion evidence. Zero observed losses is not proof that the candidate is never worse.

Decoded byte equivalence54/100 differs from strict-correctness ties57/100; representation and decision metrics are not conflated. Per-stratum intervals and all aggregate metrics are in [results](evidence/bank-v5-dev-study-result.json). Item-level tasks, raw model outputs, decoded records and journals remain private.

## Measured-rate v3.2 reachability

Rates are plugged in separately: multi-source discordance.22, format-variant.64, conditional wins1.0 in each. Four other answer strata use the historical zero-discordance plug-in, explicitly an assumption rather than proof. The57% tie rate is **within agreement items**; it is not spread across all answer strata. Under balanced nine-stratum sampling, the plug-in overall tie rate is90.444%.

| Seeds | Scenario | Accepts /10,000 | Primary accepts | Coverage incomplete after primary | Mean total items |
|---|---|---:|---:|---:|---:|
| registered | empirical | 0 | 1737 | 1737 | 169.48 |
| registered | good_085 | 0 | 294 | 294 | 111.76 |
| registered | never_worse | 0 | 1737 | 1737 | 169.48 |
| registered | optimistic_upper | 0 | 8417 | 8417 | 436.68 |
| fresh | empirical | 0 | 1825 | 1825 | 173.00 |
| fresh | good_085 | 0 | 331 | 331 | 113.24 |
| fresh | never_worse | 0 | 1825 | 1825 | 173.00 |
| fresh | optimistic_upper | 0 | 8455 | 8455 | 438.20 |

The empirical and never-worse fixtures cannot promote at this cap: silent strata cannot reach60 observations, and they have no discordances in the plug-in. The optimistic sensitivity uses marginal Wilson upper discordance endpoints for the two measured and four historically silent strata, with conditional wins1; it also observed zero promotions. This sensitivity is neither a joint confidence bound nor a proof of universal impossibility.

The bank now distinguishes the candidates on its agreement dev items. That does not cure the proposed gate’s all-nine allocation/60-item coverage conflict or its100-item primary power limit. No cap, schedule, threshold or guard was adjusted after seeing these results. No holdout continuation is authorized or performed.

The extra measured-target table in [measured-targets results](evidence/gate-v3_2/measured-targets-result.json) checks .90 good, regressed, neutral, harmful, H0 and small silent regressions at these rates, using the same seeds and guards. Its addendum is registered after measuring rates and before those simulations; it makes no gate change.


Measured-rate target checks (percentages; 10,000 streams each):

| Seeds | Good .90 | Regressed non-promotion | Neutral accept | Harmful accept | H0 promotion | Silent5% non-promotion | Silent10% non-promotion |
|---|---:|---:|---:|---:|---:|---:|---:|
| registered | 0.00 | 100.00 | 0.00 | 0.00 | 0.00 | 100.00 | 100.00 |
| fresh | 0.00 | 100.00 | 0.00 | 0.00 | 0.00 | 100.00 | 100.00 |

All small-regression identification rates are also0: the non-promotion rates reflect failed coverage/power, not successful localization. No silent60 bound is earned.

## Shutdown, cost and verification

The study completed100 logical calls in 375.35 wall seconds;101 physical attempts, one first-request timeout at the registered41.27-second limit, followed by an identical-request successful retry. Successful call median1.774s, maximum23.788s. All calls and retries are journaled.

Pod `lvojhtouu5gede` was stopped immediately after completion and independently read back EXITED; `5xndo7i7s5r9zn` was also read back EXITED. Running interval estimate8.93 minutes (0.14886 GPU hours), approximately$0.088 compute, not an invoice. Preserved storage is excluded. [Shutdown/cost receipt](evidence/bank-v5-dev-pod-exited.json).

Fresh-process offline replay matched all100 rows and the aggregate report, with network calls disabled and zero repeated inference. Source hashes were verified at admission and replay. A separate100-item mock harness test passed. Bank manifest remains `f09c2ab320813781b7dbfaf3e064593cc3355a3b1774890dd46253877ae771e4`; dev consumed100, reserve consumed0. All18 dev/reserve item files are mode000 after use; all1,800 reserve items (200 per stratum) remain sealed. No reserve contents were opened to check this status.

Evidence: [identity](evidence/bank-v5-dev-study-identity.json), [execution](evidence/bank-v5-dev-study-execution.json), [replay](evidence/bank-v5-dev-study-replay.json), [private-journal hash index](evidence/bank-v5-dev-study-private-journal-index.json), [post-dev seal](evidence/bank-v5-post-dev-seal-receipt.json), [v3.2 proposal and full simulations](126-gate-v3_2-silent-coverage-proposal.md).
