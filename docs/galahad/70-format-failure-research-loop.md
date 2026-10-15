# Failure-driven format research loop

The coordinator reads and validates the completed transport-smoke failure, runs
one fixed paired format probe, and records a decision. It never reruns the
predecessor. Durable shared claims and per-call claims bound the child to four
attempts across restarts; incomplete attempts consume the remaining budget.

Two fresh synthetic tasks compare the same registered conflict-check policy,
prompt and evidence with unrestricted versus schema-constrained decoding. The
supported measurement task runs constrained first; the unit-mismatch task runs
unrestricted first. The latter requires abstention, not unit conversion. Both
route through the real model. No development bank or sealed holdout is opened.

Each arm has a distinct policy hash binding the base configuration, decoder flag
and immutable model digest. Schema validity, format validity and strict answer
correctness are scored separately. The prospective gate requires more valid
formats, no reduction in exact answers and no newly introduced parsed wrong
answer. Passing only requests independent evaluation; two paired tasks cannot
establish efficacy, and neither outcome promotes a policy or trains weights.

[Ollama documents structured output support](https://docs.ollama.com/capabilities/structured-outputs).
That API contract motivated this test; installed-runtime evidence is recorded
separately. A transport failure stops the study without a comparison claim.

## Verification

All 1,997 repository tests passed in 178.680 seconds, including 27 new focused
study/coordinator tests. Independent code review cleared the frozen implementation.
Unit tests use mocked transport; the actual experiment is recorded below.

## Remaining scope

This implements a finite failure-to-experiment research graph. Powered matched
comparisons, independent holdout evaluation, retained skills, general outcome
adapters and the full Tier-6 conductor remain incomplete. GPU infrastructure,
Galahad licensing and durable KV recovery remain unverified. Clinical integration
remains synthetic-only, without deployment or patient-care authority.

## Actual runtime result

Four local model calls completed with Ollama 0.20.2 and
`qwen2.5-coder:1.5b` digest
`d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668`,
verified before and after. The host used the CPU research profile (128 output
tokens, 90-second socket timeout); hardware utilization was not measured.
Preload took 3.900 seconds. Each row is one observation, not a latency estimate.

| Task | Constrained | Seconds | Input/output tokens | Schema | Format | Exact |
|---|---|---:|---|---|---|---|
| Supported | yes | 71.445 | 520/51 | pass | fail | fail |
| Supported | no | 21.544 | 520/126 | fail | fail | fail |
| Unit mismatch | no | 43.652 | 378/75 | fail | fail | fail |
| Unit mismatch | yes | 15.035 | 378/51 | pass | fail | fail |

Constrained output met the generic JSON shape in 2/2 cases versus 0/2 for plain
output. Both arms scored 0/2 on full format and exact-answer correctness. The
constrained responses declared abstention while filling answer fields. The plain
responses copied schema structure. No parser repair was used. The coordinator
returned `retain_baseline`, and no efficacy rejection or skill was recorded.

Fresh-process graph resume with child dispatch, model calls, metadata, preload
and version functions disabled preserved twelve receipt/database artifacts byte
for byte and retained their modification times. No new inference was issued.

[Study receipt](evidence/scientific-candidate-format-study-v1.json),
[coordinator receipt](evidence/scientific-format-research-v1.json),
[restart evidence](evidence/scientific-format-research-v1-verification.json),
[test evidence](evidence/scientific-format-research-v1-tests.json).

The next candidate needs to address status/field consistency and instruction
comprehension on fresh tasks. This observation does not justify changing scores,
reusing the sealed holdout for tuning or declaring the model improved.

## Reproduction

From the repository root, the following command validates the existing terminal
graph without inference. The first run on its frozen fresh paths used four calls.
Changing paths does not bypass the shared consumed experiment claim.

```bash
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
PYTHONPATH=src .venv/bin/python scripts/run_scientific_format_research.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-format-research-v1 \
  --journal /Users/aliyildirim/nerve-research-runs/scientific-format-research-claims.sqlite \
  --smoke-directory /Users/aliyildirim/nerve-research-runs/scientific-candidate-transport-smoke-v1 \
  --smoke-journal /Users/aliyildirim/nerve-research-runs/scientific-candidate-transport-smoke-claims.sqlite \
  --study-directory /Users/aliyildirim/nerve-research-runs/scientific-candidate-format-study-v1 \
  --study-journal /Users/aliyildirim/nerve-research-runs/scientific-candidate-format-study-claims.sqlite \
  --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
```

## Change inventory and boundaries

Added `scientific_candidate_format_study.py` and
`scientific_format_research_coordinator.py` under the memory gateway, their two
`run_scientific_*` CLI entry points and matching test modules. Modified the
verification script to include both test modules in CPU/security groups, README
and the final implementation report. Added this document and four evidence JSON
artifacts. Existing transport, candidate executor, verified-memory authority,
receipt validators and exclusive-run lock are reused without modification.

Security tests found no regression in the covered claim, source, scope and restart
fixtures. This is local trusted-host research, not a production authentication or
clinical-security certification. Runtime calls above are real; unit-test model
responses are mocked. Nothing is deployed, pushed or merged, and no PR was created.
All changes are on `feature/galahad-persistent-memory`, based on
`75a15e888ebbeae9f295b4e134f53e397e043327`; the checkpoint commit containing this
file records the resulting source tree.


## Staged external-methods follow-on

See [implementation and limits](79-external-methods-adoption.md), drawing on [Regimes](https://arxiv.org/abs/2606.10241). This follow-on does not change this document's historical registration or evidence claims.
