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

Validation: 3 focused selection/provenance tests + 9 existing v2 compatibility
tests passed; one suite at a time under shared test lock, now released to W3.
B01 superseded before any calls by B01a to bound SSH subprocesses at 42s rather
than inherited 180s. Same items/rule; no outcome-driven revision. Active hash:
`47ae40566374094f3e3d99104e0569804c769b483373fc31113759822a35b409`.

Independent pre-call review found eager executor.map queued all100 jobs. Fixed:
at most4 submitted futures, worker failures immediately set cancellation,
checks before each claim and call, no replacement admission after a failure.
Three focused dispatcher tests pass, including injected first-batch failure
with exactly4 started items and zero subsequent items. Reviewer statically
confirmed the correction. Shared test lock released.

Active registration B01b supersedes B01a before any B study calls/results:
`094e6058bac759f3a16824f1124b8f9fd4c5a2cacccb9c6fe84cdae5a873e568`.
Schedule/keep rule unchanged. Both supersession records are preserved.
