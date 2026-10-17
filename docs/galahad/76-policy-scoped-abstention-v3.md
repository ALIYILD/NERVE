# Policy-scoped abstention and candidate v3

The current gate reclassifies `model_at_floor` as **`prompt_induced_abstention`**,
scoped to the compact-with-abstain prompt policy. It validates both the historical
floor receipt and completed calibration v2 on the same model/digest. Historical
receipts and source modules remain unchanged. The same model digest is no longer
blocked from new proposals; the registered v3 proposal is permitted. The blocked
compact policy remains available only as the explicitly declared comparison
baseline, not for promotion. The original full JSON prompt (previously described
as “490-token”) is retired from new proposals and studies. Its frozen historical
implementation remains available for receipt verification.

This is an operational policy classification supported by ten compact abstentions
versus ten non-abstaining forced outputs. The condition-major calibration does not
isolate order effects or establish a universal model-capability ceiling. Current
proposal authorization is in `scientific_policy_gate_v2`; historical v1 gate APIs
are not rewritten or represented as universal enforcement boundaries.

## Frozen v3 policy

1. Inspect current evidence by exact entity, measurement and unit matching. Missing
   evidence, entity mismatch, absent matching unit/measurement, or conflicting
   matching values cause deterministic abstention with **zero model calls**.
2. Otherwise send the compact forced-extraction prompt with all current source
   facts, including decoys. Constrain JSON to numeric `value`, string `unit`, and
   string `source_id`, with no additional properties. The source enum contains
   exactly the aliases in that prompt; unit alternatives also come from its facts.

A valid target fact beside a decoy must not trigger abstention or cause the decoy
to be filtered away. Schema validity alone does not establish provenance: choosing
an allowed but irrelevant source is still wrong. No expected value, expected
source, task stratum or answer key is included in model inputs.

## Development registration

The five bank strata are supported measurement, conflict, unit mismatch,
measurement decoy and entity decoy, **20 development items each**. Missing-evidence
and entity-only-mismatch gate behavior is tested with synthetic unit fixtures;
the bank's entity-decoy stratum contains both the valid target and another entity.

The four arms are v3, the prior compact-with-abstain baseline, always-abstain, and
a seeded random choice among abstention and evidence-derived value/unit/source
triplets. Controls make no model calls. Model arm order alternates within items.
Seed `20261015` fixes selection, order and random choices and is requested from the
model; backend bitwise reproducibility is not assumed. Reuse of development items
is declared, and none of this is a held-out generalization result.

Expected accounting: **400 scored rows**, **100 baseline calls**, **60 candidate
calls**, and **40 deterministic candidate abstentions**, at most **160 model calls**.
The output limit stays 128 tokens. A **30-second per-call timeout** is approximately
three times the prior forced-answer maximum (10.520 seconds), providing headroom
over its measured 5.920–10.520-second range. The new JSON decoder could cost more;
this is a registered allowance, not a promise that it will finish. The two-hour
wall budget bounds the complete study; timed-out calls are not retried.

**Registered prediction:** measurement and entity decoys are the regression risk.
The extractor may choose an irrelevant value, unit or source even when its JSON
satisfies the schema. Report value, unit, provenance and strict correctness
separately, with exact abstention correctness on conflict/unit-mismatch items.
Value/unit/provenance are not applicable to expected-abstention items. Typed
candidate fields are scored independently without repairing prose or JSON; strict
correctness additionally requires the complete valid output contract.

The development gate requires candidate strict correctness to exceed baseline,
always-abstain and random, with no stratum regression against baseline. A passing
result requests review only. No policy activation, source-code self-modification,
weight training, production deployment, clinical use or holdout access follows.

## Registration and verification

The actual [policy adjudication](evidence/scientific-policy-gate-v2.json) reclassifies the block, and the [v3 proposal](evidence/scientific-candidate-v3-registration.json) is allowed. The [study preregistration](evidence/scientific-candidate-v3-preregistration.json) binds 100 items and 400 scheduled rows to dataset `9fcedd8027a4bbace580f5752e5aeee6f653d75e7cf5d022feac683375acc089`. [Timeout rationale](evidence/scientific-candidate-v3-preregistration-notes.json) is recorded before inference.

The 26 focused tests passed. The full fast tier then passed **1,615 tests in 120.906 seconds** (121.954 seconds including discovery), with zero failures/errors/skips. [Fast evidence](evidence/suite-fast-v3.json). Existing slow modules were unchanged and not rerun. The `schema_valid` field is a local contract check including numeric safety bounds, not proof of server-side schema enforcement.

## Completed development verdict

**`candidate_requires_review`**. All 400 rows and 160 model calls completed with
no timeout or retry. The preregistered development gate passed. This is a hybrid
host-gate and extraction-policy result on reused synthetic development items;
generalization remains `insufficient_power`. No weights changed, policy was
promoted, or holdout accessed.

| Arm | Supported | Conflict | Unit mismatch | Measurement decoy | Entity decoy | Strict total |
|---|---:|---:|---:|---:|---:|---:|
| Candidate v3 | 20/20 | 20/20 | 20/20 | 20/20 | 19/20 | **99/100** |
| Compact baseline | 0/20 | 20/20 | 20/20 | 0/20 | 0/20 | 40/100 |
| Always-abstain | 0/20 | 20/20 | 20/20 | 0/20 | 0/20 | 40/100 |
| Seeded random | 8/20 | 4/20 | 11/20 | 3/20 | 3/20 | 29/100 |

On the 60 extraction items, candidate value correctness was **59/60**, unit
**60/60**, provenance **59/60**, and strict **59/60**. Local schema validity was
60/60. The remaining 40 candidate items abstained correctly through deterministic
gates with zero model calls. Baseline returned ABSTAIN on all 100 calls.

The sole candidate error was entity-decoy item
`dev-1f3b095cae6334fc9770bb3ad7ba61639ba89554bd4da385ac66be97a2019295`.
Its raw output selected `5617.4 mg`, alias `A1`, belonging to the decoy entity.
The requested entity's fact was `5616.7 mg`, alias `A0`. Value and provenance were
wrong while unit and schema were valid. This is consistent with the registered
decoy-risk prediction: an enum restricts source names but cannot ensure the right
source is selected. There were 59 paired gains, zero paired strict-score losses
and 41 ties against baseline; nevertheless this error is a new incorrect answer
where baseline abstained, and must not be hidden by the paired-score summary.

Candidate's 60 calls took 1,123.377 seconds in summed call intervals
(range 9.290–27.742 seconds), versus baseline's 100 calls at 812.941 seconds
(range 2.634–17.865 seconds). Thus fewer calls did not produce lower summed
inference time. Total measured call intervals were 1,936.318 seconds (32.27
minutes), not total study wall time. Usage was 12,416 prompt and 2,243 completion
tokens, 14,659 total. Preload took 6.020 seconds separately. Monetary cost, energy
and GPU utilization were not measured. Model digest and Ollama 0.20.2 matched
before and after execution.

[Full receipt with raw text](evidence/scientific-candidate-v3-study.json) and
[read-only verification](evidence/scientific-candidate-v3-verification.json) retain
the evidence. A fresh validator reconstructed every row and claim with network
and inference dispatch disabled; seven current artifacts and eleven predecessor
artifacts retained their bytes and modification times. Independent review also
reconciled all 400 rows, 160 completed claims, 70 source pins and the decoy error.
The raw report SHA-256 is
`ae24bfac8beb3fe37e3eb61efda5c8e2e5e9ac761e5a2b4c785e3acc7d9feea7`.
Execution stopped at this verdict.

## Reproduction

The following command verifies the consumed terminal receipt without inference.
`--prepare` registers only; omit both switches for the initial single execution.
A completed or failed claim cannot be rerolled for another sample.

```bash
PYTHONPATH=src .venv/bin/python scripts/run_scientific_candidate_v3_study.py --verify \
 --directory /Users/aliyildirim/nerve-research-runs/scientific-candidate-v3-study \
 --journal /Users/aliyildirim/nerve-research-runs/scientific-candidate-v3-claims.sqlite \
 --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668 \
 --bank-directory /Users/aliyildirim/nerve-research-runs/task-bank-v1 \
 --bank-manifest-sha256 e11a17a72fb6482dc5978ee5e3c8d4b488f1d71d9c8e060aa382637020718ae6 \
 --calibration-directory /Users/aliyildirim/nerve-research-runs/scientific-substrate-calibration-v2
```

The CLI denies Python opens of the real task-bank holdout and sibling private seed
paths. This is not an OS sandbox; the trusted host remains responsible for file
isolation. Development readers never receive a holdout capability.


## Staged external-methods follow-on

See [implementation and limits](79-external-methods-adoption.md), drawing on [Regimes](https://arxiv.org/abs/2606.10241). This follow-on does not change this document's historical registration or evidence claims.
