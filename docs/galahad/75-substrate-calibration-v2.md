# Substrate calibration v2

This is a separately registered diagnostic study, not a retry or continuation of
v1. V1's consumed claim and its one raw response remain unchanged. V2 uses the
same ten supported development items, identical three prompt contracts, identical
128-token output ceiling, and seed `20261015`. No prompt tuning, promotion or
holdout access is authorized.

## Registered changes and justification

| Change | Justification before execution |
|---|---|
| Per-call timeout 90 → 240 seconds | The user reported original-prompt latencies of 35–70 seconds the prior night. Repository receipts additionally record 43.652 seconds for an unconstrained original-format unit-mismatch call, 71.445 seconds for a constrained supported call, and 78.891 seconds for the original-format smoke call. V1's original call exceeded 90 seconds. A 240-second ceiling allows substantial headroom without changing model inputs or retrying timed-out calls. |
| Wall budget 30 → 60 minutes | Thirty calls at the reported upper latency of 70 seconds total 35 minutes before overhead; 60 minutes provides bounded overhead and variation allowance. This is not a guarantee that 30 worst-case 240-second calls fit: the wall budget takes precedence. |
| Condition-major order: compact, compact-forced-answer, original | The two shorter conditions finish first, preserving an interpretable paired ten-item result if the original prompt remains infeasible. Original is last; no counterbalanced-order or causal prompt-length claim is made. |

The historical latency examples are heterogeneous observations, not a matched
performance benchmark or proof that every original call will complete in 240
seconds. The 35–70-second range is attributed to the user; the exact repository
measurements above are separately recorded evidence.

All returned raw text is preserved, including malformed and length-terminated
responses. Answer rate means a valid parsed answer; correctness remains strict
against the supported item's expected fields. Forced answers are scored for
correctness, without treating a higher response rate as an improvement.

If an original-condition call times out after both compact conditions complete,
their results are reported as the partial calibration result. The separate
infrastructure finding is **“original prompt infeasible on this substrate”**.
It applies to this model, runtime and registered limits; it is not an answer
accuracy or general model-capability finding. No returned output is fabricated
for a timed-out call. Execution stops, without retrying the call or accessing a
holdout. Other failures do not receive this special completed-condition result.

## Independent reproduction

The CLI's `--prepare` mode registers the new study without inference. The normal
mode executes that registration once; `--verify` checks a terminal receipt without
network calls or new inference. V1 is a read-only predecessor input. Both versions
use separate study directories and external claim journals.

```bash
PYTHONPATH=src .venv/bin/python scripts/run_scientific_substrate_calibration_v2.py --verify \
 --directory /Users/aliyildirim/nerve-research-runs/scientific-substrate-calibration-v2 \
 --journal /Users/aliyildirim/nerve-research-runs/scientific-substrate-calibration-v2-claims.sqlite \
 --predecessor-directory /Users/aliyildirim/nerve-research-runs/scientific-substrate-calibration-v1 \
 --predecessor-journal /Users/aliyildirim/nerve-research-runs/scientific-substrate-calibration-claims.sqlite \
 --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668 \
 --bank-directory /Users/aliyildirim/nerve-research-runs/task-bank-v1 \
 --bank-manifest-sha256 e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6
```

The CLI blocks Python opens of the supplied bank's holdout and private seed paths;
this is not an OS-wide sandbox. Only the development accessor is used. A partial
original-timeout result has a consumed failed study status and the CLI exits 1,
while retaining the explicitly permitted completed-condition report.

## Validation before inference

The 21 v2 focused tests passed in 63.212 seconds (transcribed agent tool output). All 21 also passed in the initial full fast attempt, which later reached its 180-second deadline. The measured heavy v2 module was assigned to slow. The unchanged fast set then passed **1,589 tests in 97.604 seconds**, with zero failures/errors/skips; total gate time was 98.770 seconds. Existing 499 slow tests were not rerun; their prior clean run remains separate evidence. The updated slow timeout is 549 seconds, twice the combined measured estimate plus 60 seconds. No current combined slow-suite pass is claimed.

[Focused/timeout evidence](evidence/scientific-substrate-calibration-v2-test-evidence.json) · [Fast-tier evidence](evidence/suite-fast-substrate-v2.json) · [Preregistration](evidence/scientific-substrate-calibration-prereg-v2.json).

## Actual calibration result

**All 30 calls completed in 872.237 seconds (14.54 minutes), with no timeouts.**
Ten responses were saved for each condition. The model digest and Ollama runtime
`0.20.2` matched before and after. No retry, prompt change, holdout access, promotion
or model-weight update followed.

| Condition | Non-abstaining outputs /10 | Valid parsed answers /10 | Strict correct /10 | Declared abstentions /10 | Malformed /10 | Length-terminated /10 |
|---|---:|---:|---:|---:|---:|---:|
| Compact | 0 | 0 | 0 | 10 | 0 | 0 |
| Compact forced answer | 10 | 0 | 0 | 0 | 10 | 0 |
| Original | 10 | 0 | 0 | 0 | 10 | 9 |

The registered **valid-answer rate and strict correctness are 0% in each
condition**. Non-abstaining output is 100% for forced-answer and original, but it
is not a valid-answer rate. Strict correctness requires the exact measurement
and source under the existing output contract; malformed text is not repaired.

A separate descriptive inspection of all forced-answer raw outputs found the
correct numeric measurement and `mg` in **10/10**. Every response used `facts`
instead of source alias `A0`, and also failed the output grammar. For example,
the expected `240.0|mg|A0` was returned as:

```text
Value|unit|source
240.0 mg|milligram|facts
```

This is evidence of successful value copying in the raw text, despite failed
format/provenance compliance. It does not justify calling the forced condition
factually wrong in every respect, nor does it make those outputs valid evidence-
linked answers. This inspection is explicitly **post-run descriptive analysis**;
it does not alter the registered scores or gate. Original outputs copied the JSON
schema structure instead of returning the required flat object; nine also reached
the unchanged 128-token output ceiling.

| Condition | Actual prompt-token range | Prompt / completion tokens | Measured per-call seconds, min–max |
|---|---:|---:|---:|
| Compact | 68–69 | 688 / 40 | 2.405–9.966 |
| Compact forced answer | 59–60 | 598 / 179 | 5.920–10.520 |
| Original | 382–389 | 3,867 / 1,226 | 44.998–131.721 |

Total recorded tokens: **6,598**. The first original request took 131.721 seconds,
so v2's longer timeout allowed an observation that v1's 90-second limit could not.
These are one-run measurements in fixed condition order; no matched performance
or prompt-length causal effect is claimed.

**No “original prompt infeasible on this substrate” finding is recorded:** all ten
original requests returned. Original declared abstentions were **0/10**, so the
≥9/10 rule also does **not** establish “1.5B model is the ceiling.” The completed
study's registered verdict is `calibration_complete_requires_review`. The earlier
same-digest `model_at_floor` proposal gate remains unchanged; this diagnostic does
not authorize new policies or promotion.

[All raw responses and registered scores](evidence/scientific-substrate-calibration-v2.json) ·
[Descriptive forced-answer inspection](evidence/scientific-substrate-calibration-v2-raw-inspection.json) ·
[Read-only verification](evidence/scientific-substrate-calibration-verification-v2.json).
Verification disabled network/inference functions, checked all 30 claims and scores,
and confirmed seven current artifacts and all five recorded v1 predecessor
artifacts retained their bytes and modification times. Work stops at this report.


## Staged external-methods follow-on

See [implementation and limits](79-external-methods-adoption.md), drawing on [Regimes](https://arxiv.org/abs/2606.10241). This follow-on does not change this document's historical registration or evidence claims.
