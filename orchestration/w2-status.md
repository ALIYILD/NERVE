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

FINAL: B01b kept35/0/65,100RunPod calls,198.899s, both controls beaten,0observed
domain violations. W0 stopped pod and verified allEXITED. Replay verified;
200fresh arm episodes ingested; v5 next-clustering has0failures/0proposals.
Leaderboard and result/replay receipts committed under research/.

A registered CPU audit:900dev items all canonical-v3 unsupported_evidence;
300correct deterministic abstentions,600incorrect. 900episodes imported,
6clusters→1distinct routing hypothesis, not6ideas. A01 next-study design hash
1a4044ba4bbbdeb84fd2fc722701c2e3aa69862dc62c2d4dcd3212643a93a680;
not executed, still needs runner/review/authorization. Stop honored: no new
experiments/inference after W0 third-infrastructure-failure declaration.
W2 total fresh calls100; fresh experiments1kept/0reverted; total imported1200
including historical100B + fresh200B + deterministic900A. D1/D2partial.
