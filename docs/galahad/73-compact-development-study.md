# Registered compact development study

This is the user-requested development-only comparison: conflict-check candidate,
baseline, always-abstain and random, with 20 tasks each from conflict, supported
measurement and unit mismatch. Seed `20261015` fixes task selection, task/control
ordering and the requested model seed. No model reproducibility guarantee is made.

The registered 60-task dataset hash is
`844211e41ee45d6a9da6d22b3121f68e33702ccacde82b6913a9869933f026b7`.
The previously screened conflict hypothesis is
`2e540fe6530242612e17c0f1c7e537cad1b68fbaf873840038931411cf08f9d3`.
[Preregistration before inference](evidence/scientific-compact-dev-prereg-v1.json)
binds all selected development IDs/content hashes, policies, source hashes,
execution order, seed, model identity and the prospective verdict rule.

## Execution and scoring

The two model arms share the same compact prompt, evidence and decoder. Reversible
entity/source aliases shorten input while preserving the original provenance.
The strict decoder accepts `ABSTAIN` or `value|unit|source-alias`; it maps aliases
without repairing values or syntax. This is a new, explicitly hashed task interface,
not the earlier JSON-policy identity. Expected answers are never sent to inference.

The baseline runs the model for all 60 tasks. The candidate uses the existing
evidence-based conflict rule on 20 tasks and model inference on the other 40.
Always-abstain and random issue zero calls. Random selects, using a frozen hash of
seed and task ID, among `ABSTAIN` and copied source triplets, without using expected
answers. There are 240 scored rows and at most 100 task inference attempts.
Model-arm order is counterbalanced across tasks.

Total runtime-reported prompt tokens must be at most 150. No exact local tokenizer
was available, so this is verified after each call: an over-budget response is
preserved unscored and stops the consumed study. The output ceiling is 32 tokens,
socket timeout 90 seconds, wall budget three hours, and retries are disabled.
Model metadata and runtime version are checked before and after; one preload is
accounted separately. [Ollama documents the seed request field](https://docs.ollama.com/api/openai-compatibility).

The prospective development verdict requires candidate strict accuracy to exceed
baseline, always-abstain and random, with no stratum regression against baseline.
Otherwise the baseline is retained. Always-abstain has a 40/60 floor in this task
mix. A positive result requests review only; generalization remains insufficiently
powered. This evaluates a hybrid rule/model policy, not neural-weight learning.

Shared and local claims are durable before dispatch. Terminal validation rebuilds
the roster, routes, controls, scores, policy identities and exact call claims.
Interrupted or failed claims never trigger more inference. The CLI denies Python
open events for the supplied holdout and private seed paths; this is not an OS
sandbox. Only the development API is called, and no independent holdout capability
is issued. Work stops at the development verdict with no promotion.

## Verification before inference

Eighteen focused study tests passed in 22.841 seconds. Independent review cleared
source, control, policy, claim and holdout boundaries. The current fast tier, now
including those tests, passed 1,565 tests; see the measured timing artifact below.
The 499-test slow tier already passed once cleanly; no existing slow module changed.
[Fast-tier study check](evidence/suite-fast-dev-v1.json).

## Reproduction

The first execution on the registered fresh paths performs the bounded study.
A terminal rerun validates its consumed claim without dispatch. It never rerolls
selection or resets the budget.

```bash
PYTHONPATH=src .venv/bin/python scripts/run_scientific_compact_dev_study.py \
 --directory /Users/aliyildirim/nerve-research-runs/scientific-compact-dev-study-v1 \
 --journal /Users/aliyildirim/nerve-research-runs/scientific-compact-dev-study-claims.sqlite \
 --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668 \
 --bank-directory /Users/aliyildirim/nerve-research-runs/task-bank-v1 \
 --bank-manifest-sha256 e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6 \
 --screening-directory /Users/aliyildirim/nerve-research-runs/scientific-candidate-screen-v1 \
 --registration-directory /Users/aliyildirim/nerve-research-runs/scientific-candidates-v1 \
 --history-directory /Users/aliyildirim/nerve-research-runs/scientific-negative-history-v1
```
