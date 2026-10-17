# Candidate v3: sealed slice-1 holdout

**Current adjudication:** `incomplete_infrastructure` supersedes the historical verdict below. [Transport policy v2 and gate](78-transport-policy-and-slice2.md) preserve the original receipt; slice 1 remains consumed.

V3 development was committed unchanged as `cb65c81` on
`feature/galahad-persistent-memory`. This study reuses its transport, prompts,
scoring, seed `20261015`, 128-token output cap, 30-second call timeout and
alternating arm order. No candidate, prompt or scoring changes are permitted.

## Existing bank and partition

The original manifest is pinned to
`e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6`.
The bank was created before v3. It contains seven strata: six with 43 items and
stale-vs-current with 42. Deterministic SHA-256 ordering of
`20261015:partition:task_id`, independently within each study stratum, assigns
first 20 to slice 1 and next 20 to slice 2. Allocation does not inspect answers
or candidate performance. Every slice has its own content hash and manifest hash.

- Slice 1: 100 items, 20 each conflict, supported-measurement, unit-mismatch,
  measurement-decoy, entity-decoy.
- Slice 2: the same composition, 100 different items; not evaluated or opened by
  the study runner.
- Reserve: three remaining items per study stratum (**15 total**, not 15 each),
  plus all 43 multi-source-agreement and 42 stale-vs-current items, 100 total.

The trusted partitioner necessarily reads the original bank to create its slices;
no item contents leave that process. After partitioning, all slice files and the
original combined holdout have mode `000`. Only slice 1 is briefly opened by the
trusted one-use gate, then returned to mode `000`. Slice 2, reserve, original
holdout and bank seed are denied by the runner's Python-open audit hook as well.
Private study files are mode `600` under a mode `700` directory. These controls
are not isolation against the trusted owner/root restoring permissions or
arbitrary same-user processes. No generator/proposal process is run with access
to this directory. Do not interpret filesystem hashes as secrecy.

## Frozen acceptance and disclosure

The study has four matched arms: unchanged candidate v3, unchanged compact
baseline, always-abstain, and the unchanged seeded random control. It has 400
scored rows, with 160 expected model calls (60 candidate and 100 baseline).
The deterministic candidate gates make zero model calls on 40 items. The total
wall budget is 7,200 seconds. Claims are durable before calls; no retries or
second execution of slice 1 are allowed. An incomplete run retains the incumbent.

`promote_proposal` requires candidate strict total to exceed each of the three
controls and no candidate stratum below always-abstain. Otherwise the verdict is
`retain_incumbent`. This produces a proposal verdict only; promotion requires the
user's separate decision. The old development criterion against baseline per
stratum is not substituted for this registered holdout criterion.

Every arm/stratum receives a two-sided 95% Wilson interval (z=1.959963984540054)
for strict correctness, n=20. These are descriptive marginal intervals without
multiplicity correction, not an additional significance threshold. Value, unit,
provenance, abstention and schema component counts are retained separately.
Item-level outputs, inputs, answer keys, scores and identifiers remain in private
gate evidence. The exporter constructs stratum counts and derived summaries
explicitly; it never exports a redacted copy of the private report. Public
registration carries hashes and counts, not rosters. Failure messages expose only
exception classes, not model text or item contents.

## Limits and later work (not executed)

Both multi-source-agreement and stale-vs-current remain untested by v3. They must
be included in a future registered study before claims extend beyond the five
study strata. The current code filters `current=false`; therefore a claim that
it necessarily chooses stale facts first is not established. Multi-source
agreement/source-choice behavior and recency remain hypotheses requiring future
aggregate evidence, not inspection of reserve items now. No reserve study runs
as part of this work.

After slice 2 is consumed, generate and seal a fresh bank v2 with a new private
seed **before designing the next candidate**. Holdout generation must precede
candidate design. This existing bank shares generation templates with development;
instance independence does not establish unseen-template generalization.

## Reproduction

Registration is exclusive; execution consumes slice 1 once. Only the verification
command is suitable after consumption; it reads gate-private evidence and emits
aggregates, never calls the model, and never opens unused slices:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_scientific_v3_holdout.py verify \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-v3-holdout-slice1
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_scientific_v3_holdout.py
```

The test suite uses a newly generated synthetic fixture bank, not the real
holdout. Its complete mock run is test evidence only, not holdout efficacy.

## Registration evidence

[Preregistration](evidence/scientific-v3-holdout-preregistration.json) was frozen
before inference. Its SHA-256 is
`8d5ae578c8666c77a3fb8f1db80635dd64f3b864e2e32ccda9fec86f36862021`.

| Set | Manifest SHA-256 | Items |
|---|---|---:|
| Slice 1 | `19467558564553afdafb8b09a76de495f53a3cd1a318b8752d4bdc34a2e6f505` | 100 |
| Slice 2 | `3b73859075f0080f1a06bf780f491038e4620ec3afec476b8fdb304fe04754a1` | 100 |
| Reserve | `b7a9d02c7865eaeeec6af0fa52ea8d1725c7dc3842bd5a18767572eae4abb4d2` | 100 |

Eight focused tests passed in 170.277 seconds, including a complete mocked
400-row/160-call run, one-use rejection, aggregate privacy, partition invariance
to answer changes, Wilson endpoints and guarded unused-path rejection. The
initial test run found a `/tmp` canonicalization problem in the audit helper; it
was repaired and all eight tests rerun before any real holdout access. These
long-running integration tests are invoked separately; the previously measured
fast tier and its source-pinned verifier were not changed or rerun.

## Terminal result: retain_incumbent

The registered slice-1 attempt ended **failed_consumed**, with verdict
**retain_incumbent**. The 35th model attempt raised `TimeoutError` under the
unchanged 30-second call timeout. There were **34 completed calls, 81 scored
rows**, and 488.779 seconds (8.15 minutes) of measured study wall time. The
planned 100-item/400-row comparison was not completed. No call was retried;
slice 1 is consumed. Slice 2 and the reserve remain sealed. No promotion occurred.

The following are **partial descriptive results**, not the registered full-sample
acceptance result. Cells show strict correct/evaluated and the 95% Wilson interval.
Incomplete arms have different denominators; these figures must not be presented
as a successful matched holdout comparison. No final n=20-per-stratum estimate
is available. Missing outcomes are not imputed.

| Stratum | Candidate v3 | Baseline | Always-abstain | Random |
|---|---|---|---|---|
| supported-measurement | 3/3 (43.9–100.0%) | 0/3 (0.0–56.1%) | 0/3 (0.0–56.1%) | 2/3 (20.8–93.9%) |
| conflict | 3/3 (43.9–100.0%) | 3/3 (43.9–100.0%) | 3/3 (43.9–100.0%) | 1/3 (6.1–79.2%) |
| unit-mismatch | 4/4 (51.0–100.0%) | 4/4 (51.0–100.0%) | 4/4 (51.0–100.0%) | 3/4 (30.1–95.4%) |
| measurement-decoy | 3/3 (43.9–100.0%) | 0/3 (0.0–56.1%) | 0/3 (0.0–56.1%) | 1/3 (6.1–79.2%) |
| entity-decoy | 7/7 (64.6–100.0%) | 0/8 (0.0–32.4%) | 0/7 (0.0–35.4%) | 2/7 (8.2–64.1%) |

Candidate's completed extraction component counts were value **13/13**, unit
**13/13**, provenance **13/13**, and strict **13/13**; seven deterministic
abstentions were correct without model calls. These are incomplete observations
and do not override the failure verdict or justify promotion.

[Aggregate report](evidence/scientific-v3-holdout-aggregate.json) contains the
stratum-level counts for all four arms. [Read-only verification](evidence/scientific-v3-holdout-verification.json)
recomputed private rows and controls with network/inference entry points disabled.
All 91 checked current artifacts retained their hashes and modification times.
Unused slice/reserve inode, size, modification/access times and mode remained
unchanged; both remained unreadable. The published registration matches the
private preregistration exactly. The original holdout and all slice files remain
mode `000`. Item-level evidence was not exported to the repository or proposal
paths, and no reserve or slice-2 inference was performed.

Execution stopped at the verdict. No timeout adjustment, new candidate, rerun,
additional holdout study or promotion follows from this report. V3's original
commit remains `cb65c81`; this subsequent holdout implementation/report is left
uncommitted for review.


## Staged external-methods follow-on

See [implementation and limits](79-external-methods-adoption.md), drawing on [Lewis](https://openreview.net/forum?id=4ob0d33A2l). This follow-on does not change this document's historical registration or evidence claims.
