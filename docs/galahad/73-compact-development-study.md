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

## Actual development verdict — stop here

**Retain the baseline. No improvement demonstrated.** All 100 real model outputs
were exactly `ABSTAIN`. Both model arms failed every supported-evidence task,
and their overall score matched the always-abstain control.

| Arm | Conflict /20 | Supported /20 | Unit mismatch /20 | Total /60 | Task model calls |
|---|---:|---:|---:|---:|---:|
| Baseline | 20 | 0 | 20 | 40 (66.67%) | 60 |
| Conflict-check candidate | 20 | 0 | 20 | 40 (66.67%) | 40 |
| Always-abstain | 20 | 0 | 20 | 40 (66.67%) | 0 |
| Random | 4 | 8 | 11 | 23 (38.33%) | 0 |

All 240 rows passed the compact format grammar. Candidate versus baseline had
zero paired gains, zero losses and 60 ties. The candidate did not exceed baseline
or always-abstain, so the preregistered gate failed. Deterministically handling
20 conflicts avoided 20 model calls, but that is rule-based computation avoidance,
not demonstrated answer-quality improvement or learned model weights.

Every measured prompt was **67–83 total runtime tokens**, below the declared 150
ceiling. Exactly 100 task calls consumed 7,160 prompt tokens and 400 completion
tokens (7,560 total). The summed measured model-call intervals were 192.795 seconds;
this is one study observation, not a representative latency or speedup benchmark.
No energy, hardware utilization or monetary cost was measured. The runtime was
Ollama 0.20.2 before/after, with `qwen2.5-coder:1.5b` immutable digest
`d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668`.

A fresh-process terminal validation disabled inference, metadata, preload,
runtime-version calls and both-split bank status. The exact-path file guard was
active. Nine checked artifacts retained identical bytes and modification times.
Independent review recomputed the rows, controls and verdict, checked all 50 source
pins and confirmed 60 baseline plus 40 candidate durable completed call claims.
Preregistration and runtime protocol match. No retries, holdout reads, policy
promotion, negative-efficacy journal insertion or new experiment followed the
verdict. The generalization verdict remains `insufficient_power`.

[Actual receipt](evidence/scientific-compact-dev-study-v1.json),
[fresh-process verification](evidence/scientific-compact-dev-study-v1-verification.json),
[combined test coverage](evidence/compact-dev-test-coverage-v1.json).

## Checkpoint and remaining boundaries

The study was committed before inference at `cda6ffbb5bfccb003995a0083eea12b9b06ecc76` on
`feature/galahad-persistent-memory`. The preceding feedback/tier checkpoint was
`e09e0d2`. Current fast coverage is 1,565 tests in 64.888 seconds including discovery;
the single clean slow run covered 499 tests in 169.922 seconds. Slow test sources
are unchanged, and the disjoint union covers all 2,064 current test IDs with no
failures, errors or skips. The twenty slowest measured tests and the original
verifier change are in [the tier report](72-measured-test-tiers.md).

Added the compact development study module, CLI, 18 tests and preregistration;
updated CPU/security groups to include compact transport/study tests. Runtime
results are real local inference; unit model responses are mocked. Nothing was
pushed, merged, deployed or connected to real clinical data. No PR was created.
GPU/Galahad licensing and durable KV restoration remain unverified. Tier 6 and
broader self-learning are incomplete. Per the user stop instruction, work ends
at this development verdict and the holdout remains unopened.
