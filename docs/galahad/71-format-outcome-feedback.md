# Format outcomes feed new research proposals

The completed four-call format study now feeds a versioned experience store and
bounded hypothesis generator. The actual import used zero new model calls. This
closes the receipt-to-experience-to-proposal path for these outcomes; it does not
establish a successful skill or finish the general learning conductor.

## Data and authority

`ExperienceStoreV2` reuses existing scoped authorization, private SQLite lifecycle,
append-only journal behavior, export and integrity checks. Its distinct contract
adds schema validity, source receipt hash and ordinal, and persists the explicit
origin `scientific_format_probe_v1`. Historical modules and receipts are unchanged.
Only shared-field validation uses a temporary legacy-shaped copy; stored records
retain their true origin. This is a trusted-host provenance assertion, not a remote
signature or authentication system.

The importer calls the nondispatching study validator, checks the fixed complete
four-row roster, recomputes scores and decoder/model identities, and preserves raw
outputs. Incomplete receipts, changed scores, revoked access, corrupt or deleted
stores and changed exports fail without resetting evidence or restarting inference.
Publication rechecks source receipts and source-code hashes. Exact replay preserves
existing bytes and modification times.

The two unrestricted outputs have `schema_shape_failure`; the two constrained
outputs have `abstention_contract_failure`. All four have `evidence_ok=null` because
contract-invalid output is not independently established factual error. There are
no real-world outcomes, rewards, approved knowledge writes or known historical
episode timestamps.

## Candidate generation

The frozen rules aggregate both strata for each failure class and propose existing
registered configurations:

| Failure | Proposed mutation | Decoder | Evidence |
|---|---|---|---|
| Schema shape | `format_contract` | unrestricted | Two raw failures, one per stratum |
| Abstention contract | `abstention_check` | constrained | Two raw failures, one per stratum |

The second proposal tests an existing evidence-sufficiency instruction. It is not
a proven empty-field repair. Both configurations may fail or regress. Every
hypothesis binds all contributing episode hashes, current store head, registered
configuration, decoder setting, immutable model digest and current source code.
Validation reconstructs the exact hypothesis against the current authorized store.
Unknown failure classes do not invent new mutations. Duplicate exact replay does
not append episodes or rewrite proposals.

This generator uses deterministic rules, not an LLM research agent. It explicitly
reports that negative-evidence enforcement is absent here; these capability probes
do not justify inserting efficacy-rejection records. Neither proposal is evaluated
or promoted. Fresh registered development evaluation remains the next step.

## Actual evidence

The real private import contains four episodes and generated two proposals, without
new inference. A fresh process disabled child dispatch, transport, metadata,
preload and runtime-version calls. Reopening the graph preserved ten artifacts,
including the original study receipts, byte for byte and with identical mtimes.

[Imported receipt](evidence/scientific-format-episodes-v1.json),
[episode export](evidence/scientific-format-episodes.jsonl),
[rolling manifest](evidence/scientific-format-episodes.jsonl.manifest.json),
[registered hypotheses](evidence/scientific-format-feedback-v1.json),
[restart evidence](evidence/scientific-format-feedback-v1-verification.json).

## Reproduction

```bash
.venv/bin/python scripts/verify_galahad.py baseline --timeout-seconds 600
PYTHONPATH=src .venv/bin/python scripts/run_scientific_format_feedback.py \
  --directory /Users/aliyildirim/nerve-research-runs/scientific-format-feedback-v1 \
  --episode-directory /Users/aliyildirim/nerve-research-runs/scientific-format-episodes-v1 \
  --study-directory /Users/aliyildirim/nerve-research-runs/scientific-candidate-format-study-v1 \
  --study-journal /Users/aliyildirim/nerve-research-runs/scientific-candidate-format-study-claims.sqlite \
  --expected-digest d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668
```

## Scope and release status

Added three modules (`experience_store_v2`, `scientific_format_episode_import`,
`scientific_format_feedback`), two CLI entry points and three test files. The
verification script includes the new tests in CPU/security groups. Documentation
and evidence artifacts accompany the implementation. Base commit is
`64a51b9dea66e8790692b5364c44294c0bb6d504` on
`feature/galahad-persistent-memory`; no PR, push, merge or deployment occurred.

The implementation and actual import are local; unit receipt inputs are mocked.
No model weights changed and no new performance gain is claimed. Powered selection,
independent holdout, retained skills, general outcome ingestion and three unattended
full learning cycles remain incomplete. GPU endpoint/budget, Galahad licensing and
real durable KV restoration remain unverified. Clinical data, signed real-world
rewards and patient-care deployment remain outside this synthetic run.

## Verification

All 2,044 tests passed in the clean timing profile (225.761 seconds), including
27 new outcome/store/feedback tests, 14 compact transport tests and six timing
harness tests. The earlier timed-out and flawed temporary completion runs are not
counted as successful coverage. See [measured test tiers](72-measured-test-tiers.md)
for the full profile, measured partition and subsequent clean tier runs.
