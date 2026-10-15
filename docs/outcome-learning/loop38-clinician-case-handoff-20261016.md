# Loop 38 handoff: clinician-verified extraction cases

Planning only for the next work session. No real cases have been collected or
created by this handoff; no model run, external message or patient-data transfer
is authorized by it. Keep identifiable material in its approved source system.
Use an approved private intake location for reviewed deidentified artifacts,
never a public repository or chat transcript.

## Evidence boundary at handoff

The read-back mechanism receipt reports feedback-based selection at 8/8 versus
empty memory 0/8, with the best fixed prewritten handler also 8/8. Both adaptation
results (28/36 versus 24/36 and 12/36, plus 32 evaluation calls per domain) are
reruns of the existing synthetic A→B→A fixtures, not new real-world validation.
Galahad commit `5a60102` records `no_failure_supported_hypothesis`: the development
fixtures exposed no failures supporting a v4 change, so no v4 was designed or
tested. A real-case evaluation should address that evidence gap, not manufacture
failures or backfit a candidate to a test set.

## Intake manifest to prepare before scoring

Each proposed case needs a stable opaque `case_id`, `source_id`, source version
and content hash; source organization/custodian reference; document type;
collection/selection method and intended extraction question. Record permitted
research/evaluation use and the custodian's authorization reference. Source
provenance must be verifiable by the authorized reviewer without placing raw
identifiers in the manifest.

Record a deidentification attestation with method/version, scope, verification
date and reviewer ID. Verify free text, images, metadata, filenames and embedded
links as applicable. Keep any reidentification mapping exclusively with the
source custodian. If chronology is shifted, preserve relevant ordering and
record the transformation; do not label shifted dates as original dates.
An attestation is a reviewed record, not an automated guarantee. Unverified
provenance or incomplete deidentification blocks admission.

## Label and adjudication contract

Use a frozen schema that includes:

- `answerability`: answerable, should_abstain, or unresolved.
- Expected extracted `value`, `unit` and `source_id`, with source evidence spans
  in the deidentified artifact; explicit nulls when abstention is required.
- Applicable entity, measurement and time-window references; source freshness
  and conflict/agreement annotations where the extraction question requires them.
- `abstention_reason` from a predefined enumeration, such as missing evidence,
  incompatible units, unresolved conflict or unavailable current source.
- Reviewer IDs, verification timestamps, schema/scoring-rule version, and an
  adjudication status with the reason for any change to the initial labels.

A clinician qualified for the source domain verifies each label against the
source. A second independent reviewer checks disputed, ambiguous or clinically
material labels; record both original judgments and an adjudicator's resolution.
Reviewers should not see candidate predictions while setting reference labels.
Do not force agreement: unresolved cases remain explicit and follow the frozen
exclusion rule. Correct extraction from a document is not endorsement of the
clinical claim in that document.

## Split freeze and release to evaluation

Before candidate changes or scoring, group related cases by opaque patient and
source-family identifiers held privately by the custodian. Freeze patient-
**and** source-disjoint development and evaluation splits; keep duplicate,
near-duplicate, translated, longitudinal and derived-document families together.
If linkage cannot be verified, report the split as unverified rather than
claiming independence. Predeclare case counts, eligibility, strata, handling of
unresolved labels and missing outputs, controls, scoring tolerances and analysis.

Hash exact deidentified case artifacts, reference labels, split manifests,
reviewer/adjudication records and scoring configuration. Seal the evaluation
artifacts and record a manifest hash plus custody/access log before development
work begins. Public evidence may contain aggregate counts, opaque reviewer IDs
and hashes; the authorized team retains the private provenance and labels.
No candidate designer receives item-level evaluation feedback.

## Concrete next-session deliverables

1. An approved intake manifest and reviewer roster, or an explicit list of
   missing authorizations and attestations. Do not invent cases to fill gaps.
2. Reviewed reference labels with unresolved disagreements retained visibly.
3. A frozen disjoint-split manifest and hash-bound evidence bundle.
4. A preregistered evaluation plan stating what can be concluded from the
   available sample; no efficacy, promotion or retained-skill claim in advance.

No executable tests are needed for this documentation handoff. Dataset tooling,
model runs and clinical-use decisions remain separate authorized work.
