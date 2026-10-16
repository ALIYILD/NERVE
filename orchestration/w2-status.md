# W2 status

- Inspected genuine historical dev receipts and ExperienceStoreV2 schema.
- Verdict: incomplete_infrastructure (execution preflight not authorized yet).
- Model calls: 0. Pod cost: $0. No holdout reads.
- Added immutable 100-item registration, fixed keep/revert scoring, deterministic
  failure-cluster proposal generation, and stable rejection-memory keys.
- D1 blocker: ExperienceStoreV2 only supports scientific_format_probe_v1 ordinals
  0–3. Bank-study ingestion requires a separately reviewed versioned schema; do
  not invent provenance or claim historical format episodes as fresh bank studies.
- D2 blocker: fresh 100-item experiments require usable pinned RunPod preflight,
  lock, frozen evaluator/controls, and a dev-bank allocation adapter.
- No candidate ready for holdout hand-off. No kept/reverted study claimed.

Update: built explicit `ExperienceStudyStoreV2` companion without changing the
pinned original. Historical B dev rows replayed 100/100 from request claims and
wire responses; imported 100 typed episodes, generated two real failure-cluster
proposals. This is historical reuse, not three fresh iterations. Evidence:
`research/overnight-20261017/historical-b-import.json`.

Fresh B01 registered: `research/overnight-20261017/B01-registration.json`, SHA256
`aa964df1ad0477f0208474242708e37328385925a55faf97a1002e05b3c685e7`.
Remaining 100 agreement dev IDs exclude prior study; safety conclusions restricted
to answerable agreement strata. Runner awaits W0 preflight and test slot.
Family-A prior 7B v3 receipt is 100/100 (zero failures); obsolete baseline failures
must not be misrepresented as retained-v3 failures. New model calls remain zero.
